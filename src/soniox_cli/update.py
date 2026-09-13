"""Tự cập nhật `soniox-cli`.

CLI này được cài bằng trình quản lý gói (thường là `uv tool`), nên nó **không
tự cài lại chính mình**: nó nhận diện cách mình được cài rồi gọi đúng lệnh của
trình quản lý đó. Không đoán mò, không tự sửa file trong thư mục cài.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

class UpdateError(RuntimeError):
    """Không cập nhật được. Lỗi dự kiến, không phải bug."""


PACKAGE = "soniox-cli"
REPO_URL = "https://github.com/hoangvantuan/soniox-cli"
RAW_VERSION_URL = (
    "https://raw.githubusercontent.com/hoangvantuan/soniox-cli/main/src/soniox_cli/__init__.py"
)

_VERSION_RE = re.compile(r'__version__\s*=\s*["\']([^"\']+)["\']')
_GIT_RE = re.compile(r'git\s*=\s*"([^"]+)"')
_DIR_RE = re.compile(r'directory\s*=\s*"([^"]+)"')


def parse_version(source: str) -> str | None:
    """Lấy `__version__` ra khỏi nội dung `__init__.py`."""
    m = _VERSION_RE.search(source)
    return m.group(1) if m else None


def version_key(v: str) -> tuple:
    """Khóa so sánh version. Phần không phải số giữ nguyên dạng chuỗi."""
    parts: list = []
    for chunk in re.split(r"[.\-+]", v):
        parts.append((0, int(chunk)) if chunk.isdigit() else (1, chunk))
    return tuple(parts)


def is_newer(latest: str, current: str) -> bool:
    try:
        return version_key(latest) > version_key(current)
    except (TypeError, ValueError):
        return latest != current


def receipt_path() -> Path:
    return Path(sys.prefix) / "uv-receipt.toml"


def read_source() -> tuple[str, str | None]:
    """Nhận diện cách CLI được cài.

    Trả về `(kiểu, chi tiết)`: `("uv-git", url)`, `("uv-dir", đường dẫn)`,
    `("uv", None)` khi là uv tool nhưng không rõ nguồn, hoặc `("unknown", None)`.
    """
    path = receipt_path()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ("unknown", None)
    if m := _GIT_RE.search(text):
        return ("uv-git", m.group(1))
    if m := _DIR_RE.search(text):
        return ("uv-dir", m.group(1))
    return ("uv", None)


def describe_source(kind: str, detail: str | None) -> str:
    if kind == "uv-git":
        return f"uv tool, nguồn git: {detail}"
    if kind == "uv-dir":
        return f"uv tool, nguồn thư mục local: {detail}"
    if kind == "uv":
        return "uv tool"
    return "không nhận ra (không phải uv tool)"


def upgrade_command(force: bool = False) -> list[str]:
    """Lệnh nâng cấp của uv.

    `uv tool upgrade` tự giải lại git ref và lấy commit mới, đã kiểm chứng bằng
    một lần nhảy 0.3.0 -> 0.4.0 trên bản cài thật. Không cần `--reinstall` cho
    trường hợp thường.

    `--reinstall` chỉ dùng cho `--force`: cài lại kể cả khi uv cho rằng đã mới
    nhất và báo "Nothing to upgrade".
    """
    cmd = ["uv", "tool", "upgrade", PACKAGE]
    if force:
        cmd.append("--reinstall")
    return cmd


def manual_instructions(kind: str, detail: str | None) -> str:
    if kind == "uv-dir":
        return (
            f"cài từ thư mục local ({detail}), nên cập nhật bằng:\n"
            f"  git -C {detail} pull\n"
            f"  uv tool install {detail} --reinstall --no-cache"
        )
    return (
        "không nhận ra cách cài. Cài lại từ đầu bằng:\n"
        f"  uv tool install {REPO_URL.replace('https://', 'git+https://')} --force"
    )


def fetch_latest_version(timeout: float = 10.0) -> str:
    """Đọc version trên nhánh `main` của repo. Ném lên lỗi mạng để `run()` dịch."""
    import httpx

    resp = httpx.get(RAW_VERSION_URL, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    latest = parse_version(resp.text)
    if not latest:
        raise UpdateError(f"không đọc được version từ {RAW_VERSION_URL}")
    return latest


def run_upgrade(log, force: bool = False) -> int:
    """Chạy lệnh nâng cấp của uv. Trả về mã thoát của tiến trình con."""
    if not shutil.which("uv"):
        raise UpdateError(
            "không tìm thấy `uv` để nâng cấp.\n"
            "  cài uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
        )
    cmd = upgrade_command(force)
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, check=False).returncode
