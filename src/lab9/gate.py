"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []
    import math as _math
    # NaN / inf in PR metrics
    for k, v in (pr.get("metrics") or {}).items():
        if isinstance(v, float) and (v != v or v in (float("inf"), float("-inf"))):
            problems.append(f"metric {k} is nan/inf")
    # row count
    man = pr.get("manifest", {})
    items = man.get("items")
    seeds = man.get("seeds") or []
    if items is not None and len(pr.get("rows", [])) != items * len(seeds):
        problems.append(f"row count {len(pr.get('rows', []))} != {items} x {len(seeds)}")
    # (item_id, seed) set matches baseline
    pr_keys = {(r.get("item_id"), r.get("seed")) for r in pr.get("rows", [])}
    base_keys = {(r.get("item_id"), r.get("seed")) for r in base.get("rows", [])}
    if pr_keys != base_keys:
        problems.append("row (item_id, seed) set differs from baseline")
    # evaluator failures
    if pr.get("evaluator_failures"):
        problems.append("evaluator_failures non-empty")
    spec_metric_ids = {m["id"] for m in spec.get("metrics", [])}
    for r in pr.get("rows", []):
        for mid in spec_metric_ids:
            if mid in r and r[mid] is None:
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} has None for graded metric {mid}")
                break
    # base_spec ratchet
    if base_spec is not None and pr.get("manifest", {}).get("eval_set_sha") == base.get("manifest", {}).get("eval_set_sha"):
        # only ratchet when same eval-set version
        if spec.get("eval_set_version") == base_spec.get("eval_set_version"):
            # metric thresholds
            base_by_id = {m["id"]: m for m in base_spec.get("metrics", [])}
            for m in spec.get("metrics", []):
                mid = m["id"]
                th = m.get("threshold", {}) or {}
                bth = (base_by_id.get(mid, {}).get("threshold", {}) or {}) if mid in base_by_id else None
                if mid not in base_by_id:
                    # metric disappeared? new metric allowed; but a metric present in base_spec that disappears is caught below
                    pass
                if bth is not None:
                    # max may not rise
                    if "max" in th and "max" in bth and th["max"] > bth["max"] + 1e-12:
                        problems.append(f"threshold loosened: {mid} max {th['max']} > {bth['max']}")
                    if "min" in th and "min" in bth and th["min"] < bth["min"] - 1e-12:
                        problems.append(f"threshold loosened: {mid} min {th['min']} < {bth['min']}")
                    if base_by_id[mid].get("blocking") and not m.get("blocking"):
                        problems.append(f"blocking metric {mid} became non-blocking")
                    if bth.get("no_significant_drop") and not th.get("no_significant_drop"):
                        problems.append(f"no_significant_drop dropped for {mid}")
                # metric disappeared entirely
            for bm in base_spec.get("metrics", []):
                if bm["id"] not in {m["id"] for m in spec.get("metrics", [])}:
                    problems.append(f"metric {bm['id']} disappeared from spec")
            # slices
            base_slices = {s.get("name"): s for s in (base_spec.get("slices") or [])}
            spec_slices = {s.get("name"): s for s in (spec.get("slices") or [])}
            for name, bs in base_slices.items():
                if name not in spec_slices:
                    problems.append(f"slice {name} dropped from spec")
                    continue
                ss = spec_slices[name]
                bth = bs.get("threshold", {}) if "threshold" in bs else None
                # compare min
                if "min" in bs and "min" in ss and ss["min"] < bs["min"] - 1e-12:
                    problems.append(f"slice {name} min loosened")
                if bs.get("blocking") and not ss.get("blocking"):
                    problems.append(f"slice {name} blocking dropped")
                if bs.get("no_significant_drop") and not ss.get("no_significant_drop"):
                    problems.append(f"slice {name} no_significant_drop dropped")
            # no_significant_drop at spec level handled above
    # slice tags differ
    base_rows_by_key = {(r.get("item_id"), r.get("seed")): r for r in base.get("rows", [])}
    for r in pr.get("rows", []):
        br = base_rows_by_key.get((r.get("item_id"), r.get("seed")))
        if br is not None and (r.get("slices") or []) != (br.get("slices") or []):
            problems.append(f"slice tags changed for {r.get('item_id')}@{r.get('seed')}")
    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {}) or {}
    n_res = bs.get("n_resamples", 1000)
    rng = bs.get("rng", 2027)
    for sl in (spec.get("slices") or []):
        name = sl["name"]
        metric = sl["metric"]
        from lab9.eval import per_item
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        keys = sorted(set(a) & set(b))
        mean_val = (sum(a.values()) / len(a)) if a else 0.0
        line = f"  slice:{name}/{metric:<22} {mean_val!s:<8}"
        fail = False
        if "min" in sl and mean_val < sl["min"]:
            fail = True
        note = ""
        if sl.get("no_significant_drop") and keys:
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=n_res, rng=rng)
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi <= 0 and d < 0:
                fail = True
        if fail:
            blocked.append(f"slice:{name}/{metric}")
        lines.append(f"  slice:{name}/{metric:<22} {mean_val!s:<8} {note:<28} {'BLOCK' if fail and sl.get('blocking') else ('ok' if not fail else 'warn')}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if d < 0 and hi <= 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
