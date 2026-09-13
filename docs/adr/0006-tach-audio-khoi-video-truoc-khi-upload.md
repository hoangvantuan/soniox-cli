# ADR-0006: Tách audio khỏi video trước khi upload

**Trạng thái**: chấp nhận

## Bối cảnh

Soniox nhận cả container video (`mp4`, `webm`, `asf`), nên đưa thẳng file video vào `stt transcribe` vẫn chạy. Nhưng luồng hình thường chiếm phần lớn dung lượng và STT không dùng tới nó: upload nguyên video là trả tiền băng thông và thời gian cho dữ liệu bị vứt đi ngay khi tới nơi.

Để agent tự chạy `ffmpeg` rồi tự dọn file tạm là giao cho chỗ dễ quên nhất. Bước dọn dẹp là bước hay bị bỏ qua nhất khi có lỗi giữa chừng.

## Quyết định

`stt transcribe` và `files upload` tự tách audio trước khi upload, qua `media.prepared_upload()`:

1. Đuôi file chắc chắn là audio (`.mp3`, `.wav`, `.m4a`, ...) thì đi thẳng, **không gọi ffmpeg**.
2. Còn lại thì `ffprobe` xem có luồng hình thật không. Ảnh bìa (`mjpeg`, `png`, `bmp`) không tính là video.
3. Có luồng hình thì tách audio vào thư mục tạm của hệ thống, **xóa trong `finally`**.
4. Ưu tiên **copy nguyên luồng** (`-c:a copy`) khi codec nằm trong danh sách Soniox đọc được; codec lạ (`ac3`, `dts`, `wmav2`, ...) mới mã hóa lại sang AAC.

`--no-extract-audio` bỏ qua toàn bộ bước này. `--keep-extracted` giữ file tạm lại và in đường dẫn.

## Lý do

Đặt ở CLI chứ không ở skill vì đây là **sửa cấu trúc chứ không vá từng chỗ gọi**: người dùng terminal cũng được lợi, và việc dọn dẹp do `finally` bảo đảm thay vì trông vào agent nhớ làm.

Copy luồng thay vì mã hóa lại vì mục tiêu là **bỏ luồng hình**, không phải nén audio. Mã hóa lại vừa chậm vừa mất chất lượng, mà chất lượng audio ảnh hưởng trực tiếp tới độ chính xác STT.

## Đánh đổi

- Thêm phụ thuộc `ffmpeg`, nhưng chỉ khi đầu vào thật sự là video. File audio không bao giờ chạm tới nó. Thiếu ffmpeg thì báo lỗi kèm cách cài và kèm `--no-extract-audio`.
- `ffprobe` tốn thêm một lần gọi tiến trình cho file không rõ đuôi. Chấp nhận được vì đã lọc hết đuôi audio phổ biến ở bước 1.
- Nhận diện dựa vào `ffprobe`, không dựa vào đuôi file, nên `.mp4` chỉ có audio vẫn đi thẳng, và file đuôi lạ vẫn được xử lý đúng.

## Hệ quả

- URL thì không tách được (file nằm ở phía Soniox). Muốn tách phải tải về trước.
- `--keep-extracted` tạo file tạm mà CLI **không** tự dọn: đó là ý của cờ, và đường dẫn được in ra để người dùng tự xóa.
