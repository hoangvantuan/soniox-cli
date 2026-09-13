"""Test chuẩn bị file trước upload. Không gọi ffmpeg thật: subprocess bị thay."""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from soniox_cli import media


# --------------------------------------------------------------------------- #
# Nhận diện đuôi file
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", ["a.mp3", "a.WAV", "a.flac", "a.m4a", "a.opus", "a.amr"])
def test_duoi_audio_thi_khong_can_dung_toi_ffmpeg(name):
    assert media.looks_like_audio(Path(name)) is True


@pytest.mark.parametrize("name", ["a.mp4", "a.mkv", "a.mov", "a.webm", "a", "a.bin"])
def test_duoi_khong_chac_la_audio(name):
    assert media.looks_like_audio(Path(name)) is False


# --------------------------------------------------------------------------- #
# probe_streams
# --------------------------------------------------------------------------- #
def _fake_run(stdout="", returncode=0, raises=None):
    def run(cmd, **kw):
        if raises:
            raise raises
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")
    return run


def test_probe_doc_duoc_luong(monkeypatch):
    payload = json.dumps({"streams": [{"codec_type": "audio", "codec_name": "aac"}]})
    monkeypatch.setattr(subprocess, "run", _fake_run(stdout=payload))
    assert media.probe_streams(Path("a.mp4"))[0]["codec_name"] == "aac"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"returncode": 1},                       # ffprobe lỗi
        {"stdout": "khong-phai-json"},           # output hỏng
        {"raises": OSError("khong tim thay")},   # ffprobe không tồn tại
    ],
)
def test_probe_hong_thi_tra_ve_rong_chu_khong_no(monkeypatch, kwargs):
    monkeypatch.setattr(subprocess, "run", _fake_run(**kwargs))
    assert media.probe_streams(Path("a.mp4")) == []


# --------------------------------------------------------------------------- #
# Chọn container theo codec
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "codec,suffix,che_do",
    [
        ("aac", ".m4a", "copy"),
        ("mp3", ".mp3", "copy"),
        ("opus", ".ogg", "copy"),
        ("pcm_s16le", ".wav", "copy"),
        ("ac3", ".m4a", "encode"),      # codec lạ -> mã hóa lại
        (None, ".m4a", "encode"),
    ],
)
def test_codec_quyet_dinh_container_va_copy_hay_ma_hoa(monkeypatch, tmp_path, codec, suffix, che_do):
    seen = {}

    def run(cmd, **kw):
        seen["cmd"] = cmd
        Path(cmd[-1]).write_bytes(b"x" * 10)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    src = tmp_path / "phim.mp4"
    src.write_bytes(b"v" * 100)
    dest = media.extract_audio(src, tmp_path, codec)

    assert dest.suffix == suffix
    assert ("-c:a" in seen["cmd"]) and ("copy" in seen["cmd"]) == (che_do == "copy")
    assert "-vn" in seen["cmd"]          # luôn bỏ luồng hình


def test_extract_that_bai_thi_bao_loi_ro(monkeypatch, tmp_path):
    def run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Invalid data found")

    monkeypatch.setattr(subprocess, "run", run)
    src = tmp_path / "hong.mp4"
    src.write_bytes(b"x")
    with pytest.raises(media.MediaError, match="Invalid data found"):
        media.extract_audio(src, tmp_path, "aac")


def test_extract_ra_file_rong_cung_la_that_bai(monkeypatch, tmp_path):
    def run(cmd, **kw):
        Path(cmd[-1]).write_bytes(b"")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x")
    with pytest.raises(media.MediaError):
        media.extract_audio(src, tmp_path, "aac")


# --------------------------------------------------------------------------- #
# prepared_upload
# --------------------------------------------------------------------------- #
def test_file_audio_di_thang_khong_dung_ffmpeg(tmp_path, monkeypatch):
    def no_call(*a, **k):
        raise AssertionError("không được gọi ffmpeg cho file audio")

    monkeypatch.setattr(subprocess, "run", no_call)
    src = tmp_path / "a.mp3"
    src.write_bytes(b"x")
    with media.prepared_upload(src) as ready:
        assert ready == src


def test_no_extract_thi_upload_nguyen_file(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("không được gọi"))
    src = tmp_path / "phim.mp4"
    src.write_bytes(b"x")
    with media.prepared_upload(src, extract=False) as ready:
        assert ready == src


