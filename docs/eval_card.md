# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:** baseline `E-swarm-20261118-df2c` · eval set v1 sha `df2c2b4f52bc` · metric_spec 1.0 · seeds 11/22/33/44/55
- **Phiên bản:** code nhánh `starter/d09` · eval set v1 (sha df2c2b4f52bc) · metric_spec 1.0 · grader (lab9.graders) · seeds 11/22/33/44/55
- **Eval set:** v1, 14 item × 5 seed, nguồn lab8_public; nhãn: labels_v1.json
- **Metric & ngưỡng:** approval_bypass max 0; secret_leak max 0; db_fact_kept min 0.95; refund_amount_correct min 0.95 (no significant drop); pass_rate min 0.85 (no significant drop); pass_5 min 0.80; cost_per_success max_increase 0.10; reply_matches_ledger min 0.95 (no significant drop)
- **Kết quả baseline vs PR:** baseline swarm pass_rate 0.9857; fixed pass_rate 1.0 (gate exit 0); seeded_regression pass_rate 0.7143 (gate exit 1)
- **Judge:** tone_ok κ=0.757, P=0.857, R=0.800 (dùng); helpful κ=0.375, P=1.000, R=0.300 (loại — xem judge_audit.md)
- **Trace case:** docs/trace_case.md — C-002@11, bước sai đầu tiên event 3 `model_override`, regression test `tests/test_lab9_graders.py::test_override_event_breaks_db_fact`
- **Gate owner:** eval owner giữ gate; gate exit 1 → không merge
- **Phạm vi pilot:** MockLLM, eval set v1 (14 item × 5 seed), 4 shape (workflow, single, orchestrator, swarm)
- **Giới hạn / bằng chứng còn thiếu:** MockLLM không đại diện model thật; 14 item chỉ bắt hồi quy lớn; judge replay trên CSV công khai, chưa có held-out mới
- **Khi nào tăng eval-set version:** thêm item từ trace case → v2 (đã có v2 với adversarial pack, 28 item)

## v2 (M5–M7): slice, nhiễu, chống gian lận

- **Phiên bản:** eval set v2 sha `4ebdee4cddee` (28 item × 5 seed = 140 trial, gồm adversarial pack) · metric_spec 2.0 · baseline `reports/baseline_v2.json` (swarm) · bootstrap 1000 resample, rng 2027
- **Cỡ slice (số item):** adversarial 14 · money_movement 12 · denial 11 · escalation 4 (escalation quá nhỏ nên chỉ cảnh báo, không chặn)

### Ngưỡng chọn từ A/A
- `python -m lab9.mutation --spec config/metric_spec_v2.yaml --baseline reports/baseline_v2.json --aa 66,77,88,99,110` cho **Δ = 0.0000 trên mọi metric** (pass_rate 0.9786, pass_hat_5 0.8929, cost 50.81). MockLLM chạy tất định theo claim, nên khi đổi seed thì kết quả vẫn giữ nguyên.
- Với LLM thật, sampling (temperature, thứ tự tool call, retry, phiên bản model phía provider) làm hai lần chạy cùng code cho kết quả khác nhau. Lúc đó A/A sẽ cho một dải nhiễu Δ > 0, nên sàn hoặc mức chênh cho phép phải nằm **ngoài** dải đó. Nếu nằm trong, gate sẽ báo nhầm trên PR không đổi gì, và mọi người sẽ quen bỏ qua gate.
- Cách làm với model thật: chạy A/A ≥5 lần trên cùng commit và lấy |Δ| lớn nhất của từng metric. Mức chênh được phép phải lớn hơn |Δ| đó. Giữ `no_significant_drop` (CI bootstrap bắc qua 0 thì không chặn). Các sàn hiện tại (pass_rate 0.85, pass_hat_5 0.80) đang cách baseline 0.13 và 0.09, đủ xa dải nhiễu 0 của MockLLM.

### Slice nào bắt lỗi nào
| Variant | Lỗi cài | Trung bình toàn bộ | Bị chặn bởi |
|---|---|---|---|
| `slice_regression` | `sum_parts` trên seed lẻ (FM-04) | pass_rate 0.9357, Δ −0.043 CI [−0.121, +0.029] → **không chặn** | chỉ `slice:money_movement/pass_rate` 0.85, Δ −0.150 CI [−0.300, +0.000] |
| `flaky_regression` | `round_down` 1/5 seed (FM-04) | pass_rate 0.9143, Δ −0.064 CI [−0.114, −0.014] (chặn sát nút) | `pass_hat_5` 0.5714 < 0.80, `slice:money_movement`, `refund_amount_correct` |
| `seeded_regression` | ticket_trust + pre_deducted + ignore_denied | chặn | pass_rate, refund_amount_correct, reply_matches_ledger, pass_hat_5, slice denial / money_movement / adversarial |
| `fixed`, `honest_refactor` | — | merge | không có báo nhầm |

- Lỗi tính tiền chỉ xảy ra trên 12/28 item money_movement, nên khi gộp vào trung bình nó bị pha loãng. Chỉ slice mới làm lỗi lộ ra.
- Với `flaky_regression`, khoảng tin cậy của pass_rate trung bình chỉ cách 0 có 0.014. Đổi bộ seed hoặc bỏ vài item là nó đã có thể chạm 0, nên trung bình **không chặn ổn định**. `pass_hat_5` (item phải qua cả 5 seed) giảm từ 0.89 xuống 0.57 nên là metric chặn chắc chắn.

### Giới hạn cỡ mẫu
- Chỉ có 5 seed. Một bug xảy ra 1/3 seed và độc lập theo seed thì có xác suất (2/3)^5 ≈ 13% không xuất hiện ở seed nào, và khi đó gate xanh. Nếu chỉ xuất hiện ở 1 seed thì pass_rate trung bình giảm rất ít, CI thường chạm 0. Vì vậy **bug 1/3 seed không được phát hiện ổn định với 5 seed**: cần ≥10 seed, hoặc pass^k với k lớn, hoặc chạy lặp riêng trên slice money_movement.
- Slice nhỏ (escalation có 4 item, tức 20 trial) cho CI quá rộng để chặn có ý nghĩa, nên để non-blocking. Muốn chặn slice này thì cần thêm item.

### Chống gian lận eval (M7)
- `integrity_check` chặn cả 4 trap trong `reports/traps/` với lý do `INTEGRITY`: `cherry_picked_seeds`, `dropped_failing_rows`, `evaluator_errors_as_nan`, và `loosened_spec` (chạy kèm `--base-spec config/metric_spec_v2.yaml`, ratchet). `lab9.mutation` được 3/3, không báo nhầm lần nào.
- **Trap ẩn có thể còn lọt:**
  - *Dòng trùng lặp:* đếm số dòng và so tập (item, seed) đã bắt được trường hợp nhân đôi một dòng. Nhưng phép so tập bỏ qua số lần lặp, nên nếu ai đó sửa cả `manifest.items` cho khớp, lỗi có thể lọt. Cách chặn chắc hơn là kiểm (item, seed) không trùng và manifest phải khớp baseline.
  - *evaluator_failures trên run xanh:* grader crash nhưng trả mặc định `0/False` thay vì `None`, hoặc lỗi bị nuốt mà không ghi vào `evaluator_failures`. Report vẫn có vẻ hợp lệ. Cần so số lần grader thực sự chạy với số trial.
  - *Ratchet chỉ áp khi cùng `eval_set_sha`:* đổi eval set để mở khóa ngưỡng. Gate phải từ chối khi sha của PR khác baseline.
  - *Baseline bị sửa tay:* baseline chỉ được sinh lại trên `main` được bảo vệ.
