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

## Cập nhật

```bash
soniox update --check    # có bản mới không?
soniox update            # cập nhật nếu có
```

`update` không tự sửa file trong thư mục cài: nó đọc `uv-receipt.toml` để biết CLI được cài thế nào, rồi gọi đúng lệnh của trình quản lý gói.

| Cài bằng | `soniox update` làm gì |
|---|---|
| `uv tool install git+https://...` | chạy `uv tool upgrade soniox-cli` |
| `uv tool install <thư mục>` | dừng lại, in ra lệnh `git pull` cộng lệnh cài lại cho bạn chạy |
| cách khác | dừng lại, in ra lệnh cài lại từ GitHub |

`uv tool upgrade` tự giải lại git ref và lấy commit mới, không cần `--reinstall`. Kiểm chứng bằng một lần nhảy thật `0.3.0 → 0.4.0`, uv ghi đúng SHA mới vào receipt.

Cờ khác: `--no-check` bỏ qua bước hỏi GitHub, `--force` thêm `--reinstall` để cài lại kể cả khi uv cho rằng đã mới nhất, `--json` để lấy máy đọc.

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
| `soniox stt transcribe <file\|url>` | Phiên âm; **video được tách audio trước khi upload**; mặc định **chờ xong + tự dọn** file/transcription trên Soniox |
| `soniox stt transcribe <x> --subtitles srt` | Xuất **phụ đề SRT / VTT** |
| `soniox stt transcribe <x> --timestamps` | Text ngắt dòng theo **lượt nói**, mỗi dòng mở đầu bằng `[HH:MM:SS]` |
| `soniox stt get\|list\|transcript\|count\|delete\|delete-all` | Quản lý transcription |
| `soniox stt transcript <id> --destroy` | Kéo transcript về rồi dọn cả transcription lẫn file |
| `soniox files upload\|list\|get\|count\|delete\|delete-all` | File audio đã upload |
| `soniox tts generate "<text>" -o out.wav` | Sinh giọng nói ra file |
| `soniox voices list\|get\|create\|count\|recompute\|delete` | Voice cloning |
| `soniox models [--tts]` · `soniox usage` · `soniox concurrency` · `soniox auth check` | Metadata |
| `soniox update [--check]` | Cập nhật CLI lên bản mới nhất |
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

# Không chờ (khi tiến trình local có thể không sống tới lúc xong): trả id ngay
soniox stt transcribe long.mp3 --no-wait --ref hop-2026-09-13
soniox stt transcript <id> -o /tmp/hop.txt --destroy   # --no-wait không tự dọn

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

## Video

Đưa thẳng file video vào, CLI tách audio trước khi upload:

```bash
soniox stt transcribe hop.mp4
# tách audio khỏi video (aac) trước khi upload...
# upload 55 KB thay vì 224 KB (hop.m4a)
```

Soniox nhận cả `mp4` / `webm`, nên upload nguyên video vẫn chạy; tách audio chỉ để khỏi trả băng thông cho luồng hình mà STT không dùng. Cơ chế:

- Đuôi audio quen thuộc đi thẳng, **không gọi ffmpeg**.
- Còn lại thì `ffprobe` kiểm tra có luồng hình thật không (ảnh bìa `mjpeg` không tính).
- Tách bằng **copy nguyên luồng**, không mã hóa lại, nên không mất chất lượng. Codec lạ (`ac3`, `dts`, ...) mới chuyển sang AAC.
- File tạm nằm trong thư mục tạm hệ thống và **bị xóa trong `finally`**, kể cả khi lỗi giữa chừng.

`--no-extract-audio` upload nguyên file. `--keep-extracted` giữ file tách lại và in đường dẫn (CLI không tự xóa). Chi tiết và đánh đổi: [ADR-0006](docs/adr/0006-tach-audio-khoi-video-truoc-khi-upload.md).

Cần `ffmpeg` **chỉ khi** đầu vào là video. macOS: `brew install ffmpeg`.

## Đường ra: stdout hay file

Mặc định mọi kết quả in ra **stdout**, không tạo file nào. `-o <file>` ghi thẳng ra file (tự tạo thư mục cha), dùng được cho cả text thuần, `--timestamps` lẫn `--subtitles`. Riêng `tts generate` thì `-o` là bắt buộc vì đầu ra là nhị phân.

