# ADR-0002: Dùng raw `client.request()` cho TTS generate, voices và usage-logs

**Trạng thái**: chấp nhận, có đường thoát

## Bối cảnh

Sàn phụ thuộc là `soniox>=2.3.2,<3`. Đã kiểm chứng trên chính bản 2.3.2 cài thật:

- không có `client.voices`
- không có `client.usage_logs`
- `CreateTtsPayload` không có trường `speed`

Từ 2.8.0 SDK đã có đủ cả ba.

## Quyết định

Ba đường này gọi raw `client.request()` tới endpoint REST (`/voices`, `/usage-logs`, `{tts_api_base_url}/tts`) thay vì dùng namespace của SDK.

## Lý do

Raw request chạy đúng trên toàn dải `>=2.3.2,<3`. Dùng namespace SDK sẽ buộc phải nâng sàn phụ thuộc, cắt bỏ người dùng đang ở bản cũ, để đổi lấy thứ mà đường REST vốn đã làm được.

## Đánh đổi

Code bám vào **nội bộ** SDK: `client.request()` và `client.tts_api_base_url`. Vì vậy phụ thuộc chặn major (`<3`). Nâng qua major phải kiểm lại `cmd_tts_generate`, `_request_json`, và các đường dẫn `/voices`, `/usage-logs`.

## Đường thoát

Khi sàn phụ thuộc nâng lên `>=2.8`, chuyển ba đường này sang API SDK và bỏ `_request_json`. Việc này cần có test bao phủ trước, hiện chưa có vì test không chạm mạng.
