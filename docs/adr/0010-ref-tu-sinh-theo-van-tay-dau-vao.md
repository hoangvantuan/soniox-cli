# ADR-0010: Ref tự sinh theo vân tay đầu vào

**Trạng thái**: chấp nhận. Nối tiếp [ADR-0008](0008-tin-hieu-huy-khong-xoa-du-lieu-tu-xa.md).

## Bối cảnh

[ADR-0008](0008-tin-hieu-huy-khong-xoa-du-lieu-tu-xa.md) chốt rằng job trên Soniox phải sống sót qua cái chết của tiến trình local, và chỉ ra `--ref` là đường cuối cùng tìm lại được file mồ côi khi bị giết **giữa lúc upload**, lúc mà transcription còn chưa tồn tại nên chưa có id nào để in.

Nhưng `--ref` phải gõ tay. Không ai gõ. Và ngay cả người có gõ cũng chỉ cứu được chính mình ở phiên đó: sang phiên sau, nhãn `hop-2026-09-13` nằm trong đầu người, không nằm trong file.

Nên chạy lại mù sau khi mất ngữ cảnh vẫn là: upload lại 147 MB, phiên âm lại 2h40, trả tiền lần hai. Không có cách nào biết "job này mình đã chạy rồi".

Hai cách từng nghĩ tới và **loại bỏ**:

- **Dò `stt list` theo `filename` + `duration`.** Danh tính mờ. Hai cuộc họp cùng tên `meeting.mp4` cùng dài 2h40 là chuyện có thật. Tệ hơn: `Transcription.filename` là tên file **đã tách audio** (`meeting.m4a`), không phải tên đầu vào (`meeting.mp4`).
- **Ref dạng `soniox-cli/<file>/<timestamp>`.** Vô dụng: `filename` là trường bắt buộc và `created_at` luôn có, nên ref kiểu đó không thêm một bit thông tin nào so với thứ `stt list` đã trả về.

Thứ có giá trị là khóa mà người gọi **tái tạo được** sau khi mất sạch ngữ cảnh. Vân tay của chính đầu vào thỏa điều đó: không cần nhớ gì, chỉ cần còn file.

## Quyết định

**Không có `--ref` thì CLI tự sinh ref từ vân tay đầu vào, rồi dò dùng lại job cũ trùng ref trước khi upload.**

1. `ref = "soniox-cli:1:" + sha256(tên file + kích thước + sha256(1 MB đầu + 1 MB cuối) + model + config)[:32]`.
2. **Danh tính job gồm cả model và config**, không chỉ audio. Dịch sang tiếng khác là job khác, dù cùng audio: kết quả khác thì không dùng lại được.
3. Ref được in ra stderr **trước khi upload**, vô điều kiện. Đó là điểm duy nhất chắc chắn chạy trước khi có thứ gì tồn tại trên Soniox.
4. Thấy job trùng ref ở trạng thái `completed` hoặc đang chạy thì **tự dùng lại**, kèm một dòng stderr nói rõ đang dùng lại cái gì. `--no-reuse` tắt việc dùng lại mà vẫn gắn ref; `--no-ref` tắt hẳn.
5. **Chỉ dò theo ref mang tiền tố `soniox-cli:`**, bất kể do CLI sinh ra hay người dùng gõ lại đúng chuỗi đó. Nhãn thường (`--ref hop-tuan`) thì giữ nguyên đường cũ, không dò.
6. Không thấy transcription nhưng thấy **file** mang ref đó (bị giết sau khi upload xong, trước khi transcription kịp tạo) thì dùng lại `file_id`, khỏi upload lần nữa.
7. **Lỗi trong lúc dò không được làm hỏng lượt chạy.** Dò hỏng thì cảnh báo rồi tạo job mới như thường.
8. Chỉ file local mới có ref tự sinh. URL và `--file-id` thì không.

## Lý do

**Khóa phải tái tạo được, không phải ghi nhớ được.** Đó là toàn bộ điểm khác nhau giữa `--ref` gõ tay và ref tự sinh. Sau một `SIGKILL` và một lần mất sạch ngữ cảnh, thứ duy nhất còn trong tay là file đầu vào. Khóa nào suy ra được từ đúng thứ đó thì dùng được; khóa nào cần nhớ thêm gì nữa thì không.

