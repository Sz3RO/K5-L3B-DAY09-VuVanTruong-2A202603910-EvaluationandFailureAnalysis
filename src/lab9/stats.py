"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge sequences must have the same length")
    tp = fp = fn = tn = 0
    for h_raw, j_raw in zip(human, judge):
        h = h_raw.strip().upper() == POS
        j = j_raw.strip().upper() == POS
        if h and j:
            tp += 1
        elif not h and j:
            fp += 1
        elif h and not j:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    tp, fp, fn = cm["tp"], cm["fp"], cm["fn"]
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    n = len(human)
    if n == 0 or len(judge) != n:
        raise ValueError("non-empty equal-length sequences required")
    cm = confusion(human, judge)
    p_o = (cm["tp"] + cm["tn"]) / n
    p_h_pos = (cm["tp"] + cm["fn"]) / n
    p_j_pos = (cm["tp"] + cm["fp"]) / n
    p_e = p_h_pos * p_j_pos + (1.0 - p_h_pos) * (1.0 - p_j_pos)
    if math.isclose(1.0 - p_e, 0.0, abs_tol=1e-12):
        raise ValueError("Cohen's kappa is undefined when p_e == 1")
    return (p_o - p_e) / (1.0 - p_e)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    denom = sensitivity + specificity - 1.0
    if math.isclose(denom, 0.0, abs_tol=1e-12) or denom < 0:
        return min(1.0, max(0.0, observed_rate))
    est = (observed_rate + specificity - 1.0) / denom
    return min(1.0, max(0.0, est))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    import numpy as np
    from scipy.stats import bootstrap

    a_arr = np.asarray(list(a), dtype=float)
    b_arr = np.asarray(list(b), dtype=float)
    if a_arr.shape != b_arr.shape:
        raise ValueError("a and b must have the same shape")
    if a_arr.size == 0:
        raise ValueError("non-empty sequences required")
    if np.allclose(a_arr, b_arr):
        return (0.0, 0.0, 0.0)
    d = float(np.mean(a_arr) - np.mean(b_arr))
    res = bootstrap((a_arr, b_arr), lambda x, y: np.mean(x) - np.mean(y),
                    paired=True, method="percentile",
                    rng=np.random.default_rng(rng), confidence_level=confidence,
                    n_resamples=n_resamples)
    return (d, float(res.confidence_interval.low), float(res.confidence_interval.high))


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    if k > n or k <= 0 or c < 0 or c > n or n <= 0:
        raise ValueError("invalid n,c,k")
    from math import comb
    if k > n - c:
        # C(n-c,k) = 0
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    if k > n or k <= 0 or c < 0 or c > n or n <= 0:
        raise ValueError("invalid n,c,k")
    from math import comb
    if k > c:
        return 0.0
    return comb(c, k) / comb(n, k)
