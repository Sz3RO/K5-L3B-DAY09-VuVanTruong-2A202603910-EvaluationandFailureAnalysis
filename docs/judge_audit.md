# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | có | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | không (κ<0.6, R<0.7) | loại |

Ma trận nhầm lẫn (lớp dương = FAIL):
- tone_ok: TP 24 · FP 4 · FN 6 · TN 66. Tỉ lệ FAIL quan sát 0.28, sau Rogan-Gladen là 0.30.
- helpful: TP 9 · FP 0 · FN 21 · TN 70. Tỉ lệ FAIL quan sát 0.09, sau Rogan-Gladen là 0.30. Judge bỏ sót 21/30 reply hỏng.

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú: lỗi và cách sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 tone | PASS | FAIL | người | Xưng "em" kèm "nha" là quá suồng sã với khách khiếu nại, nhưng judge coi là thân thiện. **Sửa rubric:** bắt buộc xưng "LogiX"/"anh/chị" và cấm "em… nha"; thêm H-008 làm ví dụ FAIL. |
| 2 | H-017 tone | PASS | FAIL | người | Gọi khách là "bạn ơi" là sai cách xưng hô. **Sửa rubric:** đưa vào cùng quy tắc xưng hô như case 1, liệt kê "bạn", "bạn ơi" là FAIL. |
| 3 | H-029 tone | PASS | FAIL | người | "không cần nhắn thêm" là giọng ra lệnh, judge chỉ nhìn thấy "Dạ, vui lòng". **Sửa rubric:** chấm cả câu chứ không chấm từ mở đầu; câu mệnh lệnh hoặc chặn khách liên hệ là FAIL dù mở bằng "Dạ". |
| 4 | H-042 tone | FAIL | PASS | người | Ngắn nhưng đủ ý, judge phạt vì thiếu lời xin lỗi. **Sửa rubric:** ghi rõ không bắt buộc xin lỗi khi đã hoàn tiền đúng; độ ngắn không phải lỗi giọng. |
| 5 | H-051 tone | FAIL | PASS | người | Từ "refund" được CS LogiX cho phép, judge phạt vì là tiếng Anh. **Sửa rubric:** thêm danh sách thuật ngữ được phép (refund, ship, COD). |
| 6 | H-070 tone | PASS | FAIL | người | Dùng emoji 😂 trong ngữ cảnh khiếu nại. **Sửa rubric:** emoji trong reply khiếu nại là FAIL. |
| 7 | H-081 tone | FAIL | PASS | **judge** | Nhãn người sai vì đọc nhầm ticket; reply từ chối đúng chính sách. **Hành động:** sửa nhãn người thành FAIL trong bộ nhãn, không sửa rubric. |
| 8 | HL-015 helpful | PASS | FAIL | người | Reply báo hoàn 55.000đ nhưng ledger ghi 40.000đ. Judge không thấy ledger nên không thể biết. **Hành động:** bỏ "đúng số tiền" khỏi rubric helpful và chấm bằng code (`reply_matches_ledger`, FM-08). |
| 9 | HL-016 / HL-035 helpful | PASS | FAIL | người | Reply dài, xin lỗi nhiều lần nên judge cho PASS, nhưng số tiền vẫn sai so với ledger (35.000đ). **Sửa rubric:** độ dài và lời xin lỗi không cộng điểm helpful; tiền chấm bằng code như case 8. |

## Kết luận
- **Tiêu chí bị loại: `helpful`.** κ = 0.375 và recall = 0.300 (FN 21/30), nên judge bỏ sót phần lớn reply hỏng. 18/21 FN có `human_failure = sai tiền` (3 FN còn lại là sai xưng hô). Judge chỉ đọc reply, không thấy ledger, và còn bị đánh lừa bởi reply dài, xin lỗi nhiều. Vì vậy không thể dùng judge này làm gate: gate sẽ cho qua đúng loại lỗi nguy hiểm nhất (FM-08, sai tiền). Precision = 1.0 không cứu được, vì gate cần bắt được lỗi chứ không chỉ cần không báo nhầm. Tiền và approval luôn chấm bằng code.
- **`tone_ok` được dùng** (đạt FLOORS). Các bất đồng còn lại tập trung ở xưng hô, câu mệnh lệnh và emoji. Rubric bổ sung ở trên cần được calibrate lại trên nhãn mới trước khi nâng sàn.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật.
