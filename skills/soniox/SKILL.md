---
name: soniox
description: >-
  Speech-to-Text và Text-to-Speech cho FILE AUDIO BẤT KỲ qua Soniox, dùng CLI
  `soniox`. Kích hoạt khi cần: phiên âm / bóc băng / chuyển audio thành text
  ("transcribe", "phiên âm", "bóc băng", "audio thành text", "tạo phụ đề",
  "chuyển ghi âm thành chữ"); tách người nói (diarization); dịch nội dung audio
  sang ngôn ngữ khác; sinh giọng nói / đọc văn bản thành tiếng ("text to speech",
  "TTS", "đọc thành giọng nói", "tạo file audio từ text"); clone giọng nói
  (voice cloning); hoặc khi nhắc thẳng "soniox". Nhận FILE audio HOẶC VIDEO
  local (tự tách audio trước khi upload) và URL tải trực tiếp file audio, khác
  với các skill chỉ lấy phụ đề có sẵn của một nền tảng. KHÔNG tải được từ
  YouTube / Drive / trang web: tải file về trước đã. KHÔNG dùng cho realtime
  streaming micro.
---

# Soniox CLI

CLI `soniox` bọc Soniox SDK cho STT / TTS / Files / Voice cloning. Chạy local, xử lý file audio local trực tiếp.

## Thiết lập (làm 1 lần)

```bash
soniox auth check
```

