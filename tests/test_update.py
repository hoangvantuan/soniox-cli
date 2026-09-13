"""Test tự cập nhật. Không chạm mạng, không gọi uv thật."""

import subprocess
from pathlib import Path

import pytest

from soniox_cli import update as U


# --------------------------------------------------------------------------- #
# parse_version
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "source,expected",
    [
        ('__version__ = "1.2.3"', "1.2.3"),
        ("__version__='0.1.0'", "0.1.0"),
        ('"""doc"""\n\n__version__ = "2.0.0rc1"\n', "2.0.0rc1"),
        ("khong co version o day", None),
    ],
)
def test_parse_version(source, expected):
    assert U.parse_version(source) == expected


# --------------------------------------------------------------------------- #
# So sánh version
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "latest,current,moi_hon",
    [
        ("0.3.0", "0.2.0", True),
        ("0.2.0", "0.3.0", False),
        ("0.3.0", "0.3.0", False),
        ("0.10.0", "0.9.0", True),     # so theo số, không theo chuỗi
        ("1.0.0", "0.99.99", True),
    ],
)
def test_is_newer(latest, current, moi_hon):
    assert U.is_newer(latest, current) is moi_hon


def test_is_newer_chiu_duoc_version_khong_chuan():
    assert U.is_newer("banh-mi", "0.1.0") is True      # khác nhau thì coi là mới
    assert U.is_newer("0.1.0", "0.1.0") is False


# --------------------------------------------------------------------------- #
# Nhận diện cách cài
# --------------------------------------------------------------------------- #
def _receipt(monkeypatch, tmp_path, text):
    p = tmp_path / "uv-receipt.toml"
    if text is not None:
        p.write_text(text, encoding="utf-8")
    monkeypatch.setattr(U, "receipt_path", lambda: p)


def test_nhan_dien_nguon_git(monkeypatch, tmp_path):
    _receipt(monkeypatch, tmp_path, """[tool]
requirements = [{ name = "soniox-cli", git = "https://github.com/hoangvantuan/soniox-cli" }]
""")
    assert U.read_source() == ("uv-git", "https://github.com/hoangvantuan/soniox-cli")


def test_nhan_dien_nguon_thu_muc(monkeypatch, tmp_path):
    _receipt(monkeypatch, tmp_path, """[tool]
requirements = [{ name = "soniox-cli", directory = "/home/toi/soniox-cli" }]
""")
    assert U.read_source() == ("uv-dir", "/home/toi/soniox-cli")


def test_uv_tool_nhung_khong_ro_nguon(monkeypatch, tmp_path):
    _receipt(monkeypatch, tmp_path, '[tool]\nrequirements = [{ name = "soniox-cli" }]\n')
    assert U.read_source() == ("uv", None)


def test_khong_co_receipt_thi_khong_nhan_ra(monkeypatch, tmp_path):
    _receipt(monkeypatch, tmp_path, None)
    assert U.read_source() == ("unknown", None)


@pytest.mark.parametrize(
    "kind,detail,phai_chua",
    [
        ("uv-git", "https://x/y", "git"),
        ("uv-dir", "/tmp/repo", "/tmp/repo"),
        ("uv", None, "uv tool"),
        ("unknown", None, "không nhận ra"),
    ],
)
def test_describe_source(kind, detail, phai_chua):
    assert phai_chua in U.describe_source(kind, detail)


# --------------------------------------------------------------------------- #
# Lệnh nâng cấp
# --------------------------------------------------------------------------- #
def test_lenh_nang_cap_luon_kem_reinstall():
    """Thiếu --reinstall thì uv báo 'Nothing to upgrade' và bỏ qua commit mới."""
    cmd = U.upgrade_command()
    assert cmd[:4] == ["uv", "tool", "upgrade", "soniox-cli"]
    assert "--reinstall" in cmd


def test_nguon_thu_muc_thi_huong_dan_git_pull():
    text = U.manual_instructions("uv-dir", "/home/toi/soniox-cli")
    assert "git -C /home/toi/soniox-cli pull" in text
    assert "--no-cache" in text


def test_khong_nhan_ra_thi_huong_dan_cai_lai_tu_github():
    assert "git+https://github.com/" in U.manual_instructions("unknown", None)


def test_thieu_uv_thi_bao_loi_kem_cach_cai(monkeypatch):
    monkeypatch.setattr(U.shutil, "which", lambda _: None)
    with pytest.raises(U.UpdateError, match="astral.sh/uv"):
        U.run_upgrade(lambda _m: None)


def test_run_upgrade_tra_ve_ma_thoat(monkeypatch):
    monkeypatch.setattr(U.shutil, "which", lambda _: "/usr/bin/uv")
    monkeypatch.setattr(
        subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 3)
    )
    assert U.run_upgrade(lambda _m: None) == 3


# --------------------------------------------------------------------------- #
# fetch_latest_version
# --------------------------------------------------------------------------- #
class _FakeResp:
    """httpx.Response thật cần gắn request mới gọi được raise_for_status."""

    def __init__(self, text, status=200):
        self.text, self.status_code = text, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_fetch_doc_duoc_version(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResp('__version__ = "9.9.9"'))
    assert U.fetch_latest_version() == "9.9.9"


def test_fetch_khong_thay_version_thi_bao_loi(monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResp("rong"))
    with pytest.raises(U.UpdateError, match="không đọc được version"):
        U.fetch_latest_version()


def test_UpdateError_la_loi_du_kien_khong_phai_bug():
    assert issubclass(U.UpdateError, RuntimeError)
