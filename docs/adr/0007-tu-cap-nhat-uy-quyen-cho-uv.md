# ADR-0007: `soniox update` ủy quyền cho trình quản lý gói

**Trạng thái**: chấp nhận

## Bối cảnh

CLI cài bằng `uv tool install`. Người dùng (và agent) cần biết mình có đang chạy bản cũ không, và cập nhật mà không phải nhớ lệnh cài ban đầu.

Kiểm chứng trên máy thật: `uv tool upgrade soniox-cli` với nguồn git báo `Nothing to upgrade` khi số version không đổi, dù nhánh đã có commit mới. Phải có `--reinstall` (kéo theo `--refresh`) mới lấy lại từ git.

`uv-receipt.toml` trong `sys.prefix` ghi rõ nguồn cài: `git = "..."` hay `directory = "..."`.

## Quyết định

`soniox update` **không tự tải và ghi đè thư mục cài của chính mình**. Nó:

1. Đọc `uv-receipt.toml` để biết được cài thế nào.
2. So version hiện tại với `__version__` trên nhánh `main` của GitHub.
3. Nguồn git thì chạy `uv tool upgrade soniox-cli --reinstall`. Nguồn khác thì **dừng lại và in hướng dẫn**.

## Lý do

Một CLI tự ghi đè file của chính nó trong lúc đang chạy là nguồn lỗi kinh điển: hỏng nửa chừng thì không còn gì để chạy lại. Trình quản lý gói đã giải quyết việc này (cài ra môi trường mới rồi mới đổi chỗ), nên việc đúng là ủy quyền chứ không viết lại.

Dừng lại thay vì đoán khi không nhận ra cách cài: chạy `uv` lên một bản cài bằng `pipx` hay `pip -e` sẽ làm hỏng thứ người dùng đang có.

## Đánh đổi

- `--check` cần mạng và phụ thuộc vào GitHub còn sống. Đây là thao tác chỉ đọc, và `--no-check` bỏ qua được.
- So version theo `__version__` trên `main`, không theo tag. Nghĩa là commit lên `main` mà quên bump version thì `--check` báo "đã mới nhất" dù mã đã khác. Chấp nhận được vì `--force` luôn cài lại được.
- Nguồn thư mục local không tự cập nhật: CLI không tự chạy `git pull` trên repo của người dùng. Nó in lệnh ra để người dùng tự quyết.
