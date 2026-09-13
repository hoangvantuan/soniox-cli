# ADR-0008: Tín hiệu hủy không xóa dữ liệu từ xa

**Trạng thái**: chấp nhận. Sửa phần hành vi-khi-hủy của [ADR-0003](0003-transcribe-mac-dinh-tu-don.md).

## Bối cảnh

Một lần chạy thật: phiên âm 2h40 audio tách từ file video 993 MB. Tiến trình local bị giết trong lúc đang `stt.wait`. Dòng thời gian:

```
21:44   ffmpeg bắt đầu đọc 993 MB
21:47   tách xong, upload 147.8 MB
21:48   transcription được tạo trên Soniox
  ...   phiên trước kết thúc, tiến trình local bị giết
<=21:53 Soniox xử lý xong (2h40 audio trong dưới 5 phút)
21:53   phiên mới: `stt list` -> tìm lại id -> kéo transcript về
```

Chẩn đoán ban đầu đổ lỗi cho `--timeout`. Sai. Soniox xong trước cả lúc timeout thành vấn đề. Thứ giết lượt chạy là **vòng đời tiến trình local**, và thứ cứu được nó là **job vẫn còn nguyên trên Soniox**.

[ADR-0003](0003-transcribe-mac-dinh-tu-don.md) chốt rằng nắm được id là để dọn dẹp đáng tin, và liệt kê "Ctrl-C giữa chừng: tự destroy" là một trong ba tình huống cần id. ADR này **đảo ngược đúng dòng đó**. Phần còn lại của ADR-0003 (tự dọn sau khi phiên âm xong, tự tạo rồi tự chờ để nắm id) giữ nguyên.

Trước quyết định này, CLI coi mọi tín hiệu hủy là lệnh vứt dữ liệu:

- `Ctrl-C` gọi `_try_destroy`, xóa cả transcription lẫn file đã upload, trừ khi có `--keep`.
- `SIGTERM` thì Python kết thúc ngay, không chạy `finally`, nên file audio đã tách nằm lại trong temp vĩnh viễn.

Nếu cú giết lúc 21:48 là `Ctrl-C` thay vì `SIGTERM`, transcript đã bị xóa sạch và phải trả tiền phiên âm lại 2h40.

## Quyết định

**Không tín hiệu hủy nào được xóa dữ liệu trên Soniox.**

1. `Ctrl-C` in id kèm lệnh lấy kết quả và lệnh dọn, rồi thoát với code 130. Không gọi `_try_destroy` nữa.
2. `SIGTERM` được đổi thành `SystemExit(143)` qua `signal.signal`, để mọi khối `finally` được chạy: file tạm cục bộ **được dọn**, job từ xa **không bị chạm tới**.
3. Id của transcription được in ra stderr **ngay sau khi tạo**, vô điều kiện, kể cả trên đường hạnh phúc và kể cả khi có `--no-wait`.

Auto-destroy chỉ còn xảy ra ở hai chỗ có ý định rõ ràng: phiên âm **xong xuôi** (hành vi mặc định của `transcribe`), và job **lỗi** (không còn gì để cứu).

## Lý do

**Hủy chờ khác hủy job.** `Ctrl-C` và `SIGTERM` chỉ diễn đạt được ý thứ nhất: người dùng thôi đứng đợi, hoặc harness dọn tiến trình. Không tín hiệu nào mang nghĩa "vứt dữ liệu đi". Suy ra ý thứ hai từ ý thứ nhất là CLI tự đoán thay người dùng, đúng thứ [AGENTS.md](../../AGENTS.md) cấm.

**Đánh đổi không đối xứng.** Rác quota dọn bằng một lệnh (`stt delete-all --destroy --yes`), và SDK ghi rõ *"Transcriptions are automatically deleted 30 days after creation"*, nên nó còn tự lành. Transcript đã xóa thì không bao giờ lành: phải upload lại và trả tiền phiên âm lại.

**Id phải là dữ kiện, không phải artifact của nhánh lỗi.** Trước đây id chỉ xuất hiện trong handler `TimeoutError` và `KeyboardInterrupt`. `SIGKILL`, mất điện, harness teardown không chạy nhánh `except` nào cả. In id ngay lúc nó tồn tại là chỗ duy nhất chắc chắn được chạy, và phủ được cả lớp sự cố mà không handler nào bắt nổi.

## Đánh đổi

- **Quota bẩn hơn.** Ai `Ctrl-C` rồi bỏ đi sẽ để lại job và file trên Soniox. Chấp nhận: xem lý do bất đối xứng ở trên. `stt list` giờ in thêm `created_at` và thời lượng để nhận ra job cũ.
- **`--keep` hẹp nghĩa lại.** Nó chỉ còn chi phối đường hạnh phúc và đường lỗi, không còn chi phối đường hủy nữa.
- **Thêm một `eprint` trên mọi lần chạy.** Một dòng stderr cho mỗi lần `transcribe`. Đổi lại là không bao giờ mất id. Đáng.
- **`SIGKILL` vẫn không cứu được file tạm.** Không tiến trình nào bắt được `SIGKILL`. Đó là lý do `--ref` (`client_reference_id`) tồn tại: nó gắn nhãn cho **cả file lẫn transcription** ngay từ lúc tạo, nên tìm lại được kể cả khi bị giết giữa lúc upload, lúc mà id còn chưa kịp tồn tại.
