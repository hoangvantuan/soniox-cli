# ADR-0005: Phụ đề bản dịch mượn mốc thời gian của nguyên bản

**Trạng thái**: chấp nhận

## Bối cảnh

Skill quảng cáo "tạo phụ đề" nhưng CLI chỉ in được text phẳng. Token của Soniox có `start_ms` / `end_ms` nên dựng SRT/VTT là làm được.

Khi bật `--translate`, kiểm tra trên dữ liệu thật cho thấy **token bản dịch có `start_ms = end_ms = 0`**, toàn bộ 97/97 token. Dùng thẳng thì mọi cue phụ đề dồn về giây 0, tức là vô dụng.

Token trả về theo **đoạn**: một đoạn nguyên bản có mốc thời gian, rồi ngay sau đó là đoạn bản dịch của chính khoảng đó, mốc 0, rồi lại đoạn nguyên bản tiếp theo.

## Quyết định

`normalize_tokens()` gán mốc cho token bản dịch bằng cách **mượn khoảng thời gian của đoạn nguyên bản liền trước**, rồi chia cho các token trong đoạn **theo tỉ lệ độ dài ký tự**.

Không có đoạn nguyên bản phía trước thì lấy đoạn phía sau. Không có đoạn nào thì để nguyên 0.

## Lý do

Chia theo tỉ lệ ký tự, thay vì gán cả đoạn cùng một mốc, để `build_cues` vẫn cắt được đoạn dài thành nhiều cue có mốc tăng dần. Nếu gán chung một mốc thì một câu dịch dài sẽ thành một cue duy nhất chạy suốt, đọc không kịp.

## Đánh đổi

Mốc thời gian trong cue bản dịch là **suy ra**, không phải đo. Độ dài ký tự không tỉ lệ chính xác với thời gian nói, nhất là giữa hai ngôn ngữ khác hệ chữ. Cue vẫn đúng **biên** của đoạn (đầu và cuối khớp nguyên bản), chỉ các mốc cắt bên trong là ước lượng.

Chấp nhận được vì phụ đề đọc theo đoạn, và biên đoạn mới là thứ phải khớp audio.

## Hệ quả

- `--subtitle-track` mặc định `auto`: có bản dịch thì lấy bản dịch, vì đó là thứ người ta cần khi làm phụ đề cho audio tiếng nước ngoài.
- `both` dựng hai luồng cue rồi trộn theo thời gian, giống cách output text đang xen kẽ gốc và bản dịch.
- Có test khóa lại: `test_phu_de_ban_dich_khong_con_nam_o_giay_0`.