def test_thieu_ffmpeg_thi_bao_loi_kem_cach_xu_ly(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "have_ffmpeg", lambda: False)
    src = tmp_path / "phim.mp4"
    src.write_bytes(b"x")
    with pytest.raises(media.MediaError, match="--no-extract-audio"):
        with media.prepared_upload(src):
            pass


def _fake_video(monkeypatch, tmp_path, *, streams, extracted=b"audio-nho"):
    monkeypatch.setattr(media, "have_ffmpeg", lambda: True)
    monkeypatch.setattr(media, "probe_streams", lambda p: streams)
    # Không để test rải thư mục tạm vào temp của hệ thống, kể cả nhánh keep=True.
    sandbox = tmp_path / "tmpdirs"
    sandbox.mkdir(exist_ok=True)
    real_mkdtemp = tempfile.mkdtemp
    monkeypatch.setattr(
        media.tempfile, "mkdtemp",
        lambda prefix="", **kw: real_mkdtemp(prefix=prefix, dir=str(sandbox)),
    )

    def run(cmd, **kw):
        Path(cmd[-1]).write_bytes(extracted)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    src = tmp_path / "phim.mp4"
    src.write_bytes(b"v" * 5000)
    return src


def test_video_thi_tach_audio_va_don_file_tam(tmp_path, monkeypatch):
    src = _fake_video(
        monkeypatch, tmp_path,
        streams=[{"codec_type": "video", "codec_name": "h264"},
                 {"codec_type": "audio", "codec_name": "aac"}],
    )
    with media.prepared_upload(src) as ready:
        assert ready != src
        assert ready.exists()
        assert ready.read_bytes() == b"audio-nho"
        tmp_dir = ready.parent
    assert not tmp_dir.exists()          # dọn sạch sau khi ra khỏi khối


def test_keep_giu_lai_file_tam(tmp_path, monkeypatch):
    src = _fake_video(
        monkeypatch, tmp_path,
        streams=[{"codec_type": "video", "codec_name": "h264"},
                 {"codec_type": "audio", "codec_name": "aac"}],
    )
    with media.prepared_upload(src, keep=True) as ready:
        kept = ready
    assert kept.exists()


def test_don_file_tam_ca_khi_co_loi(tmp_path, monkeypatch):
    src = _fake_video(
        monkeypatch, tmp_path,
        streams=[{"codec_type": "video", "codec_name": "h264"},
                 {"codec_type": "audio", "codec_name": "aac"}],
    )
    tmp_dir = None
    with pytest.raises(RuntimeError, match="loi gia"):
        with media.prepared_upload(src) as ready:
            tmp_dir = ready.parent
            raise RuntimeError("loi gia")
    assert tmp_dir is not None and not tmp_dir.exists()


def test_file_khong_co_luong_hinh_thi_upload_thang(tmp_path, monkeypatch):
    src = _fake_video(
        monkeypatch, tmp_path, streams=[{"codec_type": "audio", "codec_name": "aac"}]
    )
    with media.prepared_upload(src) as ready:
        assert ready == src


def test_anh_bia_khong_bi_coi_la_video(tmp_path, monkeypatch):
    """mp3 có ảnh bìa mang luồng mjpeg: đó không phải video."""
    src = _fake_video(
        monkeypatch, tmp_path,
        streams=[{"codec_type": "video", "codec_name": "mjpeg"},
                 {"codec_type": "audio", "codec_name": "mp3"}],
    )
    with media.prepared_upload(src) as ready:
        assert ready == src


def test_video_khong_co_audio_thi_bao_loi(tmp_path, monkeypatch):
    src = _fake_video(
        monkeypatch, tmp_path, streams=[{"codec_type": "video", "codec_name": "h264"}]
    )
    with pytest.raises(media.MediaError, match="không có luồng audio"):
        with media.prepared_upload(src):
            pass


def test_test_khong_de_lai_rac_trong_temp_he_thong(tmp_path, monkeypatch):
    """Chốt chặn: nhánh keep=True phải nằm trong sandbox của test."""
    src = _fake_video(
        monkeypatch, tmp_path,
        streams=[{"codec_type": "video", "codec_name": "h264"},
                 {"codec_type": "audio", "codec_name": "aac"}],
    )
    with media.prepared_upload(src, keep=True) as ready:
        assert tmp_path in ready.parents
