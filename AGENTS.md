# AGENTS.md

Hướng dẫn cho agent làm việc trên repo này.

## Repo là gì

`soniox-cli`: CLI Python bọc Soniox SDK (STT / TTS / Files / Voices). Không có state, không có server, không có realtime streaming.

- `src/soniox_cli/cli.py`: toàn bộ lệnh và parser.
- `src/soniox_cli/subtitles.py`: dựng SRT/VTT từ token. Thuần logic, không chạm mạng, test dày.

## Lệnh

```bash
uv run --group dev pytest -q            # test (thuần logic, không chạm mạng)
uv build                                # sdist + wheel
uv tool install . --reinstall --no-cache   # cài lại bản local (cần --no-cache vì version không đổi)
```

Test không cần `SONIOX_API_KEY`. Mọi test chạm mạng đều nằm ngoài repo: đừng thêm vào `tests/`.

## Quy ước

- **Version có một nguồn**: `__version__` trong `src/soniox_cli/__init__.py`; hatch đọc ngược ra `project.version`. Đừng chép số version sang chỗ khác.
- **Lỗi phải đi qua `die()`**, ra stderr kèm exit code khác 0. Không để traceback lọt ra người dùng. Khi thêm lời gọi mạng mới, kiểm tra `run()` có bắt được loại exception đó không: `httpx.HTTPError` không phải lớp con của `SonioxError`.
- **Cờ `--json` cấp subcommand phải dùng `default=argparse.SUPPRESS`** (qua `_add_json_flag`), nếu không sẽ ghi đè cờ `--json` người dùng đặt trước tên subcommand. Đọc giá trị bằng `wants_json(args)`.
- **`--config-json` lọc key lạ chỉ ở đường đi QUA model pydantic** (STT), bằng `reject_unknown_keys()`: pydantic mặc định `extra="ignore"` nên gõ sai tên trường sẽ bị bỏ im lặng. Payload gửi thẳng API (TTS) thì **không lọc**, vì ở đó API mới là bên phán quyết và lọc theo model SDK sẽ chặn oan trường mới (`speed` không có trong `CreateTtsPayload` của 2.3.2; `reduce_silence` chỉ có từ 2.9.0).
- **Không âm thầm đoán thay người dùng.** Đuôi file lạ, `--format` lạ, `--speed` ngoài dải: báo lỗi kèm danh sách hợp lệ.
- **Đừng tin kiểu dữ liệu API trả về.** `cost_usd` về dạng chuỗi, `Voice.models` là danh sách dict chứ không phải chuỗi, token bản dịch có `start_ms = 0`. Ép kiểu và kiểm tra hình dạng trước khi dùng; cả ba đều là bug thật bắt được khi chạy với API thật, không phải suy đoán.
- **Dọn dẹp phải nắm được id.** `stt transcribe` tự tạo rồi tự chờ (thay vì dùng `transcribe_and_wait_with_tokens`) để khi timeout hoặc Ctrl-C còn id mà dọn hoặc lấy lại kết quả.

## Ràng buộc phụ thuộc

`soniox>=2.3.2,<3`. Code bám vào nội bộ SDK: `client.request()` và `client.tts_api_base_url`. Nâng qua major phải kiểm lại `cmd_tts_generate`, `_request_json`, và các đường dẫn `/voices`, `/usage-logs`.

## Tài liệu domain

Trước khi sửa code, đọc:

- [`CONTEXT.md`](CONTEXT.md): bảng thuật ngữ và ranh giới. Phân biệt **transcription** với **transcript**, **delete** với **destroy**.
- [`docs/adr/`](docs/adr/): 4 quyết định kiến trúc đã chốt kèm lý do và đánh đổi.

Nếu thay đổi của bạn đi ngược một ADR, nói thẳng ra thay vì lặng lẽ ghi đè.

## Quy ước cho skill

- [`docs/agents/domain.md`](docs/agents/domain.md): cách đọc tài liệu domain.
- [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md): thao tác issue qua `gh`.
- [`docs/agents/triage-labels.md`](docs/agents/triage-labels.md): 5 vai trò triage; 4 label còn thiếu kèm lệnh tạo.

## Issue tracker

GitHub Issues của `hoangvantuan/soniox-cli`, thao tác qua `gh` CLI (`gh issue list`, `gh issue create`, `gh issue view <n> --comments`).
