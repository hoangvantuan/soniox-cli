"""Test vân tay đầu vào STT: thuần logic, chỉ đọc file trong tmp_path."""

from pathlib import Path

import pytest

from soniox_cli import fingerprint as fp


def _file(tmp_path: Path, name: str, data: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


def _cfg(**kw):
    from soniox.types import CreateTranscriptionConfig

    return CreateTranscriptionConfig(**kw)


# --------------------------------------------------------------------------- #
# Hình dạng ref
# --------------------------------------------------------------------------- #
def test_ref_co_tien_to_va_do_dai_on_dinh(tmp_path):
    ref = fp.compute_ref(_file(tmp_path, "a.mp3", b"x" * 10), model="stt-async-v5", config=None)
    prefix, version, digest = ref.split(":")
    assert (prefix, version) == (fp.REF_PREFIX, fp.REF_VERSION)
    assert len(digest) == 32 and all(c in "0123456789abcdef" for c in digest)
    assert len(ref) <= 256      # trần của client_reference_id phía Soniox


def test_ref_tai_tao_duoc_qua_hai_lan_goi(tmp_path):
    f = _file(tmp_path, "a.mp3", b"noi dung" * 100)
    a = fp.compute_ref(f, model="stt-async-v5", config=None)
    b = fp.compute_ref(f, model="stt-async-v5", config=None)
    assert a == b


def test_is_auto_ref_chi_nhan_ref_do_cli_sinh(tmp_path):
    ref = fp.compute_ref(_file(tmp_path, "a.mp3", b"x"), model="m", config=None)
    assert fp.is_auto_ref(ref) is True
    assert fp.is_auto_ref("hop-2026-09-13") is False
    assert fp.is_auto_ref(None) is False


# --------------------------------------------------------------------------- #
# Thứ làm ref đổi
# --------------------------------------------------------------------------- #
def test_noi_dung_khac_thi_ref_khac(tmp_path):
    a = fp.compute_ref(_file(tmp_path, "a.mp3", b"mot"), model="m", config=None)
    b = fp.compute_ref(_file(tmp_path, "b.mp3", b"hai"), model="m", config=None)
    assert a != b


def test_ten_file_khac_thi_ref_khac(tmp_path):
    data = b"y het nhau"
    a = fp.compute_ref(_file(tmp_path, "hop-a.mp3", data), model="m", config=None)
    b = fp.compute_ref(_file(tmp_path, "hop-b.mp3", data), model="m", config=None)
    assert a != b


def test_model_khac_thi_ref_khac(tmp_path):
    f = _file(tmp_path, "a.mp3", b"x" * 50)
    assert fp.compute_ref(f, model="stt-async-v5", config=None) != fp.compute_ref(
        f, model="stt-async-v4", config=None
    )


def test_config_khac_thi_ref_khac(tmp_path):
    """Dịch sang tiếng khác là job khác, dù cùng audio."""
    f = _file(tmp_path, "a.mp3", b"x" * 50)
    khong = fp.compute_ref(f, model="m", config=None)
    dich = fp.compute_ref(f, model="m", config=_cfg(translation={"type": "one_way", "target_language": "vi"}))
    dich_fr = fp.compute_ref(f, model="m", config=_cfg(translation={"type": "one_way", "target_language": "fr"}))
    assert len({khong, dich, dich_fr}) == 3


def test_config_cung_noi_dung_khac_thu_tu_van_cho_cung_ref(tmp_path):
    f = _file(tmp_path, "a.mp3", b"x" * 50)
    a = fp.compute_ref(f, model="m", config=_cfg(enable_speaker_diarization=True, language_hints=["vi"]))
    b = fp.compute_ref(f, model="m", config=_cfg(language_hints=["vi"], enable_speaker_diarization=True))
    assert a == b


def test_size_khac_thi_ref_khac_du_dau_file_giong_nhau(tmp_path):
    a = fp.compute_ref(_file(tmp_path, "a.mp3", b"x" * 100), model="m", config=None)
    b = fp.compute_ref(_file(tmp_path, "a.mp3", b"x" * 101), model="m", config=None)
    assert a != b


def test_doi_byte_o_duoi_file_thi_ref_khac(tmp_path):
    """Đuôi file nằm trong vân tay: cùng size, cùng đầu file vẫn phân biệt được."""
    n = fp.CHUNK_BYTES
    a = fp.compute_ref(_file(tmp_path, "a.bin", b"h" * n + b"m" * n + b"t" * n), model="m", config=None)
    b = fp.compute_ref(_file(tmp_path, "a.bin", b"h" * n + b"m" * n + b"T" * n), model="m", config=None)
    assert a != b


def test_doi_byte_o_giua_file_lon_thi_ref_KHONG_doi(tmp_path):
    """Đánh đổi có chủ đích: chỉ băm đầu + đuôi để không phải đọc hết file 993 MB."""
    n = fp.CHUNK_BYTES
    a = fp.compute_ref(_file(tmp_path, "a.bin", b"h" * n + b"m" * n + b"t" * n), model="m", config=None)
    b = fp.compute_ref(_file(tmp_path, "a.bin", b"h" * n + b"M" * n + b"t" * n), model="m", config=None)
    assert a == b


# --------------------------------------------------------------------------- #
# Biên của phần đọc byte
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "size", [0, 1, fp.CHUNK_BYTES - 1, fp.CHUNK_BYTES, fp.CHUNK_BYTES + 1, 2 * fp.CHUNK_BYTES + 5]
)
def test_moi_co_file_deu_bam_duoc(tmp_path, size):
    ref = fp.compute_ref(_file(tmp_path, "a.bin", b"z" * size), model="m", config=None)
    assert fp.is_auto_ref(ref)


def test_file_nho_hon_mot_chunk_khong_bam_trung_phan_dau(tmp_path):
    """Đầu và đuôi chồng nhau ở file nhỏ: mỗi byte chỉ được đưa vào băm một lần."""
    n = fp.CHUNK_BYTES
    a = fp.compute_ref(_file(tmp_path, "a.bin", b"a" * (n + 10)), model="m", config=None)
    b = fp.compute_ref(_file(tmp_path, "a.bin", b"a" * n + b"b" * 10), model="m", config=None)
    assert a != b


# --------------------------------------------------------------------------- #
# Ranh giới với SDK: trường mới không được đổi vân tay của file cũ
# --------------------------------------------------------------------------- #
def test_chi_bam_truong_nguoi_goi_that_su_dat():
    """`exclude_unset`, không phải `exclude_none`.

    Trường mới của SDK mặc định `False` hay `[]` mà lọt vào vân tay thì mọi ref
    cũ đổi hết trong im lặng, và việc dùng lại chết mà không ai biết.
    """
    assert fp._canonical_config(_cfg(language_hints=["vi"])) == '{"language_hints":["vi"]}'


def test_config_rong_khac_khong_co_config():
    """`CreateTranscriptionConfig()` rỗng vẫn là một lựa chọn, không phải là 'không đặt gì'."""
    assert fp._canonical_config(None) is None
    assert fp._canonical_config(_cfg()) == "{}"
