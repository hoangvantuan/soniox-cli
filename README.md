# soniox-cli

[![CI](https://github.com/hoangvantuan/soniox-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/hoangvantuan/soniox-cli/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CLI bọc [Soniox Python SDK](https://soniox.com/docs/sdk/python-SDK) cho **Speech-to-Text**, **Text-to-Speech**, **Files** và **Voice cloning**. Thiết kế để agent (Claude qua skill) gọi qua shell, đồng thời tiện cho người dùng terminal.

> Chỉ bọc phần **request/response** của SDK. **Không** bọc realtime streaming (WebSocket STT/TTS) vì luồng audio liên tục không hợp mô hình một-lệnh-một-kết-quả.

## Cài đặt

```bash
uv tool install git+https://github.com/hoangvantuan/soniox-cli

export SONIOX_API_KEY=<key>   # lấy tại https://console.soniox.com
soniox auth check             # xác nhận key hợp lệ
```

Cài từ bản clone local:

```bash
git clone https://github.com/hoangvantuan/soniox-cli && cd soniox-cli
uv tool install .
```

> Sau khi sửa code: `uv tool install . --reinstall --no-cache` (version không đổi nên `uv` sẽ dùng lại build cache cũ nếu thiếu `--no-cache`).

Gỡ: `uv tool uninstall soniox-cli`

## Biến môi trường

| Biến | Bắt buộc | Việc |
|---|---|---|
| `SONIOX_API_KEY` | có | API key |
| `SONIOX_API_BASE_URL` | không | endpoint REST theo vùng (data residency), mặc định `https://api.soniox.com/v1` |
| `SONIOX_TTS_API_BASE_URL` | không | endpoint TTS theo vùng, mặc định `https://tts-rt.soniox.com` |

## Lệnh chính

| Lệnh | Việc |
|---|---|
| `soniox stt transcribe <file\|url>` | Phiên âm; mặc định **chờ xong + tự dọn** file/transcription trên Soniox |
| `soniox stt transcribe <x> --subtitles srt` | Xuất **phụ đề SRT / VTT** |
| `soniox stt get\|list\|transcript\|count\|delete\|delete-all` | Quản lý transcription |
| `soniox files upload\|list\|get\|count\|delete\|delete-all` | File audio đã upload |
| `soniox tts generate "<text>" -o out.wav` | Sinh giọng nói ra file |
| `soniox voices list\|get\|create\|count\|recompute\|delete` | Voice cloning |
| `soniox models [--tts]` · `soniox usage` · `soniox concurrency` · `soniox auth check` | Metadata |
| `soniox --version` · `soniox --help` | Thông tin CLI |

`stt list` và `files list` nhận `--all` để phân trang lấy hết thay vì dừng ở `--limit`.

Thêm `--json` để lấy JSON đầy đủ (token-level: timestamp, speaker, confidence...). Đặt được ở cả hai vị trí: `soniox --json stt list` và `soniox stt list --json`.

## Ví dụ

```bash
# Phiên âm 1 file local, in text thuần (tự xóa khỏi Soniox sau khi xong)
soniox stt transcribe hop.mp3

# Tách người nói + gợi ý ngôn ngữ
soniox stt transcribe hop.mp3 --diarize --language-hints vi,en

# Dịch audio sang tiếng Anh
soniox stt transcribe bai.mp3 --translate en

# Phiên âm từ URL công khai, lấy token-level JSON
soniox stt transcribe https://soniox.com/media/examples/coffee_shop.mp3 --json

# Không chờ (job dài): trả id để poll sau
soniox stt transcribe long.mp3 --no-wait
soniox stt transcript <id>

# Phụ đề SRT, tách người nói
soniox stt transcribe hop.mp3 --diarize --subtitles srt -o hop.srt

# Phụ đề WebVTT tiếng Việt cho audio tiếng Anh (auto lấy bản dịch)
soniox stt transcribe english.mp3 --translate vi --subtitles vtt -o english.vtt

# Phụ đề song ngữ
soniox stt transcribe english.mp3 --translate vi --subtitles srt --subtitle-track both

# Text-to-Speech
soniox tts generate "Xin chào từ Soniox" -o hello.mp3 --language vi --speed 1.1
echo "Đoạn văn dài..." | soniox tts generate -o out.wav --language vi

# Quản lý quota
soniox stt count && soniox files count
soniox stt delete-all --destroy --yes     # dọn sạch khi đã lỡ đầy
soniox usage                              # chi phí 24h gần nhất, gộp theo model
soniox concurrency                        # phiên đồng thời và giới hạn
```

## Phụ đề

`--subtitles srt|vtt` có ở cả `stt transcribe` và `stt transcript`. Token của Soniox nhỏ hơn từ nên CLI gom lại thành **cue**, cắt khi đổi người nói, quá `--subtitle-max-chars` (mặc định 84), quá 6 giây, im lặng quá 0.7 giây, hoặc hết câu.

`--subtitle-track` chọn luồng khi có bản dịch:

| Giá trị | Việc |
|---|---|
| `auto` (mặc định) | Có bản dịch thì lấy bản dịch, không thì lấy nguyên bản |
| `original` | Chỉ nguyên bản |
| `translation` | Chỉ bản dịch |
| `both` | Cả hai, trộn theo thứ tự thời gian |

Soniox trả token bản dịch **không kèm mốc thời gian**; CLI mượn khoảng thời gian của đoạn nguyên bản tương ứng rồi chia theo độ dài ký tự. Chi tiết và đánh đổi: [ADR-0005](docs/adr/0005-phu-de-muon-moc-thoi-gian-ban-dich.md).

`--subtitles` không dùng chung với `--no-wait` (chưa có transcript thì chưa dựng được phụ đề).

## Hành vi đáng lưu ý

- **`transcribe` mặc định tự dọn** (`destroy`) file + transcription sau khi lấy transcript, tránh đầy quota Soniox. Dùng `--keep` để giữ lại (khi cần `get`/`transcript` sau).
  - Hết `--timeout` (mặc định 600s): CLI in ra id kèm lệnh để lấy kết quả hoặc dọn thủ công.
  - Ctrl-C giữa chừng: CLI tự dọn transcription vừa tạo (trừ khi có `--keep`), không bỏ mồ côi dữ liệu trên Soniox.
- **Định dạng TTS** suy từ đuôi `-o`: `.wav`, `.mp3`, `.flac`, `.opus`, `.aac`, `.pcm`. Đuôi lạ sẽ báo lỗi chứ không âm thầm ghi byte WAV vào file sai đuôi; muốn ép thì dùng `--format`.
- **`--speed`** trong khoảng 0.7 đến 1.3, kiểm tra ngay phía client.
- **Tham số ít dùng**: truyền qua `--config-json '{...}'`.
  - STT gộp vào `CreateTranscriptionConfig`; tên trường sai sẽ **báo lỗi kèm danh sách trường hợp lệ** thay vì bị pydantic bỏ im lặng.
  - TTS gộp thẳng vào payload gửi API, không lọc: trường mà API đã hỗ trợ nhưng SDK bản đang cài chưa biết vẫn dùng được.
- **Đầu vào STT là file local, `--file-id`, hoặc URL tải trực tiếp file audio.** Link trang web (YouTube, Drive share, ...) sẽ hỏng: Soniox tải URL đó về và nhận được HTML chứ không phải audio. Tải file về trước rồi đưa đường dẫn local.
- **Xóa hàng loạt bắt buộc `--yes`.** `stt delete-all` và `files delete-all` không hỏi tương tác (để agent gọi được an toàn); thiếu `--yes` thì chúng báo số lượng sẽ xóa rồi dừng.
- **Lỗi** ra stderr, exit code khác 0. Ctrl-C thoát với code 130.

## Kiến trúc

- STT / Files / models / tts-models dùng thẳng `soniox` SDK.
- **Phụ đề** nằm trong `src/soniox_cli/subtitles.py`, thuần logic và không chạm mạng, nên test được đầy đủ.
- **TTS generate**, **voices** và **usage-logs** gọi raw `client.request()`. Lý do đã kiểm chứng trên chính bản 2.3.2: SDK khi đó chưa có `client.voices`, chưa có `client.usage_logs`, và `CreateTtsPayload` chưa có `speed`. Raw request chạy đúng trên cả dải `>=2.3.2,<3`. Từ 2.8.0 SDK đã có sẵn cả ba; chuyển sang API SDK là việc làm sau, kèm nâng sàn phụ thuộc.
- Phụ thuộc chặn major (`<3`) vì code bám vào nội bộ SDK (`client.request`, `client.tts_api_base_url`).

## Phát triển

```bash
uv run --group dev pytest -q   # test logic thuần, không chạm mạng, không cần API key
uv build                       # sdist + wheel
```

## Skill cho agent

[`skills/soniox/SKILL.md`](skills/soniox/SKILL.md) là Claude Code skill bọc CLI này. Chép vào `~/.claude/skills/soniox/` để dùng.

## License

[MIT](LICENSE)
