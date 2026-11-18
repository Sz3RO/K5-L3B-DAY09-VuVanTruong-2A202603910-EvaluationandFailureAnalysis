# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case C-002@11 — ticket_trust (FM-03)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID `E-seeded_regression-20261118-df2c` |
| Triệu chứng | Grader `trial_pass` fail (`status resolved != denied`); reply báo hoàn `20.000đ` trong khi ledger không nên có refund; `refund_amount_correct` và `reply_matches_ledger` cũng fail |
| Bước sai đầu tiên | Event 3 `model_override` `{"delay_days": 5}` — ghi đè `delay_days` DB (2) bằng số trong ticket (5) |
| Vì sao là bước *đầu tiên* | Event 1 handoff và event 2 investigator đúng (order O-202, delay_days=2); event 4 quote chỉ là hệ quả của override; event 6 reply chỉ phản ánh proposal sai |
| Failure mode | FM-03 `ticket_trust` |
| Đối chứng | Cùng claim@seed trên `fixed`: không có event `model_override`; quote trả `0` (`no_entitlement`); status `denied`; ledger rỗng |
| Regression test | `tests/test_lab9_graders.py::test_override_event_breaks_db_fact` (DbFactKept) + metric `db_fact_kept` trong spec; đã thấy fail trên variant lỗi và pass trên `fixed` |
| Chưa chắc chắn | Trace không chứng minh được agent có *cố ý* tin ticket hay do prompt; chỉ chứng minh số ngày bị ghi đè |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
