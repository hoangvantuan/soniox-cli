# soniox-cli

CLI bọc [Soniox Python SDK](https://soniox.com/docs/sdk/python-SDK) cho **Speech-to-Text**, **Text-to-Speech**, **Files** và **Voice cloning**. Thiết kế để agent (Claude qua skill) gọi qua shell, đồng thời tiện cho người dùng terminal.

> Chỉ bọc phần **request/response** của SDK. **Không** bọc realtime streaming (WebSocket STT/TTS) vì luồng audio liên tục không hợp mô hình một-lệnh-một-kết-quả.

## Cài đặt

```bash
uv tool install .            # từ thư mục repo -> tạo lệnh `soniox` global
export SONIOX_API_KEY=<key>  # lấy tại https://console.soniox.com
soniox auth check            # xác nhận key hợp lệ
```

> Sau khi sửa code, cài lại bằng `uv tool install . --reinstall --no-cache` (version không đổi nên `uv` sẽ dùng lại build cache cũ nếu thiếu `--no-cache`).

## Lệnh chính

| Lệnh | Việc |
|---|---|
| `soniox stt transcribe <file\|url>` | Phiên âm; mặc định **chờ xong + tự dọn** file/transcription trên Soniox |
| `soniox stt get\|list\|transcript\|delete` | Quản lý transcription |
| `soniox files upload\|list\|get\|delete` | File audio đã upload |
| `soniox tts generate "<text>" -o out.wav` | Sinh giọng nói ra file |
| `soniox voices list\|create\|delete` | Voice cloning |
| `soniox models [--tts]` · `soniox usage` · `soniox auth check` | Metadata |

Thêm `--json` vào bất kỳ lệnh nào để lấy JSON đầy đủ (token-level: timestamp, speaker, confidence...).

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

# Text-to-Speech
soniox tts generate "Xin chào từ Soniox" -o hello.mp3 --language vi --speed 1.1
echo "Đoạn văn dài..." | soniox tts generate -o out.wav --language vi
```

## Hành vi đáng lưu ý

- **`transcribe` mặc định tự dọn** (`destroy`) file + transcription sau khi lấy transcript, tránh đầy quota Soniox. Dùng `--keep` để giữ lại (khi cần `get`/`transcript` sau).
- Tham số STT ít dùng: truyền qua `--config-json '{...}'` (gộp thẳng vào `CreateTranscriptionConfig`).
- Region (data residency): đặt env `SONIOX_API_BASE_URL` nếu cần endpoint theo vùng.

## Kiến trúc

- STT / Files / TTS-model / models dùng thẳng `soniox` SDK.
- **TTS generate** gọi raw `POST {tts_api_base_url}/tts` để hỗ trợ đầy đủ `speed` (SDK 2.3.2 chưa expose field này).
- **Voices** và **usage-logs** gọi raw `client.request()` (SDK 2.3.2 chưa wrap 2 namespace này, nhưng endpoint REST đã hoạt động).