Với bản ghi dài, nên dùng `-o` rồi đọc phần cần thay vì đổ hết ra màn hình. Quên `-o` mà kết quả dài hơn 20.000 ký tự thì CLI nhắc một dòng ở stderr (stderr nên không ảnh hưởng `|` và `>`). `--json` cũng đi qua đúng đường này ở `stt transcribe` (khi có chờ kết quả) và `stt transcript`, nên `-o` và lời nhắc đều có tác dụng. Các lệnh còn lại, kể cả `transcribe --no-wait --json`, in JSON thẳng ra stdout: output ngắn nên dùng `>` là đủ.

## Lấy lại kết quả khi mất tiến trình

Job chạy trên Soniox, không chạy trên máy bạn. Tiến trình local chết không làm job chết theo, nên gần như luôn lấy lại được:

```bash
soniox stt list                                  # id, trạng thái, thời điểm tạo, thời lượng, tên file
soniox stt transcript <id> -o /tmp/ket-qua.txt   # kéo transcript về
soniox stt transcript <id> --destroy             # kéo về xong dọn luôn, cả file đính kèm
```

Đặt `--ref <nhãn>` lúc `transcribe` thì `stt list --json` lọc được chính xác theo `client_reference_id`, khỏi phải đoán theo tên file. Nhãn gắn cho **cả file lẫn transcription**, nên còn tìm được cả trường hợp bị giết giữa lúc upload, lúc mà transcription còn chưa kịp tồn tại.

`--no-wait` **không** có auto-destroy. Dọn tay bằng `stt transcript <id> --destroy`, hoặc `stt delete <id> --destroy`.

## Mốc thời gian trong text

`transcript.text` của Soniox là **một dòng duy nhất**: bản ghi 2h40 thành khoảng 140.000 ký tự trên một dòng, không `grep -n` được, không `diff` được. `--timestamps` (có ở cả `stt transcribe` và `stt transcript`) ngắt dòng theo **lượt**: chuỗi token liên tiếp không bị ngắt bởi khoảng lặng quá 0.7 giây, cũng không bị ngắt bởi việc đổi người nói.

```
[00:12:34] Speaker 1: Chào mọi người, hôm nay ta chốt ngân sách.
[00:13:02] Speaker 2: Vâng, tôi đồng ý.
```

Chỉ in mốc **bắt đầu** lượt, không in cả khoảng: grep được, hợp quy ước biên bản họp, in cả khoảng chỉ thêm nhiễu. Có bản dịch thì mỗi lượt dịch là một dòng riêng, giữ nguyên nhãn `→ <ngôn ngữ>:` của text thuần. `--flat` bỏ nhãn `Speaker N:`, lượt khi đó chỉ ngắt theo khoảng lặng.

**Lượt** là anh em với **cue** của phụ đề: cùng cách gom token, khác chỗ dừng. Cue phải nằm vừa màn hình nên bị chặn bởi `--subtitle-max-chars`, bởi 6 giây và bởi dấu kết câu; lượt để đọc và `grep` nên không chặn gì cả.

`--timestamps` không dùng chung với `--subtitles` (hai cách dựng khác nhau cho cùng một đầu ra) và cũng không dùng chung với `--no-wait` (chưa có transcript thì chưa có token).

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

`--subtitles` không dùng chung với `--no-wait` (chưa có transcript thì chưa dựng được phụ đề). Cũng không dùng chung với `--timestamps`.

## Hành vi đáng lưu ý

