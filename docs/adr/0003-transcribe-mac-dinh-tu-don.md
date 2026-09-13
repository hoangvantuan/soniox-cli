# ADR-0003: `stt transcribe` mặc định tự dọn dữ liệu trên Soniox

**Trạng thái**: chấp nhận

## Bối cảnh

Mỗi lần phiên âm để lại **hai** thứ trên Soniox: một transcription và một file đã upload. Cả hai đều tính vào quota. Người dùng terminal và agent hầu như chỉ cần text rồi thôi.

## Quyết định

`stt transcribe` mặc định **destroy** cả transcription lẫn file sau khi lấy được transcript. Muốn giữ thì thêm `--keep`.

CLI tự tạo rồi tự chờ (`transcribe` cộng `wait`) thay vì gọi `transcribe_and_wait_with_tokens` của SDK, để **luôn nắm được id**.

## Lý do

Mặc định an toàn là mặc định không âm thầm làm đầy quota của người khác. Người muốn giữ lại biết mình muốn gì và gõ thêm được một cờ; người không biết thì không nên bị phạt.

Nắm được id là điều kiện để dọn dẹp đáng tin. Ba tình huống đều cần nó:

- hết `--timeout`: in id kèm lệnh lấy lại kết quả và lệnh dọn tay
- Ctrl-C giữa chừng: tự destroy, không bỏ mồ côi dữ liệu
- `status == "error"`: báo `error_message` rõ ràng rồi dọn

Dùng helper của SDK thì id nằm trong bụng nó, mất sạch ba đường trên.

## Đánh đổi

Tự viết vòng chờ nghĩa là phải tự bảo trì nó khi SDK đổi. Đổi lại là không bao giờ bỏ rác trên tài khoản người dùng. Đánh đổi này chấp nhận được vì vòng chờ chỉ là `transcribe` cộng `wait`, cả hai đều có từ 2.3.2.
