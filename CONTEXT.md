# CONTEXT

Bảng thuật ngữ và ranh giới của `soniox-cli`. Dùng đúng những từ này trong issue, test, commit và đề xuất refactor.

## Ranh giới

CLI bọc **phần request/response** của Soniox API. Nằm ngoài phạm vi: realtime streaming (WebSocket STT/TTS) và webhook receiver. Xem [ADR-0001](docs/adr/0001-khong-boc-realtime-streaming.md).

CLI **không giữ state**. Mọi thứ bền vững đều nằm trên Soniox; máy local chỉ có file audio đầu vào và file audio đầu ra.

## Thuật ngữ

| Thuật ngữ | Nghĩa trong repo này |
|---|---|
| **transcription** | Bản ghi *công việc* phiên âm trên Soniox: có `id`, `status`, `model`, `file_id`. Không phải nội dung text. |
| **transcript** | *Kết quả* của một transcription: `text` cộng danh sách **token**. Lấy bằng `stt transcript <id>`. |
| **token** | Đơn vị nhỏ nhất của transcript: `text`, mốc thời gian, `speaker`, `language`, `translation_status`, `confidence`. Chỉ thấy được qua `--json`. |
| **file** | Audio đã upload lên Soniox, có `id` riêng, **tồn tại độc lập** với transcription dùng nó. |
| **delete** | Xóa **chỉ** transcription. File đã upload vẫn còn và vẫn tính quota. |
| **destroy** | Xóa transcription **và** file đính kèm. Đây là thứ `transcribe` làm mặc định. Đừng gọi cả hai là "xóa". |
| **voice** | Giọng đã clone từ clip mẫu, dùng lại được khi `tts generate --voice <id>`. |
| **diarization** | Tách người nói. Bật bằng `--diarize`, kết quả hiện ở trường `speaker` của token. |
| **translation** | Dịch nội dung audio. `one_way` (sang một ngôn ngữ đích) hoặc `two_way` (giữa hai ngôn ngữ). Token được gắn `translation_status` là `original` hoặc `translation`. |
| **language hints** | Gợi ý ngôn ngữ cho STT, không phải ràng buộc cứng. |
| **cue** | Một khối phụ đề: khoảng thời gian cộng đoạn text hiện lên màn hình. Token Soniox nhỏ hơn từ nên phải gom lại thành cue. |
| **track** | Luồng token dùng cho phụ đề: `original`, `translation`, `both`, hay `auto` (có dịch thì lấy dịch). |
| **escape hatch** | `--config-json`: đường truyền thẳng tham số mà CLI chưa có cờ riêng. Xem [ADR-0004](docs/adr/0004-loc-config-json-bat-doi-xung.md). |

## Phân biệt dễ nhầm

- **transcription ≠ transcript**: một bên là công việc, một bên là kết quả. `stt get` trả về transcription; `stt transcript` trả về transcript.
- **delete ≠ destroy**: xem bảng trên. Nhầm hai từ này làm đầy quota file mà không ai nhận ra.
- **`--keep` không phải "lưu về máy"**: nó nghĩa là *giữ lại trên Soniox*, không tự dọn.
- **`--no-wait` không phải chạy nền ở local**: công việc luôn chạy trên Soniox; cờ này chỉ quyết định CLI có đứng chờ hay không.
