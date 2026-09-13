# ADR-0001: Không bọc realtime streaming

**Trạng thái**: chấp nhận

## Bối cảnh

Soniox SDK có cả `client.realtime` (WebSocket STT và TTS) lẫn API request/response thông thường.

## Quyết định

CLI chỉ bọc phần request/response. Không bọc `realtime`, không bọc webhook receiver.

## Lý do

Một lệnh shell có mô hình vào-ra là **một lệnh, một kết quả, rồi thoát**. Luồng audio liên tục hai chiều không hợp mô hình đó: nó cần vòng đời dài, xử lý sự kiện, và quản lý backpressure. Ép nó vào CLI sẽ tạo ra một giao diện tệ cho cả người dùng terminal lẫn agent.

Ai cần realtime thì gọi SDK trực tiếp, đó là chỗ đúng của nó.

## Hệ quả

- `soniox` không bao giờ là công cụ cho micro trực tiếp. Skill phải nói rõ điều này để agent không kích hoạt nhầm.
- Job dài được phục vụ bằng `--no-wait` cộng poll, không phải bằng streaming.
