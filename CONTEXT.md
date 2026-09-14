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
| **tách audio** | Bỏ luồng hình khỏi file video trước khi upload, bằng cách copy nguyên luồng audio. Không phải "convert", không mã hóa lại. |
| **cue** | Một khối phụ đề: khoảng thời gian cộng đoạn text hiện lên màn hình. Token Soniox nhỏ hơn từ nên phải gom lại thành cue. |
| **lượt** | Chuỗi token liên tiếp không bị ngắt bởi khoảng lặng vượt ngưỡng, cũng không bị ngắt bởi việc đổi speaker. Đơn vị ngắt dòng của `--timestamps`. |
| **track** | Luồng token dùng cho phụ đề: `original`, `translation`, `both`, hay `auto` (có dịch thì lấy dịch). |
| **escape hatch** | `--config-json`: đường truyền thẳng tham số mà CLI chưa có cờ riêng. Xem [ADR-0004](docs/adr/0004-loc-config-json-bat-doi-xung.md). |
| **mồ côi** | Job mà **id của nó không tồn tại ở đâu ngoài Soniox**. Không phải "job còn sót lại": job còn sót mà biết id là tài sản phục hồi, không phải rác. |
| **ref** | `client_reference_id`: nhãn gắn cho **cả file lẫn transcription**, tìm lại bằng `stt list` / `files list`. Đây là cách chống mồ côi khi id còn chưa kịp tồn tại. Hai loại: nhãn người dùng đặt bằng `--ref`, và **ref tự sinh** theo vân tay (tiền tố `soniox-cli:`). |
| **vân tay** | Khóa xác định của một lần phiên âm, tính từ **tên file + kích thước + 1 MB đầu + 1 MB cuối + model + config**. Tái tạo được từ chính file đầu vào, không cần nhớ gì. Là nguồn của ref tự sinh. Xem [ADR-0010](docs/adr/0010-ref-tu-sinh-theo-van-tay-dau-vao.md). |
| **dùng lại** | `transcribe` thấy job cũ trùng ref tự sinh thì lấy luôn transcript của nó, không upload và không phiên âm lại. Tắt bằng `--no-reuse`. |
| **heartbeat** | Dòng stderr khoảng 30 giây một lần trong lúc `stt transcribe` đứng chờ: id, thời gian đã trôi qua, `status`. Tín hiệu sống, **không phải** thanh tiến độ: Soniox không trả phần trăm hoàn thành. Xem [ADR-0009](docs/adr/0009-cli-tu-nuoi-vong-lap-cho.md). |
| **hủy chờ** | Thôi đứng đợi kết quả (`Ctrl-C`, `SIGTERM`). **Không** đụng tới job trên Soniox. Xem [ADR-0008](docs/adr/0008-tin-hieu-huy-khong-xoa-du-lieu-tu-xa.md). |
| **hủy job** | Xóa dữ liệu trên Soniox. Chỉ xảy ra khi người dùng nói thẳng (`stt delete`), hoặc khi `transcribe` đã lấy xong transcript. |

## Phân biệt dễ nhầm

- **lượt ≠ cue**: cùng một cách gom token, khác mục đích. Cue phục vụ màn hình nên bị chặn bởi `max_chars`, độ dài và dấu kết câu; lượt phục vụ đọc và `grep` nên không chặn gì ngoài khoảng lặng và đổi speaker.
- **transcription ≠ transcript**: một bên là công việc, một bên là kết quả. `stt get` trả về transcription; `stt transcript` trả về transcript.
- **delete ≠ destroy**: xem bảng trên. Nhầm hai từ này làm đầy quota file mà không ai nhận ra.
- **`--keep` không phải "lưu về máy"**: nó nghĩa là *giữ lại trên Soniox*, không tự dọn.
- **`--no-wait` không phải chạy nền ở local**: công việc luôn chạy trên Soniox; cờ này chỉ quyết định CLI có đứng chờ hay không.
- **heartbeat ≠ tiến độ**: dòng heartbeat nói "còn sống, đang ở trạng thái này", không nói "còn bao lâu nữa".
- **hủy chờ ≠ hủy job**: `Ctrl-C` và `SIGTERM` chỉ nói được "thôi đợi", không nói được "vứt dữ liệu". Rác quota tự lành sau 30 ngày; transcript đã xóa thì không.
- **mồ côi không phải "còn sót"**: thứ quyết định là id có tồn tại ngoài tiến trình hay không, không phải job có còn trên Soniox hay không.
- **ref tự sinh ≠ nhãn `--ref`**: một bên là danh tính suy ra được từ file, một bên là nhãn người dùng đặt mà Soniox nói rõ "does not need to be unique". Tiền tố `soniox-cli:` là thứ phân biệt hai loại, và chỉ ref mang tiền tố mới được dò để dùng lại job cũ.
- **dùng lại ≠ `--keep`**: dùng lại nói về job **đã có trước lượt chạy này**; `--keep` nói về việc giữ job lại **sau** lượt chạy. Job dùng lại vẫn bị dọn nếu không có `--keep`.
