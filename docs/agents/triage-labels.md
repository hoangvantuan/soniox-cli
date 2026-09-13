# Triage Labels

Các skill nói theo 5 vai trò triage chuẩn. File này ánh xạ vai trò sang chuỗi label thật trong issue tracker của repo.

| Vai trò            | Label trong repo  | Nghĩa                                       | Đã tồn tại |
| ------------------ | ----------------- | ------------------------------------------- | ---------- |
| `needs-triage`     | `needs-triage`    | Maintainer cần đánh giá issue này            | chưa       |
| `needs-info`       | `needs-info`      | Đang chờ người báo cáo bổ sung thông tin     | chưa       |
| `ready-for-agent`  | `ready-for-agent` | Đã đặc tả đủ, agent chạy AFK được            | chưa       |
| `ready-for-human`  | `ready-for-human` | Cần người thật làm                           | chưa       |
| `wontfix`          | `wontfix`         | Sẽ không xử lý                               | **rồi**    |

Khi một skill nhắc tới vai trò (ví dụ "gắn label AFK-ready"), dùng chuỗi label ở cột thứ hai.

## Tạo 4 label còn thiếu

Repo hiện mới có bộ label mặc định của GitHub (`bug`, `documentation`, `duplicate`, `enhancement`, `good first issue`, `help wanted`, `invalid`, `question`, `wontfix`). Bốn label triage còn lại tạo bằng:

```bash
gh label create needs-triage    --description "Maintainer cần đánh giá"        --color FBCA04
gh label create needs-info      --description "Chờ người báo cáo bổ sung"      --color D4C5F9
gh label create ready-for-agent --description "Đặc tả đủ, agent chạy AFK được" --color 0E8A16
gh label create ready-for-human --description "Cần người thật làm"             --color 1D76DB
```

Kiểm tra lại: `gh label list`. Nếu một skill cần label chưa tồn tại, tạo nó trước rồi mới gắn, đừng gắn label khác thay thế.