**Tự dùng lại thay vì hỏi.** Issue đề xuất hỏi người dùng có dùng lại không. Bỏ, vì ba lý do. CLI này để agent gọi: một câu hỏi tương tác là một lần treo, đúng thứ [AGENTS.md](../../AGENTS.md) đã tránh ở `delete-all` bằng cách bắt `--yes` thay vì hỏi. Đánh đổi ở đây cũng bất đối xứng như [ADR-0008](0008-tin-hieu-huy-khong-xoa-du-lieu-tu-xa.md): dùng lại nhầm thì mất một lệnh chạy lại với `--no-reuse`, phiên âm lại thì mất tiền thật. Và dùng lại một job trùng **đúng vân tay byte + đúng model + đúng config** không phải là đoán thay người dùng, nó là trả lời đúng câu hỏi người dùng vừa hỏi. Bù lại, mỗi lần dùng lại đều in một dòng stderr nói rõ id và trạng thái: không âm thầm.

**Chỉ dò theo ref có tiền tố.** Soniox nói rõ `client_reference_id` "does not need to be unique". Nhãn người dùng đặt là nhãn, không phải danh tính: `--ref hop-tuan` có thể dính vào mười job khác nhau. Tiền tố `soniox-cli:` là thứ duy nhất phân biệt được "chuỗi này mang ngữ nghĩa danh tính" với "chuỗi này là nhãn".

**Dò hỏng không được làm hỏng lượt chạy.** Đây là ngoại lệ có chủ đích với quy ước "lỗi phải đi qua `die()`". Dò lại chỉ là đường tắt tiết kiệm tiền; để nó `die()` là biến `transcribe` thành kém tin cậy hơn lúc chưa có tính năng này. Tính năng thêm vào không được lấy đi thứ đã có.

**Chỉ file local.** URL thì nội dung đổi được dưới chân mình mà CLI không hề biết: dùng lại theo URL là trả về transcript của một file đã không còn ở đó. `--file-id` thì đã upload xong rồi, phần đắt nhất đã trả. Cả hai đều không đáng một vân tay giả.

**Dùng lại vẫn theo luật dọn dẹp của [ADR-0003](0003-transcribe-mac-dinh-tu-don.md).** Job dùng lại bị destroy sau khi lấy transcript, y như job vừa tạo, trừ khi có `--keep`. Cho job dùng lại một luật riêng là đẻ ra thứ tồn tại trên Soniox mà không lệnh nào của người dùng nói ra.

## Đánh đổi

- **Sửa byte ở GIỮA một file lớn mà giữ nguyên kích thước sẽ cho cùng vân tay.** Chỉ băm đầu 1 MB và đuôi 1 MB: đọc hết 993 MB mất vài giây **mỗi lần chạy**, cho một trường hợp gần như không xảy ra với file audio/video thật (sửa nội dung hầu như luôn đổi kích thước, và header ở 1 MB đầu mang codec, thời lượng, timestamp encoder). Cần chắc chắn tuyệt đối thì `--no-reuse`. Đổi công thức thì tăng `REF_VERSION`, ref cũ và mới không được lẫn vào nhau.
- **Mỗi lần `transcribe` tốn thêm một lượt quét `stt list`.** API không lọc được theo `client_reference_id` (`GET /transcriptions` chỉ nhận `limit` và `cursor`), nên dò ref là quét tuần tự. Chặn trên ở `REF_SCAN_MAX = 500` bản ghi; chạm trần thì nói ra rồi tạo job mới. Vì `transcribe` mặc định tự dọn, tài khoản thường rất ít bản ghi.
- **Cùng audio nhưng khác config thì upload lại.** Một ref duy nhất gắn cho cả file lẫn transcription (SDK `transcribe_from_file` làm vậy), nên file kế thừa danh tính của job. Tách làm hai ref (file theo audio, job theo audio + config) sẽ dùng lại được file khi đổi config, nhưng buộc CLI tự nuôi đường upload thay vì gọi SDK. Chưa đáng; ghi lại đây làm việc có thể làm sau.
- **Chạy lại mà quên `--keep` thì job đang cố ý giữ sẽ bị dọn.** Lần 1 chạy với `--keep` để giữ job lại; lần 2 chạy lại đúng lệnh nhưng quên `--keep` thì nhánh dùng lại bắn trúng chính job đó, lấy transcript xong rồi destroy nó theo luật của [ADR-0003](0003-transcribe-mac-dinh-tu-don.md). Trước tính năng này, lần 2 tạo và dọn một job của riêng nó, job đã giữ vẫn sống. Chấp nhận, vì cho job dùng lại một luật dọn dẹp riêng còn tệ hơn: nó đẻ ra thứ tồn tại trên Soniox mà không lệnh nào của người dùng nói ra. Bù lại, mỗi lần dùng lại đều in sẵn dòng nhắc `--keep` ra stderr.
- **Thêm hai dòng stderr mỗi lần chạy.** Một dòng ref, và khi dùng lại thì một dòng nữa. Cùng lý do với dòng in id ở [ADR-0008](0008-tin-hieu-huy-khong-xoa-du-lieu-tu-xa.md): rẻ, và đổi lại là không bao giờ mất đường về.
