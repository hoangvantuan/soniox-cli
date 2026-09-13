# Domain Docs

Cách các skill kỹ thuật đọc tài liệu domain của repo này khi khám phá codebase.

## Trước khi khám phá, đọc các file này

- **[`CONTEXT.md`](../../CONTEXT.md)** ở gốc repo: bảng thuật ngữ và ranh giới của CLI.
- **[`docs/adr/`](../adr/)**: các quyết định kiến trúc đã chốt. Đọc ADR chạm tới vùng bạn sắp sửa.

Repo này là **single-context**: một `CONTEXT.md` duy nhất ở gốc, không có `CONTEXT-MAP.md`. Nếu về sau tách nhiều context thì mới thêm `CONTEXT-MAP.md` trỏ tới từng `CONTEXT.md` con.

## Cấu trúc

```
/
├── CONTEXT.md                          ← bảng thuật ngữ, ranh giới
├── docs/adr/
│   ├── 0001-khong-boc-realtime-streaming.md
│   ├── 0002-raw-request-cho-tts-voices-usage.md
│   ├── 0003-transcribe-mac-dinh-tu-don.md
│   └── 0004-loc-config-json-bat-doi-xung.md
└── src/soniox_cli/
```

## Dùng đúng từ vựng trong bảng thuật ngữ

Khi output của bạn gọi tên một khái niệm domain (tiêu đề issue, đề xuất refactor, giả thuyết, tên test), dùng đúng thuật ngữ như `CONTEXT.md` định nghĩa. Đừng trôi sang từ đồng nghĩa mà bảng thuật ngữ đã chủ động tránh: ví dụ phân biệt rõ **delete** (chỉ xóa transcription) với **destroy** (xóa cả file đính kèm), đừng gộp cả hai thành "xóa".

Nếu khái niệm bạn cần chưa có trong bảng thuật ngữ, đó là tín hiệu: hoặc bạn đang bịa ra ngôn ngữ mà dự án không dùng (xem lại), hoặc có khoảng trống thật (ghi lại cho `/domain-modeling`).

## Nêu rõ khi mâu thuẫn với ADR

Nếu output của bạn đi ngược một ADR đang có, nói thẳng ra thay vì lặng lẽ ghi đè:

> _Trái với ADR-0002 (raw request cho TTS/voices/usage-logs), nhưng đáng mở lại vì…_