- **`transcribe` mặc định tự dọn** (`destroy`) file + transcription sau khi lấy transcript, tránh đầy quota Soniox. Dùng `--keep` để giữ lại (khi cần `get`/`transcript` sau).
  - Id được in ra stderr **ngay khi transcription vừa tạo**, trước cả lúc bắt đầu chờ. Mất kết nối, mất tiến trình, đóng máy: vẫn còn chỗ bám để lấy lại kết quả.
  - **Trong lúc chờ, cứ khoảng 30 giây CLI in một dòng stderr**: id, thời gian đã trôi qua, `status` hiện tại. Đây là tín hiệu sống để phân biệt "đang chạy" với "đã treo", không phải thanh tiến độ: Soniox không trả phần trăm hoàn thành. Nhịp bám theo vòng poll nên giãn ra được khi một lần hỏi bị treo hoặc khi đang thử lại sau lỗi mạng; lúc đó chính dòng cảnh báo thử lại là tín hiệu sống.
  - Hết `--timeout` (mặc định 600s): CLI in ra id kèm lệnh để lấy kết quả hoặc dọn thủ công.
  - Mất kết nối giữa lúc chờ: CLI thử lại tối đa 5 lần (nghỉ 5/10/20/40/60 giây) rồi mới bỏ cuộc, và khi bỏ cuộc vẫn in id ra. Mạng hỏng ở máy bạn không nói gì về job trên Soniox. Xem [ADR-0009](docs/adr/0009-cli-tu-nuoi-vong-lap-cho.md).
  - Ctrl-C hoặc `SIGTERM` giữa chừng: CLI dọn file tạm cục bộ rồi in id, **không xóa job trên Soniox**. Hủy chờ không phải hủy job. Xem [ADR-0008](docs/adr/0008-tin-hieu-huy-khong-xoa-du-lieu-tu-xa.md).
  - `--ref <nhãn>` gắn nhãn tự đặt cho cả file lẫn transcription, để tìm lại bằng `stt list` khi mất sạch ngữ cảnh.
- **Người nói và bản dịch tự hiện ra.** Cả `transcribe` lẫn `transcript` đều gắn nhãn `Speaker N:` khi token có speaker, và xen kẽ bản dịch khi có. `--flat` tắt nhãn Speaker (bản dịch vẫn giữ). `--group-speakers` là cờ cũ, nay không còn tác dụng, giữ lại cho tương thích. `--timestamps` thêm mốc `[HH:MM:SS]` và ngắt dòng theo lượt nói.
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
- **Tự cập nhật** nằm trong `src/soniox_cli/update.py`: nhận diện cách cài rồi ủy quyền cho `uv`, không tự ghi đè thư mục cài của chính mình.
- **Chuẩn bị file upload** nằm trong `src/soniox_cli/media.py`, gọi `ffmpeg`/`ffprobe` qua `subprocess`; test thay `subprocess` nên không cần ffmpeg để chạy.
- **TTS generate**, **voices** và **usage-logs** gọi raw `client.request()`. Lý do đã kiểm chứng trên chính bản 2.3.2: SDK khi đó chưa có `client.voices`, chưa có `client.usage_logs`, và `CreateTtsPayload` chưa có `speed`. Raw request chạy đúng trên cả dải `>=2.3.2,<3`. Từ 2.8.0 SDK đã có sẵn cả ba; chuyển sang API SDK là việc làm sau, kèm nâng sàn phụ thuộc.
- Phụ thuộc chặn major (`<3`) vì code bám vào nội bộ SDK (`client.request`, `client.tts_api_base_url`).

## Phát triển

```bash
uv run --group dev pytest -q   # test logic thuần, không chạm mạng, không cần API key
uv build                       # sdist + wheel
```

## Skill cho agent

[`skills/soniox/SKILL.md`](skills/soniox/SKILL.md) là agent skill bọc CLI này. Cài bằng [`skills`](https://github.com/vercel-labs/skills):

```bash
npx skills add hoangvantuan/soniox-cli          # chọn agent và phạm vi khi được hỏi
npx skills add hoangvantuan/soniox-cli -g -a claude-code -y   # không hỏi: global, Claude Code
npx skills update soniox                        # kéo bản mới về sau này
```

Mặc định nó symlink từ thư mục của từng agent về một bản gốc duy nhất, nên không có chuyện mỗi agent giữ một bản khác nhau. **Đừng chép tay** đè lên bản đó: lockfile (`~/.agents/.skill-lock.json`) sẽ lệch với nội dung trên đĩa, và `skills update` lần sau sẽ kéo bản trên GitHub về đè lại.

Sửa skill thì thử tại chỗ bằng đường dẫn local trước khi push:

```bash
npx skills add . --list      # xem repo này expose những skill nào
npx skills add . --skill soniox
```

Skill và CLI phải đi cùng nhau: skill mô tả cờ nào thì bản `soniox` đang cài phải có cờ đó. Nếu skill nói về một cờ mà CLI báo `unrecognized arguments`, chạy `soniox update`.

## License

[MIT](LICENSE)
