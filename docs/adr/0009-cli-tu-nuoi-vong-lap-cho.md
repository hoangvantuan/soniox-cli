# ADR-0009: CLI tự nuôi vòng lặp chờ

**Trạng thái**: chấp nhận.

## Bối cảnh

`stt transcribe` mặc định đứng chờ tới 600 giây. Suốt quãng đó CLI không phát ra tín hiệu nào: không phân biệt được "đang chạy bình thường" với "đã treo". Với audio dài, thời gian chờ là hàng phút (xem dòng thời gian trong [ADR-0008](0008-tin-hieu-huy-khong-xoa-du-lieu-tu-xa.md)), đủ lâu để người dùng nghi ngờ và giết tiến trình sớm, đúng thứ ADR-0008 vừa phải đi sửa hậu quả.

`client.stt.wait` (`soniox/api/stt.py`) **không nhận callback**, chỉ có `interval_sec` và `timeout_sec`. Không có chỗ nào cắm nhịp báo sống vào.

## Quyết định

Bỏ `client.stt.wait`, CLI tự nuôi vòng lặp chờ trong `wait_for_transcription`:

1. Hỏi `client.stt.get` mỗi 5 giây, bằng mặc định cũ của SDK.
2. Cứ 30 giây in một dòng stderr: id, thời gian đã trôi qua, `status` hiện tại. Nhịp được kiểm ngay sau mỗi lần hỏi, nên 30 giây là mục tiêu chứ không phải bảo đảm.
3. Deadline vẫn là `--timeout`. Khoảng nghỉ luôn bị cắt theo thời gian còn lại, không bao giờ ngủ quá hạn.
4. `httpx.TransportError` (mất mạng, DNS, timeout tầng vận chuyển): thử lại tối đa 5 lần liên tiếp, nghỉ 5/10/20/40/60 giây, đếm lại từ đầu sau mỗi lần hỏi thành công. Quá số đó thì ném lỗi ra.
5. `SonioxError` **không** thử lại.
6. Hết giờ trong lúc mạng đang hỏng thì ném đúng lỗi mạng, không ném `TimeoutError`.
7. Mất kết nối là một **đường bỏ cuộc mới**, nên nó cũng in id kèm lệnh lấy lại kết quả, y như hết giờ và `Ctrl-C`.

## Lý do

**Im lặng không phải là tín hiệu.** Người đứng trước terminal và agent đọc log đều chỉ có một cách phân biệt sống với treo: thấy thứ gì đó nhúc nhích. Một dòng mỗi 30 giây là mức rẻ nhất làm được việc đó.

**Heartbeat phải nằm trong vòng lặp poll.** Có thể đẩy `stt.wait` sang thread rồi đếm nhịp ở thread chính, nhưng thứ đáng giá nhất của heartbeat là `status` hiện tại (`queued` khác `processing`), mà chỉ vòng lặp poll mới biết. Thêm nữa `Ctrl-C` xuyên thread là một lớp rắc rối mới, trong khi ADR-0008 vừa chốt rằng đường hủy phải chắc chắn. Ôm vòng lặp về là đường thuận.

**Thử lại vì job vẫn còn.** Mạng hỏng ở máy local không nói gì về job trên Soniox. Bỏ cuộc ngay lần hỏng đầu là vứt đi thứ còn cứu được, cùng loại sai lầm mà ADR-0008 đã sửa. Ngược lại, `SonioxError` nghĩa là API đã trả lời: hỏi lại một cái 404 năm lần chỉ làm chậm thông báo lỗi. Ranh giới này kiểm chứng được trong SDK: `ensure_success` đổi mọi non-2xx thành `SonioxAPIError`, nên `httpx.HTTPStatusError` không bao giờ lọt tới vòng lặp, và `httpx.TransportError` đúng là lớp "mạng chập chờn".

## Đánh đổi

- **Nợ mới.** Deadline, backoff, phân loại lỗi giờ là code của repo này: phải tự test, tự sửa, và tự đối chiếu khi nâng SDK. Đổi lại, SDK đổi chính sách chờ cũng không lấy mất heartbeat.
- **Thêm dòng stderr.** Một dòng mỗi 30 giây; job 10 phút là 20 dòng. Chấp nhận theo đúng logic ADR-0008: stderr ồn hơn một chút đổi lấy việc không bao giờ mù.
- **Không có cờ tắt heartbeat.** Nhịp 30 giây cố định. Thêm cờ khi có người thật cần, không đoán trước.
- **Thử lại che lỗi mạng thật trong tối đa 135 giây.** Không im lặng: mỗi lần hỏng đều in cảnh báo kèm lần thử thứ mấy.
- **Nhịp 30 giây là mục tiêu, không phải bảo đảm.** Heartbeat nằm trong vòng poll nên một lần hỏi bị treo (SDK để timeout HTTP 30 giây) hoặc một quãng nghỉ backoff dài sẽ giãn khoảng cách ra. Đổi lại không phải nuôi thread riêng, và trong quãng backoff thì chính dòng cảnh báo thử lại đã là tín hiệu sống. `status` in ra cũng là giá trị của lần hỏi thành công gần nhất, không phải giá trị ngay lúc đó.
- **Heartbeat không phải thanh tiến độ.** Soniox không trả phần trăm hoàn thành, nên dòng này chỉ nói "còn sống, đang ở trạng thái này", không nói "còn bao lâu nữa".