- Nếu lệnh `soniox` không tồn tại: `uv tool install git+https://github.com/hoangvantuan/soniox-cli`
- Nếu báo thiếu key: cần `export SONIOX_API_KEY=<key>` (lấy tại https://console.soniox.com).

## Bảng lệnh

| Lệnh | Việc |
|---|---|
| `soniox stt transcribe <file\|url>` | Phiên âm. Mặc định **chờ xong + in text + tự dọn** khỏi Soniox |
| `soniox stt transcribe <x> --no-wait` | Trả `id` ngay (job dài); poll sau |
| `soniox stt transcribe <x> --subtitles srt\|vtt` | Xuất **phụ đề** |
| `soniox stt get\|transcript\|list\|count\|delete\|delete-all` | Quản lý transcription |
| `soniox stt transcript <id> --group-speakers` | Gộp lại theo người nói (nếu transcript có) |
| `soniox files upload\|list\|get\|count\|delete\|delete-all` | File audio đã upload |
| `soniox tts generate "<text>" -o out.wav` | Text → file audio |
| `soniox voices list\|get\|create\|count\|recompute\|delete` | Voice cloning |
| `soniox models [--tts]` · `usage` · `concurrency` · `auth check` | Metadata |

Thêm `--json` vào bất kỳ lệnh nào để lấy JSON đầy đủ (token-level: timestamp, speaker, confidence, language).

## Video: đưa thẳng vào, đừng tự convert

```bash
soniox stt transcribe hop.mp4     # tự tách audio, tự dọn file tạm
```

CLI phát hiện luồng hình bằng `ffprobe`, tách audio ra thư mục tạm (copy nguyên luồng, không mã hóa lại nên không mất chất lượng), upload phần audio, rồi **xóa file tạm trong `finally`**. Chỉ upload phần cần thiết:

```
tách audio khỏi video (aac) trước khi upload...
upload 55 KB thay vì 224 KB (hop.m4a)
```

**Đừng tự chạy `ffmpeg` rồi tự dọn.** CLI đã làm, và bước dọn dẹp thủ công là bước hay bị bỏ sót nhất khi có lỗi giữa chừng.

- Thiếu `ffmpeg` thì CLI báo kèm cách cài. Không có ffmpeg mà vẫn muốn chạy: `--no-extract-audio` (upload nguyên video, Soniox vẫn nhận `mp4`/`webm`, chỉ tốn băng thông).
- Cần giữ lại file audio đã tách: `--keep-extracted`, CLI in đường dẫn và **không** tự xóa. Xóa tay sau khi dùng xong.
- Đuôi audio quen thuộc (`.mp3`, `.wav`, `.m4a`, ...) đi thẳng, không đụng tới ffmpeg.

## Tiết kiệm context: audio dài thì ghi ra file

Mặc định kết quả in ra **stdout**, tiện khi clip ngắn. Với bản ghi dài, đổ cả transcript vào context là lãng phí: dùng `-o` rồi đọc phần cần.

```bash
soniox stt transcribe hop-2-tieng.mp4 -o /tmp/hop.txt
wc -l /tmp/hop.txt && head -40 /tmp/hop.txt     # xem trước rồi mới quyết
grep -n "ngân sách" /tmp/hop.txt                # tìm thẳng thứ cần
```

`-o` dùng được cho cả text thuần lẫn `--subtitles`, và CLI tự tạo thư mục cha. Nếu quên `-o` mà kết quả dài hơn 20.000 ký tự, CLI nhắc một dòng ở stderr.

**Quy tắc**: audio dài hơn khoảng 10 phút, hoặc chỉ cần tóm tắt / trích một đoạn, thì ghi ra file trước. Đặt file tạm vào `/tmp` và xóa sau khi xong.

## Ví dụ hay dùng

```bash
# Phiên âm file local, lấy text (tự xóa khỏi Soniox sau khi xong)
soniox stt transcribe ghiam.mp3

# Video: đưa thẳng, CLI tách audio rồi dọn file tạm
soniox stt transcribe hop.mp4 --diarize

# Bản ghi dài: ghi ra file, rồi đọc phần cần thay vì đổ hết vào context
soniox stt transcribe hop-dai.mp4 -o /tmp/hop.txt && head -40 /tmp/hop.txt

# Tách người nói + gợi ý ngôn ngữ (kết quả in theo "Speaker 1: ...")
soniox stt transcribe hop.mp3 --diarize --language-hints vi,en

# Dịch audio sang tiếng Việt (in xen kẽ gốc và "→ vi: ...")
soniox stt transcribe english.mp3 --translate vi
# Dịch hai chiều
soniox stt transcribe call.mp3 --translate two-way:en,vi

# Job dài: không chờ
id=$(soniox stt transcribe long.mp3 --no-wait --json | jq -r .id)
soniox stt transcript "$id"          # khi status=completed

# Phụ đề SRT kèm tách người nói
soniox stt transcribe hop.mp3 --diarize --subtitles srt -o hop.srt
# Phụ đề tiếng Việt cho audio tiếng Anh (auto lấy bản dịch)
soniox stt transcribe english.mp3 --translate vi --subtitles vtt -o english.vtt
# Phụ đề song ngữ
soniox stt transcribe english.mp3 --translate vi --subtitles srt --subtitle-track both

# Text-to-Speech
soniox tts generate "Xin chào" -o hello.mp3 --language vi --speed 1.1
echo "Đoạn dài..." | soniox tts generate -o out.wav --language vi   # đọc từ stdin

# Voice cloning: tạo giọng từ clip mẫu rồi dùng khi generate
soniox voices create mau.wav --name giong_toi
soniox tts generate "Thử giọng" -o thu.mp3 --voice <voice_id> --language vi

# Kiểm tra quota và dọn dẹp
soniox usage                            # chi phí 24h gần nhất, gộp theo model
soniox stt count && soniox files count  # còn gì trên Soniox
soniox stt delete-all --destroy --yes   # dọn sạch (bắt buộc --yes)
soniox concurrency                      # phiên đồng thời và giới hạn, để chẩn 429
```

## Lưu ý quan trọng

- **Auto-destroy**: `transcribe` mặc định xóa file + transcription khỏi Soniox sau khi lấy text (tránh đầy quota). Dùng `--keep` nếu cần `get`/`transcript` lại sau. Hết `--timeout` (mặc định 600s) thì CLI in id kèm lệnh để lấy kết quả hoặc dọn tay.
- **Đầu vào STT**: file audio hoặc video local, `--file-id`, hoặc URL **tải trực tiếp file audio**. Video chỉ tách được khi là file local; URL thì Soniox tải phía nó, muốn tách phải tải về trước. Link YouTube/Drive/trang web sẽ hỏng (Soniox nhận về HTML, báo "Invalid audio file") — tải file về trước rồi đưa đường dẫn local. Không truyền đồng thời `--file-id` và file/URL.
- **Phụ đề**: `--subtitles srt|vtt`, thêm `-o <file>` để ghi ra file. `--subtitle-track` chọn `auto` (mặc định, có dịch thì lấy bản dịch), `original`, `translation`, hay `both` (song ngữ). Không dùng chung với `--no-wait`.
- **File dài**: mặc định chờ tối đa 600s. Dài hơn thì tăng `--timeout`, hoặc `--no-wait` rồi poll bằng `stt transcript <id>`. Hết giờ CLI in sẵn id kèm lệnh lấy lại kết quả.
- **TTS**: bắt buộc `-o <file>`; định dạng suy từ đuôi (`.wav`, `.mp3`, `.flac`, `.opus`, `.aac`, `.pcm`). Đuôi lạ sẽ báo lỗi, ép bằng `--format`. `--speed` 0.7 đến 1.3.
- **Tham số hiếm**: `--config-json '{...}'` cho cả STT lẫn TTS. Tên trường sai sẽ báo lỗi kèm danh sách hợp lệ.
- **Lỗi**: ra stderr, exit code khác 0. Đọc thông báo (kèm `request_id`) để chẩn đoán.

## Khi cần chi tiết vượt CLI

Danh sách ngôn ngữ hỗ trợ, giải thích tham số, giới hạn quota... → **WebFetch** docs Soniox:
`https://soniox.com/docs/stt/concepts/supported-languages`, `https://soniox.com/docs/sdk/python-SDK`,
`https://soniox.com/docs/api-reference`. Dữ liệu động (model, voice) lấy thẳng: `soniox models`, `soniox voices list`.
