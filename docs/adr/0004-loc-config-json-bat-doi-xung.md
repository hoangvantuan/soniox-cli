# ADR-0004: `--config-json` lọc key lạ ở STT nhưng không lọc ở TTS

**Trạng thái**: chấp nhận

## Bối cảnh

`--config-json` là escape hatch cho tham số mà CLI chưa có cờ riêng. Hai đường đi khác nhau về bản chất:

- **STT**: dict được nhồi vào model pydantic `CreateTranscriptionConfig`. Pydantic mặc định `extra="ignore"`, nên key sai chính tả **biến mất không một lời cảnh báo**. Gõ `language_hint` thiếu chữ s thì cấu hình đơn giản là không có tác dụng, người dùng không hề biết.
- **TTS**: dict được gộp thẳng vào payload JSON gửi lên API. Không có model nào ở giữa, không có gì bị bỏ.

## Quyết định

Lọc key lạ (`reject_unknown_keys`) **chỉ ở đường STT**. Đường TTS không lọc.

## Lý do

Lọc ở nơi giá trị sẽ **bốc hơi âm thầm**; nhường quyền phán quyết cho API ở nơi nó thực sự tới được API.

Lọc phía TTS còn có hại: danh sách key hợp lệ sẽ bị trói vào model của bản SDK đang cài. Bằng chứng cụ thể, `speed` không có trong `CreateTtsPayload` của 2.3.2 còn `reduce_silence` chỉ xuất hiện từ 2.9.0. Lọc theo model nghĩa là chặn oan những trường mà API đã hỗ trợ.

## Hệ quả

- Thêm trường STT mới mà SDK chưa biết thì bị CLI chặn, kèm danh sách trường hợp lệ. Cách xử lý là nâng SDK. Chấp nhận được vì thà báo lỗi rõ còn hơn bỏ im lặng.
- Có test khóa hành vi TTS lại (`test_config_json_tts_khong_bi_loc_theo_model_sdk`), để không ai "sửa cho nhất quán" mà phá mất.
