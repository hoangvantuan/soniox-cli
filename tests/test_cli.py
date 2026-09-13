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
