# Issue tracker: GitHub

Issue và spec của repo này nằm ở GitHub Issues của `hoangvantuan/soniox-cli`. Mọi thao tác dùng `gh` CLI, nó tự suy ra repo khi chạy trong bản clone.

## Quy ước

- **Tạo issue**: `gh issue create --title "..." --body "..."`. Body nhiều dòng thì dùng heredoc.
- **Đọc issue**: `gh issue view <number> --comments`.
- **Liệt kê**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`, thêm `--label` / `--state` để lọc.
- **Bình luận**: `gh issue comment <number> --body "..."`
- **Gắn / gỡ label**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`. Label chưa tồn tại thì tạo trước, xem [`triage-labels.md`](triage-labels.md).
- **Đóng**: `gh issue close <number> --comment "..."`

## PR có phải bề mặt tiếp nhận yêu cầu không

**Không.** Repo này không coi PR từ bên ngoài là feature request. `/triage` đọc cờ này và sẽ bỏ qua PR.

Nếu về sau đổi ý, sửa dòng trên thành "Có" và dùng các lệnh `gh pr` tương đương: `gh pr view <n> --comments`, `gh pr diff <n>`, `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments` rồi giữ lại `authorAssociation` là `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR` hoặc `NONE`.

GitHub dùng chung một dải số cho issue và PR, nên `#42` trần có thể là một trong hai: thử `gh pr view 42` trước, không được thì `gh issue view 42`.

## Khi một skill nói "publish lên issue tracker"

Tạo một GitHub issue.

## Khi một skill nói "lấy ticket liên quan"

`gh issue view <number> --comments`.

## Thao tác wayfinding

Dùng bởi `/wayfinder`. **Map** là một issue duy nhất, **ticket** là các issue con.

- **Map**: issue gắn label `wayfinder:map`, thân chứa Notes / Decisions-so-far / Fog. `gh issue create --label wayfinder:map`.
- **Ticket con**: issue liên kết với map dưới dạng GitHub sub-issue (`gh api` vào endpoint sub-issues). Nơi chưa bật sub-issue thì thêm ticket vào task list trong thân map và đặt `Part of #<map>` ở đầu thân ticket. Label: `wayfinder:<type>` (`research` / `prototype` / `grilling` / `task`). Khi đã nhận thì gán cho người đang làm.
- **Chặn**: dùng **issue dependencies** gốc của GitHub, đây là biểu diễn chuẩn và hiện trên UI. Thêm cạnh bằng `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, trong đó `<blocker-db-id>` là **database id** dạng số của blocker (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, **không phải** `#number` hay `node_id`). GitHub trả `issue_dependencies_summary.blocked_by` (chỉ đếm blocker còn mở, đây là cổng chặn thật). Nơi chưa có dependencies thì lùi về một dòng `Blocked by: #<n>, #<n>` ở đầu thân ticket. Ticket hết chặn khi mọi blocker đã đóng.
- **Truy vấn frontier**: liệt kê issue con còn mở của map (`gh issue list --state open`, giới hạn trong sub-issue / task list của map), bỏ cái nào còn blocker mở (`issue_dependencies_summary.blocked_by > 0`, hoặc còn issue mở trong dòng `Blocked by`) hoặc đã có người nhận; cái đứng trước trong map thắng.
- **Nhận việc**: `gh issue edit <n> --add-assignee @me`, đây là thao tác ghi đầu tiên của phiên.
- **Chốt**: `gh issue comment <n> --body "<câu trả lời>"`, rồi `gh issue close <n>`, rồi nối một con trỏ ngữ cảnh (gist kèm link) vào mục Decisions-so-far của map.
