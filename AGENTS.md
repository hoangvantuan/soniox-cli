# AGENTS.md

Hướng dẫn cho agent làm việc trên repo này.

## Repo là gì

`soniox-cli`: CLI Python bọc Soniox SDK (STT / TTS / Files / Voices). Không có state, không có server, không có realtime streaming.

- `src/soniox_cli/cli.py`: toàn bộ lệnh và parser.
- `src/soniox_cli/subtitles.py`: dựng SRT/VTT từ token. Thuần logic, không chạm mạng, test dày.
- `src/soniox_cli/media.py`: tách audio khỏi video trước khi upload. Gọi `ffmpeg`/`ffprobe` qua `subprocess`.
- `src/soniox_cli/update.py`: tự cập nhật. Nhận diện cách cài qua `uv-receipt.toml` rồi ủy quyền cho `uv`.

## Lệnh

```bash
uv run --group dev pytest -q            # test (thuần logic, không chạm mạng)
uv build                                # sdist + wheel
uv tool install . --reinstall --no-cache   # cài lại bản local (cần --no-cache vì version không đổi)
```

Test không cần `SONIOX_API_KEY`, cũng không cần `ffmpeg`: `subprocess` bị thay trong test. Mọi test chạm mạng đều nằm ngoài repo: đừng thêm vào `tests/`.

Test cũng **không được để lại file trong temp của hệ thống**. Nhánh `keep=True` của `media.prepared_upload` có tạo thư mục tạm thật, nên `_fake_video` thay `tempfile.mkdtemp` để nó rơi vào `tmp_path`.

## Quy ước

- **Version có một nguồn**: `__version__` trong `src/soniox_cli/__init__.py`; hatch đọc ngược ra `project.version`. Đừng chép số version sang chỗ khác.
- **Lỗi phải đi qua `die()`**, ra stderr kèm exit code khác 0. Không để traceback lọt ra người dùng. Khi thêm lời gọi mạng mới, kiểm tra `run()` có bắt được loại exception đó không: `httpx.HTTPError` không phải lớp con của `SonioxError`.
- **Cờ `--json` cấp subcommand phải dùng `default=argparse.SUPPRESS`** (qua `_add_json_flag`), nếu không sẽ ghi đè cờ `--json` người dùng đặt trước tên subcommand. Đọc giá trị bằng `wants_json(args)`.
- **`--config-json` lọc key lạ chỉ ở đường đi QUA model pydantic** (STT), bằng `reject_unknown_keys()`: pydantic mặc định `extra="ignore"` nên gõ sai tên trường sẽ bị bỏ im lặng. Payload gửi thẳng API (TTS) thì **không lọc**, vì ở đó API mới là bên phán quyết và lọc theo model SDK sẽ chặn oan trường mới (`speed` không có trong `CreateTtsPayload` của 2.3.2; `reduce_silence` chỉ có từ 2.9.0).
- **Không âm thầm đoán thay người dùng.** Đuôi file lạ, `--format` lạ, `--speed` ngoài dải: báo lỗi kèm danh sách hợp lệ.
- **Đừng tin kiểu dữ liệu API trả về.** `cost_usd` về dạng chuỗi, `Voice.models` là danh sách dict chứ không phải chuỗi, token bản dịch có `start_ms = 0`. Ép kiểu và kiểm tra hình dạng trước khi dùng; cả ba đều là bug thật bắt được khi chạy với API thật, không phải suy đoán.
- **Đừng để CLI tự ghi đè thư mục cài của chính nó.** `update.py` chỉ nhận diện cách cài rồi gọi `uv`; không chắc cài bằng gì thì in hướng dẫn chứ không đoán.
- **File tạm phải xóa trong `finally`.** `media.prepared_upload` là context manager chính vì thế: bước dọn dẹp là bước hay bị bỏ sót nhất khi có lỗi giữa chừng. Ngoại lệ duy nhất là `--keep-extracted`, và khi đó đường dẫn được in ra. `finally` chỉ chạy nếu tiến trình còn sống đủ lâu, nên `main()` bắt `SIGTERM` và đổi nó thành `SystemExit`: mặc định Python bỏ qua `finally` khi nhận SIGTERM.
- **Tín hiệu hủy không xóa dữ liệu từ xa.** `Ctrl-C` và `SIGTERM` nghĩa là *thôi đứng chờ*, không nghĩa là *vứt job đi*. Cả hai chỉ dọn cục bộ rồi thoát; job trên Soniox giữ nguyên. Id thì đã được in từ lúc transcription vừa tạo, xem gạch đầu dòng dưới. Rác quota dọn được bằng một lệnh và tự hết sau 30 ngày, transcript đã xóa thì phải trả tiền phiên âm lại. Xem [ADR-0008](docs/adr/0008-tin-hieu-huy-khong-xoa-du-lieu-tu-xa.md).
- **Id phải ra ngoài ngay khi tồn tại.** `stt transcribe` tự tạo rồi tự chờ (thay vì dùng `transcribe_and_wait_with_tokens`) để luôn nắm được id, và in id ra stderr **vô điều kiện** ngay sau khi tạo. Đừng đưa lời in đó vào một nhánh nào cả: `SIGKILL`, mất điện và harness teardown không chạy `except` nào hết.
- **Lệnh cứu hộ không được cho kết quả kém hơn lệnh nó cứu hộ.** `stt transcript <id>` phải in ra y hệt `stt transcribe` cho cùng một job, nên nó đi chung `emit_transcript`. Đừng thêm "đường nhanh cho text thuần": `transcript.text` không có nhãn speaker và không có bản dịch.
- **Mọi đường ra dữ liệu lớn đều đi qua `write_out`.** Đó là chỗ duy nhất có `-o` và cảnh báo `BIG_OUTPUT_CHARS`. `print_json` đi thẳng ra stdout nên chỉ dùng cho output ngắn (`emit`); transcript thì dùng `write_out(args, json_text(...))`.

## Ràng buộc phụ thuộc

`soniox>=2.3.2,<3`. Code bám vào nội bộ SDK: `client.request()` và `client.tts_api_base_url`. Nâng qua major phải kiểm lại `cmd_tts_generate`, `_request_json`, và các đường dẫn `/voices`, `/usage-logs`.

## Tài liệu domain

Trước khi sửa code, đọc:

- [`CONTEXT.md`](CONTEXT.md): bảng thuật ngữ và ranh giới. Phân biệt **transcription** với **transcript**, **delete** với **destroy**.
- [`docs/adr/`](docs/adr/): 8 quyết định kiến trúc đã chốt kèm lý do và đánh đổi.

Nếu thay đổi của bạn đi ngược một ADR, nói thẳng ra thay vì lặng lẽ ghi đè.

## Quy ước cho skill

- [`docs/agents/domain.md`](docs/agents/domain.md): cách đọc tài liệu domain.
- [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md): thao tác issue qua `gh`.
- [`docs/agents/triage-labels.md`](docs/agents/triage-labels.md): 5 vai trò triage; 4 label còn thiếu kèm lệnh tạo.

## Issue tracker

GitHub Issues của `hoangvantuan/soniox-cli`, thao tác qua `gh` CLI (`gh issue list`, `gh issue create`, `gh issue view <n> --comments`).
