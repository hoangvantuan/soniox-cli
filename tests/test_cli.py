"""Test cho phần logic thuần của CLI: không chạm mạng, không cần API key."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from soniox_cli.cli import (
    build_parser,
    build_stt_config,
    fmt_from_output,
    format_transcript_text,
    parse_translate,
    resolve_audio_input,
    wants_json,
)


def tok(text, *, speaker=None, translation_status=None, language=None):
    return SimpleNamespace(
        text=text, speaker=speaker, translation_status=translation_status, language=language
    )


# --------------------------------------------------------------------------- #
# parse_translate
# --------------------------------------------------------------------------- #
def test_parse_translate_one_way():
    assert parse_translate("fr") == {"type": "one_way", "target_language": "fr"}


@pytest.mark.parametrize("spec", ["two-way:en,vi", "two_way:en, vi"])
def test_parse_translate_two_way(spec):
    assert parse_translate(spec) == {"type": "two_way", "language_a": "en", "language_b": "vi"}


@pytest.mark.parametrize("spec", ["two-way:en", "two-way:en,vi,fr", "two-way:"])
def test_parse_translate_two_way_sai_so_ngon_ngu(spec):
    with pytest.raises(SystemExit):
        parse_translate(spec)


# --------------------------------------------------------------------------- #
# build_stt_config
# --------------------------------------------------------------------------- #
def _stt_args(**kw):
    base = dict(
        language_hints=None, diarize=False, context=None, translate=None, config_json=None
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_build_stt_config_rong_tra_ve_none():
    assert build_stt_config(_stt_args()) is None


def test_build_stt_config_gop_co():
    cfg = build_stt_config(_stt_args(language_hints="vi, en ,", diarize=True, context="y tế"))
    assert cfg.language_hints == ["vi", "en"]
    assert cfg.enable_speaker_diarization is True
    assert cfg.context.text == "y tế"


def test_build_stt_config_translate_bat_language_identification():
    cfg = build_stt_config(_stt_args(translate="vi"))
    assert cfg.enable_language_identification is True


def test_build_stt_config_json_khong_hop_le():
    with pytest.raises(SystemExit):
        build_stt_config(_stt_args(config_json="{khong phai json}"))


def test_build_stt_config_json_phai_la_object():
    with pytest.raises(SystemExit):
        build_stt_config(_stt_args(config_json='["mang"]'))


def test_build_stt_config_truong_la_bi_tu_choi():
    with pytest.raises(SystemExit):
        build_stt_config(_stt_args(config_json='{"khong_ton_tai": 1}'))


# --------------------------------------------------------------------------- #
# fmt_from_output
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name,expected", [("a.wav", "wav"), ("a.MP3", "mp3"), ("a.pcm", "pcm_s16le")]
)
def test_fmt_tu_duoi_file(name, expected):
    assert fmt_from_output(Path(name), None) == expected


@pytest.mark.parametrize("name", ["a.ogg", "a.m4a", "khong_co_duoi"])
def test_fmt_duoi_la_bao_loi_thay_vi_am_tham_wav(name):
    with pytest.raises(SystemExit):
        fmt_from_output(Path(name), None)


def test_fmt_override_hop_le_thang_duoi_file():
    assert fmt_from_output(Path("a.bin"), "flac") == "flac"


def test_fmt_override_khong_hop_le():
    with pytest.raises(SystemExit):
        fmt_from_output(Path("a.wav"), "vorbis")


# --------------------------------------------------------------------------- #
# resolve_audio_input
# --------------------------------------------------------------------------- #
def test_resolve_url():
    args = SimpleNamespace(file_id=None, input="https://x/a.mp3")
    assert resolve_audio_input(args) == {"audio_url": "https://x/a.mp3"}


def test_resolve_file_local(tmp_path):
    f = tmp_path / "a.mp3"
    f.write_bytes(b"x")
    args = SimpleNamespace(file_id=None, input=str(f))
    assert resolve_audio_input(args) == {"file": str(f)}


def test_resolve_file_id():
    assert resolve_audio_input(SimpleNamespace(file_id="f1", input=None)) == {"file_id": "f1"}


def test_resolve_file_id_va_input_cung_luc_la_loi():
    with pytest.raises(SystemExit):
        resolve_audio_input(SimpleNamespace(file_id="f1", input="a.mp3"))


@pytest.mark.parametrize("value", [None, "khong/ton/tai.mp3"])
def test_resolve_dau_vao_khong_hop_le(value):
    with pytest.raises(SystemExit):
        resolve_audio_input(SimpleNamespace(file_id=None, input=value))


# --------------------------------------------------------------------------- #
# format_transcript_text
# --------------------------------------------------------------------------- #
def test_format_khong_co_gi_dac_biet_dung_text_san():
    tr = SimpleNamespace(text="xin chào", tokens=[])
    assert format_transcript_text(tr, diarize=False) == "xin chào"


def test_format_diarize_gop_theo_speaker():
    tr = SimpleNamespace(
        text="bỏ qua",
        tokens=[tok("a ", speaker=1), tok("b", speaker=1), tok("c", speaker=2)],
    )
    assert format_transcript_text(tr, diarize=True) == "Speaker 1: a b\nSpeaker 2: c"


def test_format_co_token_speaker_nhung_khong_bat_diarize_thi_dung_text_san():
    tr = SimpleNamespace(text="nguyên bản", tokens=[tok("a", speaker=1)])
    assert format_transcript_text(tr, diarize=False) == "nguyên bản"


def test_format_translation_xen_ke_goc_va_ban_dich():
    tr = SimpleNamespace(
        text="hello",
        tokens=[
            tok("hello", translation_status="original"),
            tok("xin chào", translation_status="translation", language="vi"),
        ],
    )
    assert format_transcript_text(tr, diarize=False) == "hello\n→ vi: xin chào"


def test_format_translation_kem_speaker():
    tr = SimpleNamespace(
        text="hi",
        tokens=[
            tok("hi", speaker=1, translation_status="original"),
            tok("chào", speaker=1, translation_status="translation", language="vi"),
        ],
    )
    out = format_transcript_text(tr, diarize=True)
    assert out == "[Speaker 1] hi\n[Speaker 1] → vi: chào"


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "argv,expected",
    [
        (["--json", "stt", "list"], True),   # cờ toàn cục không bị subparser nuốt
        (["stt", "list", "--json"], True),
        (["stt", "list"], False),
        (["--json", "files", "list"], True),
        (["--json", "voices", "list"], True),
        (["--json", "auth", "check"], True),
    ],
)
def test_co_json_o_ca_hai_vi_tri(argv, expected):
    assert wants_json(build_parser().parse_args(argv)) is expected


def test_moi_subcommand_deu_gan_func():
    p = build_parser()
    for argv in (
        ["stt", "transcribe", "a.mp3"],
        ["stt", "get", "i"],
        ["stt", "list"],
        ["stt", "transcript", "i"],
        ["stt", "delete", "i"],
        ["stt", "count"],
        ["stt", "delete-all"],
        ["files", "upload", "a"],
        ["files", "list"],
        ["files", "get", "i"],
        ["files", "delete", "i"],
        ["files", "count"],
        ["files", "delete-all"],
        ["tts", "generate", "x", "-o", "o.wav"],
        ["voices", "list"],
        ["voices", "create", "a.wav", "--name", "n"],
        ["voices", "delete", "i"],
        ["voices", "get", "i"],
        ["voices", "count"],
        ["voices", "recompute", "i"],
        ["concurrency"],
        ["models"],
        ["usage"],
        ["auth", "check"],
    ):
        assert callable(p.parse_args(argv).func), argv


def test_thieu_subcommand_thi_loi():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


# --------------------------------------------------------------------------- #
# reject_unknown_keys
# --------------------------------------------------------------------------- #
def test_reject_unknown_keys_chan_key_la():
    from soniox.types import CreateTranscriptionConfig

    from soniox_cli.cli import reject_unknown_keys

    with pytest.raises(SystemExit):
        reject_unknown_keys({"khong_ton_tai": 1}, CreateTranscriptionConfig, "--config-json")


def test_reject_unknown_keys_cho_key_dung_di_qua():
    from soniox.types import CreateTranscriptionConfig

    from soniox_cli.cli import reject_unknown_keys

    reject_unknown_keys({"language_hints": ["vi"]}, CreateTranscriptionConfig, "--config-json")


def test_config_json_stt_truong_la_bi_tu_choi():
    # `language_hint` thiếu chữ s: pydantic vốn bỏ im lặng, CLI phải chặn.
    with pytest.raises(SystemExit):
        build_stt_config(_stt_args(config_json='{"language_hint": ["vi"]}'))


def test_config_json_stt_truong_dung_duoc_gop_vao():
    cfg = build_stt_config(_stt_args(config_json='{"enable_language_identification": true}'))
    assert cfg.enable_language_identification is True


def test_config_json_tts_khong_bi_loc_theo_model_sdk(tmp_path, monkeypatch):
    """Payload TTS đi thẳng API: trường SDK chưa biết vẫn phải lọt qua.

    Lọc theo model của SDK sẽ chặn oan, ví dụ `speed` không có trong
    CreateTtsPayload của soniox 2.3.2, hay `reduce_silence` chỉ có từ 2.9.0.
    """
    import soniox_cli.cli as cli

    sent: dict = {}
    out = tmp_path / "o.wav"

    class FakeResp:
        status_code = 200
        content = b"RIFF"

    class FakeClient:
        tts_api_base_url = "https://tts.test"

        def request(self, method, url, *, json=None, **kw):
            sent.update(json)
            return FakeResp()

    monkeypatch.setattr(cli, "get_client", lambda: FakeClient())
    args = build_parser().parse_args(
        ["tts", "generate", "xin chào", "-o", str(out),
         "--config-json", '{"reduce_silence": true}']
    )
    cli.cmd_tts_generate(args)

    assert sent["reduce_silence"] is True   # trường SDK cũ không biết vẫn đi qua
    assert sent["text"] == "xin chào"
    assert sent["audio_format"] == "wav"
    assert out.read_bytes() == b"RIFF"


# --------------------------------------------------------------------------- #
# Phụ đề ở tầng CLI
# --------------------------------------------------------------------------- #
def test_no_wait_khong_di_cung_subtitles():
    import soniox_cli.cli as cli

    args = build_parser().parse_args(
        ["stt", "transcribe", "https://x/a.mp3", "--no-wait", "--subtitles", "srt"]
    )
    with pytest.raises(SystemExit):
        cli.cmd_stt_transcribe(args)


def test_subtitle_track_mac_dinh_la_auto():
    args = build_parser().parse_args(["stt", "transcribe", "a.mp3", "--subtitles", "vtt"])
    assert args.subtitle_track == "auto"
    assert args.subtitles == "vtt"


def test_transcript_ho_tro_phu_de_va_ghi_ra_file(tmp_path, monkeypatch):
    import soniox_cli.cli as cli

    out = tmp_path / "phu-de.srt"
    transcript = SimpleNamespace(
        text="Xin chào.",
        tokens=[{"text": "Xin chào.", "start_ms": 0, "end_ms": 1500, "speaker": None}],
    )

    class FakeStt:
        def get_transcript(self, _id):
            return transcript

    monkeypatch.setattr(cli, "get_client", lambda: SimpleNamespace(stt=FakeStt()))
    args = build_parser().parse_args(
        ["stt", "transcript", "abc", "--subtitles", "srt", "-o", str(out)]
    )
    cli.cmd_stt_transcript(args)

    assert out.read_text(encoding="utf-8") == "1\n00:00:00,000 --> 00:00:01,500\nXin chào.\n"


def test_transcript_khong_co_token_thi_bao_loi(monkeypatch):
    import soniox_cli.cli as cli

    class FakeStt:
        def get_transcript(self, _id):
            return SimpleNamespace(text="x", tokens=[])

    monkeypatch.setattr(cli, "get_client", lambda: SimpleNamespace(stt=FakeStt()))
    args = build_parser().parse_args(["stt", "transcript", "abc", "--subtitles", "srt"])
    with pytest.raises(SystemExit):
        cli.cmd_stt_transcript(args)


# --------------------------------------------------------------------------- #
# diarization_on: nhận cả escape hatch
# --------------------------------------------------------------------------- #
def test_diarization_on_nhan_ca_config_json():
    from soniox_cli.cli import diarization_on

    cfg = build_stt_config(_stt_args(config_json='{"enable_speaker_diarization": true}'))
    assert diarization_on(_stt_args(), cfg) is True


def test_diarization_on_nhan_co_diarize():
    from soniox_cli.cli import diarization_on

    assert diarization_on(_stt_args(diarize=True), None) is True


def test_diarization_off_khi_khong_bat_gi():
    from soniox_cli.cli import diarization_on

    assert diarization_on(_stt_args(), None) is False


# --------------------------------------------------------------------------- #
# Xóa hàng loạt phải có --yes
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "argv,cmd", [(["stt", "delete-all"], "cmd_stt_delete_all"), (["files", "delete-all"], "cmd_files_delete_all")]
)
def test_delete_all_khong_co_yes_thi_tu_choi(argv, cmd, monkeypatch):
    import soniox_cli.cli as cli

    monkeypatch.setattr(cli, "get_client", lambda: object())
    monkeypatch.setattr(cli, "_request_json", lambda *a, **k: {"total": 7})
    with pytest.raises(SystemExit):
        getattr(cli, cmd)(build_parser().parse_args(argv))


def test_delete_all_khi_rong_thi_khong_can_yes(monkeypatch, capsys):
    import soniox_cli.cli as cli

    monkeypatch.setattr(cli, "get_client", lambda: object())
    monkeypatch.setattr(cli, "_request_json", lambda *a, **k: {"total": 0})
    cli.cmd_stt_delete_all(build_parser().parse_args(["stt", "delete-all"]))
    assert "không có transcription nào" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Tổng hợp usage
# --------------------------------------------------------------------------- #
def test_usage_summary_gop_theo_model():
    from soniox_cli.cli import _usage_summary

    out = _usage_summary(
        [
            {"model": "stt-async-v5", "input_audio_duration_ms": 60_000, "cost_usd": 0.10},
            {"model": "stt-async-v5", "input_audio_duration_ms": 30_000, "cost_usd": 0.05},
            {"model": "tts-rt-v1", "output_audio_duration_ms": 5_000, "cost_usd": 0.01},
        ],
        "A",
        "B",
    )
    assert "stt-async-v5" in out and "tts-rt-v1" in out
    assert "1m30s" in out          # 90 giây audio gộp lại
    assert "0.1600" in out         # tổng chi phí
    assert out.count("\n") > 4     # dạng bảng, không phải JSON thô


def test_usage_summary_rong():
    from soniox_cli.cli import _usage_summary

    assert "không có bản ghi usage" in _usage_summary([], "A", "B")


def test_usage_summary_chiu_duoc_cost_dang_chuoi():
    """API trả `cost_usd` là chuỗi, không phải số."""
    from soniox_cli.cli import _usage_summary

    out = _usage_summary(
        [{"model": "m", "input_audio_duration_ms": "1000", "cost_usd": "0.1956645000"}], "A", "B"
    )
    assert "0.1957" in out


def test_usage_summary_bo_qua_gia_tri_rac():
    from soniox_cli.cli import _usage_summary

    out = _usage_summary([{"model": "m", "cost_usd": "khong-phai-so"}], "A", "B")
    assert "0.0000" in out


# --------------------------------------------------------------------------- #
# Voices
# --------------------------------------------------------------------------- #
def test_voice_models_la_danh_sach_dict_khong_phai_chuoi():
    from soniox_cli.cli import _voice_models

    out = _voice_models([{"model": "tts-rt-v1", "status": "ready"}, {"model": "tts-rt-v2"}])
    assert out == "tts-rt-v1 (ready), tts-rt-v2"


def test_voice_models_rong():
    from soniox_cli.cli import _voice_models

    assert _voice_models(None) == "-"


def test_recompute_khong_co_model_van_gui_object_rong(monkeypatch):
    """Gửi `null` bị API trả 400; phải là `{}`."""
    import soniox_cli.cli as cli

    seen = {}

    def fake(client, method, path, **kw):
        seen.update(method=method, path=path, json=kw.get("json"))
        return {"id": "v1", "name": "n", "models": []}

    monkeypatch.setattr(cli, "get_client", lambda: object())
    monkeypatch.setattr(cli, "_request_json", fake)
    cli.cmd_voices_recompute(build_parser().parse_args(["voices", "recompute", "v1"]))
    assert seen["json"] == {}
    assert seen["path"] == "/voices/v1/recompute"


def test_recompute_co_model_thi_gui_model(monkeypatch):
    import soniox_cli.cli as cli

    seen = {}
    monkeypatch.setattr(cli, "get_client", lambda: object())
    monkeypatch.setattr(
        cli, "_request_json",
        lambda c, m, p, **kw: (seen.update(json=kw.get("json")), {"id": "v1", "models": []})[1],
    )
    cli.cmd_voices_recompute(
        build_parser().parse_args(["voices", "recompute", "v1", "--model", "tts-rt-v2"])
    )
    assert seen["json"] == {"model": "tts-rt-v2"}


def test_transcript_co_group_speakers_khong_phai_diarize():
    """Trên `stt transcript` cờ chỉ gộp output, không bật được diarization."""
    args = build_parser().parse_args(["stt", "transcript", "i", "--group-speakers"])
    assert args.group_speakers is True
    assert not hasattr(args, "diarize")


# --------------------------------------------------------------------------- #
# stt transcript phải in ra y hệt stt transcribe cho cùng một job.
# Lệnh cứu hộ không được cho kết quả kém hơn lệnh nó cứu hộ.
# --------------------------------------------------------------------------- #
def _fake_transcript_client(monkeypatch, transcript, destroyed=None):
    import soniox_cli.cli as cli

    class FakeStt:
        def get_transcript(self, _id):
            return transcript

        def destroy(self, tid):
            if destroyed is not None:
                destroyed.append(tid)

    monkeypatch.setattr(cli, "get_client", lambda: SimpleNamespace(stt=FakeStt()))
    return cli


def test_transcript_tu_gop_speaker_khong_can_co(monkeypatch, capsys):
    """Token có speaker thì gộp, không bắt người dùng nhớ gõ cờ."""
    t = SimpleNamespace(
        text="A B",
        tokens=[tok("A", speaker="1"), tok(" B", speaker="2")],
    )
    cli = _fake_transcript_client(monkeypatch, t)
    cli.cmd_stt_transcript(build_parser().parse_args(["stt", "transcript", "abc"]))
    out = capsys.readouterr().out
    assert "Speaker 1: A" in out
    assert "Speaker 2: B" in out


def test_transcript_giu_ban_dich(monkeypatch, capsys):
    """`transcript.text` chỉ có bản gốc; bản dịch phải dựng lại từ token."""
    t = SimpleNamespace(
        text="Hello",
        tokens=[
            tok("Hello", translation_status="original"),
            tok("Xin chào", translation_status="translation", language="vi"),
        ],
    )
    cli = _fake_transcript_client(monkeypatch, t)
    cli.cmd_stt_transcript(build_parser().parse_args(["stt", "transcript", "abc"]))
    out = capsys.readouterr().out
    assert "→ vi: Xin chào" in out


def test_transcript_flat_in_text_phang(monkeypatch, capsys):
    t = SimpleNamespace(text="A B", tokens=[tok("A", speaker="1"), tok(" B", speaker="2")])
    cli = _fake_transcript_client(monkeypatch, t)
    cli.cmd_stt_transcript(build_parser().parse_args(["stt", "transcript", "abc", "--flat"]))
    assert capsys.readouterr().out.strip() == "A B"


def test_transcript_json_ton_trong_output(monkeypatch, tmp_path, capsys):
    """--json không được nuốt -o, nếu không 16 MB đổ thẳng ra stdout."""
    out = tmp_path / "t.json"
    t = SimpleNamespace(text="xin chào", tokens=[])
    cli = _fake_transcript_client(monkeypatch, t)
    cli.cmd_stt_transcript(
        build_parser().parse_args(["stt", "transcript", "abc", "--json", "-o", str(out)])
    )
    assert "xin chào" in out.read_text(encoding="utf-8")
    assert "xin chào" not in capsys.readouterr().out


def test_transcript_destroy_don_ca_file(monkeypatch, capsys):
    destroyed: list[str] = []
    t = SimpleNamespace(text="x", tokens=[])
    cli = _fake_transcript_client(monkeypatch, t, destroyed)
    cli.cmd_stt_transcript(
        build_parser().parse_args(["stt", "transcript", "abc", "--destroy"])
    )
    capsys.readouterr()
    assert destroyed == ["abc"]


# --------------------------------------------------------------------------- #
# Vòng đời tiến trình: id phải ra ngoài ngay, tín hiệu hủy không xóa dữ liệu xa
# --------------------------------------------------------------------------- #
def _transcribe_env(monkeypatch, *, poll, destroyed, created=None):
    """`poll` là kết quả một lượt hỏi Soniox: CLI tự nuôi vòng lặp nên nó gọi `get`."""
    import soniox_cli.cli as cli

    class FakeStt:
        def transcribe(self, **kw):
            if created is not None:
                created.append(kw)
            return SimpleNamespace(id="TR1", status="queued")

        def get(self, _id):
            return poll()

        def get_transcript(self, _id):
            return SimpleNamespace(text="xong", tokens=[])

        def destroy(self, tid):
            destroyed.append(tid)

    monkeypatch.setattr(cli, "get_client", lambda: SimpleNamespace(stt=FakeStt()))
    return cli


def _transcribe_args(tmp_path, *extra):
    f = tmp_path / "a.mp3"
    f.write_bytes(b"x")
    return build_parser().parse_args(["stt", "transcribe", str(f), *extra])


def test_transcribe_in_id_ngay_tren_duong_hanh_phuc(monkeypatch, tmp_path, capsys):
    """Id là dữ kiện, không phải artifact của nhánh lỗi."""
    destroyed: list[str] = []
    cli = _transcribe_env(
        monkeypatch,
        poll=lambda: SimpleNamespace(id="TR1", status="completed"),
        destroyed=destroyed,
    )
    cli.cmd_stt_transcribe(_transcribe_args(tmp_path))
    assert "TR1" in capsys.readouterr().err


def test_transcribe_in_id_ca_khi_no_wait(monkeypatch, tmp_path, capsys):
    """--no-wait in id ra stdout cho máy đọc; stderr vẫn phải có cho người/log."""
    cli = _transcribe_env(monkeypatch, poll=lambda: None, destroyed=[])
    cli.cmd_stt_transcribe(_transcribe_args(tmp_path, "--no-wait"))
    cap = capsys.readouterr()
    assert "TR1" in cap.err
    assert "TR1" in cap.out


def test_flat_co_tac_dung_tren_ca_transcribe(monkeypatch, tmp_path, capsys):
    """`--flat` sống ở helper cờ output dùng chung, không riêng cho `transcript`."""
    import soniox_cli.cli as cli

    class FakeStt:
        def transcribe(self, **kw):
            return SimpleNamespace(id="TR1", status="queued")

        def get(self, _id):
            return SimpleNamespace(id="TR1", status="completed")

        def get_transcript(self, _id):
            return SimpleNamespace(
                text="A B", tokens=[tok("A", speaker="1"), tok(" B", speaker="2")]
            )

        def destroy(self, _id):
            pass

    monkeypatch.setattr(cli, "get_client", lambda: SimpleNamespace(stt=FakeStt()))
    cli.cmd_stt_transcribe(_transcribe_args(tmp_path, "--diarize"))
    assert "Speaker 1: A" in capsys.readouterr().out

    cli.cmd_stt_transcribe(_transcribe_args(tmp_path, "--diarize", "--flat"))
    assert capsys.readouterr().out.strip() == "A B"


def test_ctrl_c_khong_xoa_job_tren_soniox(monkeypatch, tmp_path, capsys):
    """Hủy chờ khác hủy job. Xem ADR-0008."""
    destroyed: list[str] = []

    def boom():
        raise KeyboardInterrupt

    cli = _transcribe_env(monkeypatch, poll=boom, destroyed=destroyed)
    with pytest.raises(KeyboardInterrupt):
        cli.cmd_stt_transcribe(_transcribe_args(tmp_path))
    assert destroyed == []
    assert "TR1" in capsys.readouterr().err


def test_systemexit_khong_kich_hoat_don_dep_tu_xa(monkeypatch, tmp_path, capsys):
    """SIGTERM biến thành SystemExit; nó không được chạm vào job trên Soniox."""
    destroyed: list[str] = []

    def boom():
        raise SystemExit(143)

    cli = _transcribe_env(monkeypatch, poll=boom, destroyed=destroyed)
    with pytest.raises(SystemExit):
        cli.cmd_stt_transcribe(_transcribe_args(tmp_path))
    assert destroyed == []
    assert "stt transcript TR1" in capsys.readouterr().err


def test_loi_api_giua_luc_cho_cung_de_lai_id(monkeypatch, tmp_path, capsys):
    """Lỗi API không được thử lại, nhưng nó vẫn là một đường bỏ cuộc: id phải ra."""
    from soniox.errors import SonioxError

    destroyed: list[str] = []

    def boom():
        raise SonioxError("API sập")

    cli = _transcribe_env(monkeypatch, poll=boom, destroyed=destroyed)
    with pytest.raises(SonioxError):
        cli.cmd_stt_transcribe(_transcribe_args(tmp_path))
    assert destroyed == []
    assert "stt transcript TR1" in capsys.readouterr().err


def test_ref_duoc_gui_len_soniox(monkeypatch, tmp_path, capsys):
    created: list[dict] = []
    cli = _transcribe_env(
        monkeypatch,
        poll=lambda: SimpleNamespace(id="TR1", status="completed"),
        destroyed=[],
        created=created,
    )
    cli.cmd_stt_transcribe(_transcribe_args(tmp_path, "--ref", "hop-2026-09-13"))
    capsys.readouterr()
    assert created[0]["client_reference_id"] == "hop-2026-09-13"


def test_khong_co_ref_thi_khong_tu_bia(monkeypatch, tmp_path, capsys):
    created: list[dict] = []
    cli = _transcribe_env(
        monkeypatch,
        poll=lambda: SimpleNamespace(id="TR1", status="completed"),
        destroyed=[],
        created=created,
    )
    cli.cmd_stt_transcribe(_transcribe_args(tmp_path))
    capsys.readouterr()
    assert created[0]["client_reference_id"] is None


# --------------------------------------------------------------------------- #
# Vòng lặp chờ: heartbeat, deadline, lỗi mạng giữa chừng (ADR-0009)
# --------------------------------------------------------------------------- #
class _Clock:
    """Đồng hồ giả: `sleep` đẩy `monotonic` tới, nên test chờ hàng phút vẫn chạy tức thì."""

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, sec: float) -> None:
        self.now += sec


def _poller(*results):
    """Client giả cho `stt.get`: trả lần lượt từng phần tử, phần tử cuối lặp mãi.

    Exception thì raise, chuỗi thì coi là `status`.
    """
    seq = list(results)
    calls: list[str] = []

    def get(tid):
        calls.append(tid)
        item = seq.pop(0) if len(seq) > 1 else seq[0]
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(id=tid, status=item)

    return SimpleNamespace(stt=SimpleNamespace(get=get)), calls


def _wait(client, logs, clock, **kw):
    import soniox_cli.cli as cli

    return cli.wait_for_transcription(
        client, "TR1", log=logs.append, sleep=clock.sleep, monotonic=clock.monotonic, **kw
    )


def test_heartbeat_moi_30s_kem_thoi_gian_da_troi_qua_va_status():
    """Tín hiệu sống: phân biệt 'đang chạy bình thường' với 'đã treo'."""
    clock, logs = _Clock(), []
    client, calls = _poller(*(["processing"] * 13), "completed")
    tr = _wait(client, logs, clock, timeout_sec=600.0)
    assert tr.status == "completed"
    assert len(logs) == 2
    assert "30s" in logs[0] and "processing" in logs[0] and "TR1" in logs[0]
    assert "1m00s" in logs[1]
    assert len(calls) == 14


def test_heartbeat_mac_dinh_di_ra_stderr(capsys):
    """`log` mặc định là `eprint`: đừng để chỉ test được khi có tiêm."""
    import soniox_cli.cli as cli

    clock = _Clock()
    client, _ = _poller(*(["processing"] * 7), "completed")
    cli.wait_for_transcription(
        client, "TR1", timeout_sec=600.0, sleep=clock.sleep, monotonic=clock.monotonic
    )
    cap = capsys.readouterr()
    assert "TR1" in cap.err and "status: processing" in cap.err
    assert cap.out == ""


def test_khong_heartbeat_khi_xong_truoc_moc_dau_tien():
    """Job nhanh thì im lặng: heartbeat là để phá im lặng dài, không phải để ồn."""
    clock, logs = _Clock(), []
    client, _ = _poller("processing", "completed")
    assert _wait(client, logs, clock, timeout_sec=600.0).status == "completed"
    assert logs == []


def test_het_gio_thi_nem_timeout_va_khong_ngu_qua_han():
    clock, logs = _Clock(), []
    client, _ = _poller("processing")
    with pytest.raises(TimeoutError):
        _wait(client, logs, clock, timeout_sec=20.0)
    assert clock.now == 20.0


def test_loi_mang_tam_thoi_thi_thu_lai_chu_khong_bo_cuoc():
    """`httpx.TransportError` là mạng chập chờn, không phải câu trả lời của API."""
    import httpx

    clock, logs = _Clock(), []
    client, calls = _poller(httpx.ConnectError("mạng chập chờn"), "completed")
    assert _wait(client, logs, clock, timeout_sec=600.0).status == "completed"
    assert len(calls) == 2
    assert "ConnectError" in logs[0]


def test_loi_mang_keo_dai_thi_bo_cuoc_sau_so_lan_da_dinh(monkeypatch):
    import httpx

    import soniox_cli.cli as cli

    monkeypatch.setattr(cli, "POLL_RETRY_MAX", 3)
    clock, logs = _Clock(), []
    client, calls = _poller(httpx.ConnectError("mất mạng"))
    with pytest.raises(httpx.ConnectError):
        _wait(client, logs, clock, timeout_sec=600.0)
    assert len(calls) == 4  # lần đầu cộng 3 lần thử lại


def test_loi_api_khong_duoc_thu_lai():
    """API đã trả lời thì tin nó, đừng hỏi lại năm lần rồi mới báo."""
    from soniox.errors import SonioxError

    clock, logs = _Clock(), []
    client, calls = _poller(SonioxError("transcription không tồn tại"))
    with pytest.raises(SonioxError):
        _wait(client, logs, clock, timeout_sec=600.0)
    assert len(calls) == 1


def test_backoff_bi_cat_theo_han_va_bao_dung_loi_mang():
    """Hết giờ trong lúc mạng đang hỏng: báo lỗi mạng, đừng khuyên tăng --timeout."""
    import httpx

    clock, logs = _Clock(), []
    client, _ = _poller(httpx.ConnectError("mất mạng"))
    with pytest.raises(httpx.ConnectError):
        _wait(client, logs, clock, timeout_sec=7.0)
    assert clock.now == 7.0  # 5 rồi 2, không phải 5 rồi 10
    # Con số hứa trong cảnh báo phải là con số thật, không phải mức backoff thô.
    assert "thử lại sau 5s" in logs[0]
    assert "thử lại sau 2s" in logs[1]


def test_mat_ket_noi_khi_cho_van_in_id_de_cuu(monkeypatch, tmp_path, capsys):
    """Đường bỏ cuộc mới cũng phải để lại id: xem ADR-0008."""
    import httpx

    import soniox_cli.cli as cli

    monkeypatch.setattr(cli, "POLL_RETRY_MAX", 0)
    destroyed: list[str] = []

    def boom():
        raise httpx.ConnectError("mất mạng")

    cli = _transcribe_env(monkeypatch, poll=boom, destroyed=destroyed)
    with pytest.raises(SystemExit):
        cli.cmd_stt_transcribe(_transcribe_args(tmp_path))
    assert destroyed == []
    err = capsys.readouterr().err
    assert "TR1" in err and "stt transcript TR1" in err


# --------------------------------------------------------------------------- #
# SIGTERM
# --------------------------------------------------------------------------- #
def test_main_dang_ky_sigterm(monkeypatch):
    import signal

    import soniox_cli.cli as cli

    seen: dict = {}
    monkeypatch.setattr(signal, "signal", lambda sig, h: seen.setdefault(sig, h))
    monkeypatch.setattr(cli, "run", lambda fn, args: None)
    cli.main(["stt", "list"])
    assert signal.SIGTERM in seen


def test_sigterm_nem_systemexit_143(capsys):
    import signal

    import soniox_cli.cli as cli

    with pytest.raises(SystemExit) as e:
        cli._on_sigterm(signal.SIGTERM, None)
    assert e.value.code == 143
    assert capsys.readouterr().err.strip() != ""


# --------------------------------------------------------------------------- #
# stt list: phân biệt được hai job mồ côi trùng tên
# --------------------------------------------------------------------------- #
def test_list_in_created_at_va_duration(monkeypatch, capsys):
    import soniox_cli.cli as cli
    from datetime import datetime, timezone

    rows = [
        SimpleNamespace(
            id="A",
            status="completed",
            filename="hop.mp4",
            created_at=datetime(2026, 9, 13, 14, 48, tzinfo=timezone.utc),
            audio_duration_ms=9_600_000,
            client_reference_id=None,
        ),
        SimpleNamespace(
            id="B",
            status="queued",
            filename="hop.mp4",
            created_at=None,
            audio_duration_ms=None,
            client_reference_id="hop-2",
        ),
    ]

    class FakeStt:
        def list(self, limit=None):
            return SimpleNamespace(transcriptions=rows)

    monkeypatch.setattr(cli, "get_client", lambda: SimpleNamespace(stt=FakeStt()))
    cli.cmd_stt_list(build_parser().parse_args(["stt", "list"]))
    out = capsys.readouterr().out
    assert "2h40m" in out
    assert "2026-09-13" in out
    assert "ref=hop-2" in out


# --------------------------------------------------------------------------- #
# soniox update
# --------------------------------------------------------------------------- #
def _update_env(monkeypatch, *, latest, source, ran=None):
    import soniox_cli.cli as cli
    from soniox_cli import update as U

    monkeypatch.setattr(U, "fetch_latest_version", lambda *a, **k: latest)
    monkeypatch.setattr(U, "read_source", lambda: source)
    monkeypatch.setattr(
        U, "run_upgrade",
        lambda log, force=False: (ran.append(force) if ran is not None else None) or 0,
    )
    return cli


def test_check_khong_cai_gi(monkeypatch, capsys):
    ran = []
    cli = _update_env(monkeypatch, latest="9.9.9", source=("uv-git", "https://x"), ran=ran)
    cli.cmd_update(build_parser().parse_args(["update", "--check"]))
    assert ran == []
    assert "chưa cập nhật gì" in capsys.readouterr().out


def test_da_moi_nhat_thi_khong_cai_lai(monkeypatch, capsys):
    from soniox_cli import __version__

    ran = []
    cli = _update_env(monkeypatch, latest=__version__, source=("uv-git", "https://x"), ran=ran)
    cli.cmd_update(build_parser().parse_args(["update"]))
    assert ran == []
    assert "không có gì để cập nhật" in capsys.readouterr().out


def test_co_ban_moi_thi_chay_nang_cap(monkeypatch):
    ran = []
    cli = _update_env(monkeypatch, latest="99.0.0", source=("uv-git", "https://x"), ran=ran)
    cli.cmd_update(build_parser().parse_args(["update"]))
    assert ran == [False]      # nâng cấp thường, không kèm --reinstall


def test_force_cai_lai_du_da_moi_nhat(monkeypatch):
    from soniox_cli import __version__

    ran = []
    cli = _update_env(monkeypatch, latest=__version__, source=("uv-git", "https://x"), ran=ran)
    cli.cmd_update(build_parser().parse_args(["update", "--force"]))
    assert ran == [True]       # --force truyền xuống thành --reinstall


def test_no_check_bo_qua_github(monkeypatch):
    import soniox_cli.cli as cli
    from soniox_cli import update as U

    ran = []
    monkeypatch.setattr(U, "read_source", lambda: ("uv-git", "https://x"))
    monkeypatch.setattr(U, "run_upgrade", lambda log, force=False: ran.append(force) or 0)
    monkeypatch.setattr(
        U, "fetch_latest_version", lambda *a, **k: pytest.fail("không được hỏi GitHub")
    )
    cli.cmd_update(build_parser().parse_args(["update", "--no-check"]))
    assert ran == [False]


def test_check_va_no_check_nguoc_nhau(monkeypatch):
    import soniox_cli.cli as cli

    with pytest.raises(SystemExit):
        cli.cmd_update(build_parser().parse_args(["update", "--check", "--no-check"]))


@pytest.mark.parametrize("source", [("uv-dir", "/tmp/repo"), ("unknown", None)])
def test_nguon_khong_tu_nang_cap_duoc_thi_huong_dan_thu_cong(monkeypatch, source):
    ran = []
    cli = _update_env(monkeypatch, latest="99.0.0", source=source, ran=ran)
    with pytest.raises(SystemExit):
        cli.cmd_update(build_parser().parse_args(["update"]))
    assert ran == []      # không tự chạy uv khi không chắc


def test_nang_cap_that_bai_thi_thoat_khac_0(monkeypatch):
    import soniox_cli.cli as cli
    from soniox_cli import update as U

    monkeypatch.setattr(U, "fetch_latest_version", lambda *a, **k: "99.0.0")
    monkeypatch.setattr(U, "read_source", lambda: ("uv-git", "https://x"))
    monkeypatch.setattr(U, "run_upgrade", lambda log, force=False: 2)
    with pytest.raises(SystemExit) as e:
        cli.cmd_update(build_parser().parse_args(["update"]))
    assert e.value.code == 2


# --------------------------------------------------------------------------- #
# --timestamps: text ngắt dòng theo lượt
# --------------------------------------------------------------------------- #
def _timed(text, start, end, *, speaker=None):
    return {"text": text, "start_ms": start, "end_ms": end, "speaker": speaker}


def test_timestamps_ngat_dong_theo_luot(monkeypatch, capsys):
    t = SimpleNamespace(
        text="Xin chào Vâng",
        tokens=[
            _timed("Xin chào", 0, 1000, speaker="1"),
            _timed("Vâng", 754_000, 755_000, speaker="2"),
        ],
    )
    cli = _fake_transcript_client(monkeypatch, t)
    cli.cmd_stt_transcript(build_parser().parse_args(["stt", "transcript", "abc", "--timestamps"]))
    assert capsys.readouterr().out.strip().splitlines() == [
        "[00:00:00] Speaker 1: Xin chào",
        "[00:12:34] Speaker 2: Vâng",
    ]


def test_timestamps_flat_bo_nhan_speaker(monkeypatch, capsys):
    t = SimpleNamespace(
        text="A B",
        tokens=[_timed("A ", 0, 100, speaker="1"), _timed("B", 100, 200, speaker="2")],
    )
    cli = _fake_transcript_client(monkeypatch, t)
    cli.cmd_stt_transcript(
        build_parser().parse_args(["stt", "transcript", "abc", "--timestamps", "--flat"])
    )
    assert capsys.readouterr().out.strip() == "[00:00:00] A B"


def test_timestamps_ton_trong_output(monkeypatch, tmp_path, capsys):
    """Đường ra dữ liệu lớn nào cũng phải đi qua `write_out`, có `-o` và có phanh."""
    out = tmp_path / "hop.txt"
    t = SimpleNamespace(text="Xin chào", tokens=[_timed("Xin chào", 0, 1000)])
    cli = _fake_transcript_client(monkeypatch, t)
    cli.cmd_stt_transcript(
        build_parser().parse_args(["stt", "transcript", "abc", "--timestamps", "-o", str(out)])
    )
    assert out.read_text(encoding="utf-8") == "[00:00:00] Xin chào"
    assert "Xin chào" not in capsys.readouterr().out


def test_timestamps_khong_co_token_thi_bao_loi(monkeypatch):
    t = SimpleNamespace(text="x", tokens=[])
    cli = _fake_transcript_client(monkeypatch, t)
    with pytest.raises(SystemExit):
        cli.cmd_stt_transcript(
            build_parser().parse_args(["stt", "transcript", "abc", "--timestamps"])
        )


def test_timestamps_khong_di_cung_subtitles(monkeypatch, capsys):
    """Hai cách dựng khác nhau cho cùng một đầu ra: bắt chọn, đừng tự đoán."""
    import soniox_cli.cli as cli

    args = build_parser().parse_args(
        ["stt", "transcript", "abc", "--timestamps", "--subtitles", "srt"]
    )
    with pytest.raises(SystemExit):
        cli.cmd_stt_transcript(args)
    assert "--timestamps" in capsys.readouterr().err


def test_timestamps_khong_di_cung_no_wait(monkeypatch, capsys):
    import soniox_cli.cli as cli

    monkeypatch.setattr(cli, "get_client", lambda: SimpleNamespace())
    args = build_parser().parse_args(
        ["stt", "transcribe", "https://x/a.mp3", "--no-wait", "--timestamps"]
    )
    with pytest.raises(SystemExit):
        cli.cmd_stt_transcribe(args)
    assert "--timestamps" in capsys.readouterr().err


def test_transcribe_cung_co_timestamps():
    """Lệnh cứu hộ không kém hơn lệnh nó cứu hộ, nên cả hai phải có cờ này."""
    args = build_parser().parse_args(["stt", "transcribe", "a.mp3", "--timestamps"])
    assert args.timestamps is True
