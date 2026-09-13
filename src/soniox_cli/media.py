"""Chuẩn bị file trước khi upload lên Soniox.

Soniox nhận cả container video (`mp4`, `webm`, `asf`), nên upload thẳng video
vẫn chạy: chỉ là tốn băng thông và thời gian cho một luồng hình mà STT không
dùng tới. Module này tách luồng audio ra trước, ưu tiên **copy nguyên luồng**
(không giải mã lại, không mất chất lượng), và chỉ mã hóa lại khi codec gốc
không nằm trong danh sách Soniox nhận.

File tách ra nằm trong thư mục tạm của hệ thống và bị xóa sau khi dùng xong.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

# Đuôi chắc chắn là audio: khỏi cần gọi ffprobe cho trường hợp phổ biến nhất.
AUDIO_SUFFIXES = frozenset(
    {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".oga", ".opus",
     ".aiff", ".aif", ".amr", ".wma", ".weba"}
)

# Codec Soniox đọc được -> container chứa nó. Copy thẳng, không mã hóa lại.
_CODEC_TO_SUFFIX = {
    "aac": ".m4a",
    "mp3": ".mp3",
    "flac": ".flac",
    "opus": ".ogg",
    "vorbis": ".ogg",
    "amrnb": ".amr",
    "amr_nb": ".amr",
    "pcm_s16le": ".wav",
    "pcm_s24le": ".wav",
    "pcm_s32le": ".wav",
    "pcm_f32le": ".wav",
    "pcm_u8": ".wav",
}

# Codec lạ (ac3, dts, wmav2, alac...) thì mã hóa lại sang AAC: bộ mã hóa aac có
# sẵn trong mọi bản ffmpeg, không cần thư viện ngoài, và Soniox nhận m4a.
_FALLBACK_SUFFIX = ".m4a"
_FALLBACK_ARGS = ["-c:a", "aac", "-b:a", "96k"]


class MediaError(RuntimeError):
    """Không chuẩn bị được file để upload."""


def have_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def looks_like_audio(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_SUFFIXES


def probe_streams(path: Path) -> list[dict]:
    """Danh sách luồng của file. Rỗng nếu ffprobe không đọc được."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=index,codec_type,codec_name", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    try:
        return json.loads(out.stdout).get("streams") or []
    except json.JSONDecodeError:
        return []


def _kinds(streams: list[dict]) -> tuple[bool, str | None]:
    has_video = any(
        s.get("codec_type") == "video" and s.get("codec_name") not in ("mjpeg", "png", "bmp")
        for s in streams
    )
    audio_codec = next(
        (s.get("codec_name") for s in streams if s.get("codec_type") == "audio"), None
    )
    return has_video, audio_codec


def extract_audio(src: Path, dest_dir: Path, audio_codec: str | None) -> Path:
    """Tách luồng audio ra file riêng trong `dest_dir`."""
    suffix = _CODEC_TO_SUFFIX.get((audio_codec or "").lower())
    if suffix:
        args, mode = ["-c:a", "copy"], "copy"
    else:
        suffix, args, mode = _FALLBACK_SUFFIX, _FALLBACK_ARGS, "encode"
    dest = dest_dir / (src.stem + suffix)

    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-map", "0:a:0", *args, str(dest)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        detail = (proc.stderr or "").strip().splitlines()
        raise MediaError(
            f"ffmpeg không tách được audio từ '{src.name}'"
            + (f": {detail[-1]}" if detail else "")
        )
    return dest


@contextmanager
def prepared_upload(path: Path, *, extract: bool = True, keep: bool = False, log=None):
    """Trả về đường dẫn nên upload, dọn file tạm khi ra khỏi khối `with`.

    File audio đi thẳng. File có luồng hình thì tách audio ra thư mục tạm.
    `keep=True` giữ lại file tạm và cho biết nó nằm ở đâu.
    """
    def say(msg: str) -> None:
        if log:
            log(msg)

    if not extract or looks_like_audio(path):
        yield path
        return

    if not have_ffmpeg():
        raise MediaError(
            f"'{path.name}' có thể là video nhưng không tìm thấy ffmpeg để tách audio.\n"
            f"  cài ffmpeg (macOS: brew install ffmpeg), hoặc\n"
            f"  dùng --no-extract-audio để upload nguyên file"
        )

    has_video, audio_codec = _kinds(probe_streams(path))
    if not has_video:
        yield path
        return
    if audio_codec is None:
        raise MediaError(f"'{path.name}' không có luồng audio nào để phiên âm")

    tmp_dir = Path(tempfile.mkdtemp(prefix="soniox-"))
    try:
        say(f"tách audio khỏi video ({audio_codec}) trước khi upload...")
        dest = extract_audio(path, tmp_dir, audio_codec)
        before, after = path.stat().st_size, dest.stat().st_size
        say(f"upload {_mb(after)} thay vì {_mb(before)} ({dest.name})")
        if keep:
            say(f"giữ lại file tách: {dest}")
        yield dest
    finally:
        if not keep:
            shutil.rmtree(tmp_dir, ignore_errors=True)


def _mb(n: int) -> str:
    return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{n / 1024:.0f} KB"
