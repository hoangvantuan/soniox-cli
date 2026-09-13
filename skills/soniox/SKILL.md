---
name: soniox
description: >-
  Speech-to-Text và Text-to-Speech cho FILE AUDIO BẤT KỲ qua Soniox, dùng CLI
  `soniox`. Kích hoạt khi cần: phiên âm / bóc băng / chuyển audio thành text
  ("transcribe", "phiên âm", "bóc băng", "audio thành text", "tạo phụ đề",
  "chuyển ghi âm thành chữ"); tách người nói (diarization); dịch nội dung audio
  sang ngôn ngữ khác; sinh giọng nói / đọc văn bản thành tiếng ("text to speech",
  "TTS", "đọc thành giọng nói", "tạo file audio từ text"); clone giọng nói
  (voice cloning); hoặc khi nhắc thẳng "soniox". KHÁC youtube-transcript (chỉ
  lấy phụ đề có sẵn của YouTube) — skill này xử lý FILE audio/URL bất kỳ bằng
  mô hình STT/TTS của Soniox. KHÔNG dùng cho realtime streaming micro.
---

# Soniox CLI

CLI `soniox` bọc Soniox SDK cho STT / TTS / Files / Voice cloning. Chạy local, xử lý file audio local trực tiếp.

## Thiết lập (làm 1 lần)

```bash
soniox auth check
```

- Nếu lệnh `soniox` không tồn tại: cài từ repo — `cd <repo soniox-cli> && uv tool install .`
  (repo thường ở `~/Desktop/PERSONAL/soniox-mcp`). Sau khi sửa code: `uv tool install . --reinstall --no-cache`.
- Nếu báo thiếu key: cần `export SONIOX_API_KEY=<key>` (lấy tại https://console.soniox.com).

## Bảng lệnh

| Lệnh | Việc |
|---|---|
| `soniox stt transcribe <file\|url>` | Phiên âm. Mặc định **chờ xong + in text + tự dọn** khỏi Soniox |
| `soniox stt transcribe <x> --no-wait` | Trả `id` ngay (job dài); poll sau |
| `soniox stt get\|transcript\|list\|delete <id>` | Quản lý transcription |
| `soniox files upload\|list\|get\|delete` | File audio đã upload |
| `soniox tts generate "<text>" -o out.wav` | Text → file audio |
| `soniox voices list\|create\|delete` | Voice cloning |
| `soniox models [--tts]` · `usage` · `auth check` | Metadata |

Thêm `--json` vào bất kỳ lệnh nào để lấy JSON đầy đủ (token-level: timestamp, speaker, confidence, language).

## Ví dụ hay dùng

```bash
# Phiên âm file local, lấy text (tự xóa khỏi Soniox sau khi xong)
soniox stt transcribe ghiam.mp3

# Tách người nói + gợi ý ngôn ngữ (kết quả in theo "Speaker 1: ...")
soniox stt transcribe hop.mp3 --diarize --language-hints vi,en

# Dịch audio sang tiếng Việt (in xen kẽ gốc và "→ vi: ...")
soniox stt transcribe english.mp3 --translate vi
# Dịch hai chiều
soniox stt transcribe call.mp3 --translate two-way:en,vi

# Job dài: không chờ
id=$(soniox stt transcribe long.mp3 --no-wait --json | jq -r .id)
soniox stt transcript "$id"          # khi status=completed

# Text-to-Speech
soniox tts generate "Xin chào" -o hello.mp3 --language vi --speed 1.1
echo "Đoạn dài..." | soniox tts generate -o out.wav --language vi   # đọc từ stdin

# Voice cloning: tạo giọng từ clip mẫu rồi dùng khi generate
soniox voices create mau.wav --name giong_toi
soniox tts generate "Thử giọng" -o thu.mp3 --voice <voice_id> --language vi
```

## Lưu ý quan trọng

- **Auto-destroy**: `transcribe` mặc định xóa file + transcription khỏi Soniox sau khi lấy text (tránh đầy quota). Dùng `--keep` nếu cần `get`/`transcript` lại sau.
- **Đầu vào STT**: đường dẫn file local, URL công khai, hoặc `--file-id` (file đã upload). SDK tự upload file local.
- **TTS**: bắt buộc `-o <file>`; định dạng suy từ đuôi file (`.wav`, `.mp3`, `.flac`, `.opus`, `.aac`). `--speed` 0.7–1.3.
- **Tham số hiếm**: STT dùng `--config-json '{...}'`, TTS cũng có `--config-json`.
- **Lỗi**: ra stderr, exit code ≠ 0. Đọc thông báo (kèm `request_id`) để chẩn đoán.

## Khi cần chi tiết vượt CLI

Danh sách ngôn ngữ hỗ trợ, giải thích tham số, giới hạn quota... → **WebFetch** docs Soniox:
`https://soniox.com/docs/stt/concepts/supported-languages`, `https://soniox.com/docs/sdk/python-SDK`,
`https://soniox.com/docs/api-reference`. Dữ liệu động (model, voice) lấy thẳng: `soniox models`, `soniox voices list`.
