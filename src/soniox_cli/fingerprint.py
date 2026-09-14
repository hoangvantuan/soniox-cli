"""Vân tay xác định của đầu vào STT, để sinh `client_reference_id` tái tạo được.

Vấn đề: sau khi mất sạch ngữ cảnh, không có cách nào biết "job này mình đã chạy
rồi". Chạy lại mù nghĩa là upload lại nguyên file và trả tiền phiên âm lại.

Khóa cần tìm phải **tái tạo được** từ chính đầu vào, không cần nhớ gì. Tên file
cộng thời lượng không đủ: hai cuộc họp cùng tên `meeting.mp4` cùng dài 2h40 là
chuyện có thật. Vân tay byte của file thì đủ.

Băm **đầu 1 MB + đuôi 1 MB + kích thước + tên file**, không băm toàn bộ: đọc hết
993 MB mất vài giây mỗi lần chạy, mà phần lớn giá trị phân biệt đã nằm ở header
(codec, thời lượng, timestamp encoder) và ở kích thước. Đánh đổi: sửa byte ở
GIỮA một file lớn mà giữ nguyên kích thước sẽ cho cùng vân tay. Xem ADR-0010.

Model và config STT nằm trong vân tay vì chúng đổi *kết quả*: dịch sang tiếng
khác là job khác, dù cùng audio.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REF_PREFIX = "soniox-cli"

# Đổi khi công thức vân tay đổi: ref cũ và ref mới không được lẫn vào nhau, vì
# chúng trả lời hai câu hỏi khác nhau về cùng một file.
REF_VERSION = "1"

CHUNK_BYTES = 1_048_576   # 1 MB mỗi đầu
REF_DIGEST_CHARS = 32     # 128 bit: dư sức chống trùng ngẫu nhiên, ref vẫn đọc được


def compute_ref(path: Path, *, model: str, config: Any) -> str:
    """Ref xác định cho một lần `stt transcribe` trên file local.

    Cùng file + cùng model + cùng config thì luôn ra cùng chuỗi, trên mọi máy,
    ở mọi phiên.
    """
    size = path.stat().st_size   # một ảnh chụp duy nhất, dùng cho cả hai trường dưới
    material = json.dumps(
        {
            "name": path.name,
            "size": size,
            "bytes": _digest_bytes(path, size),
            "model": model,
            "config": _canonical_config(config),
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:REF_DIGEST_CHARS]
    return f"{REF_PREFIX}:{REF_VERSION}:{digest}"


def is_auto_ref(ref: str | None) -> bool:
    """Ref này có mang ngữ nghĩa danh tính không, hay chỉ là nhãn người dùng tự đặt?

    Tiền tố là thứ duy nhất phân biệt được hai loại. Nhãn tự đặt thì Soniox nói
    rõ "does not need to be unique", nên dò theo nó để dùng lại job là đoán mò.
    """
    return bool(ref) and ref.startswith(f"{REF_PREFIX}:")


def _digest_bytes(path: Path, size: int) -> str:
    """Băm đầu 1 MB và đuôi 1 MB. File nhỏ hơn thì băm trọn, không đọc trùng."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(CHUNK_BYTES))
        if size > CHUNK_BYTES:
            # Chặn dưới ở CHUNK_BYTES: file từ 1 đến 2 MB có đầu và đuôi chồng
            # nhau, đưa phần chồng vào băm hai lần chỉ tốn công chứ không thêm
            # một bit phân biệt nào.
            f.seek(max(size - CHUNK_BYTES, CHUNK_BYTES))
            h.update(f.read(CHUNK_BYTES))
    return h.hexdigest()


def _canonical_config(config: Any) -> str | None:
    """Config STT về dạng chuỗi ổn định: cùng nội dung thì cùng chuỗi.

    `sort_keys` để thứ tự cờ trên dòng lệnh không đổi vân tay.

    `exclude_unset` chứ không phải `exclude_none`: chỉ băm thứ người gọi **thật sự
    đặt**. Một trường mới của SDK mặc định `False` hay `[]` sẽ lọt qua
    `exclude_none` và làm lệch vân tay của **mọi file cũ** mà không ai kịp tăng
    `REF_VERSION`, giết im lặng việc dùng lại. `build_stt_config` chỉ nhồi vào
    model những key được đặt tay, nên `exclude_unset` là ranh giới đúng.
    """
    if config is None:
        return None
    data = (
        config.model_dump(mode="json", exclude_unset=True)
        if hasattr(config, "model_dump")
        else config
    )
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
