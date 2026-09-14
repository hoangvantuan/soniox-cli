"""Test dựng phụ đề: thuần logic, không chạm mạng."""

import pytest

from soniox_cli import subtitles as S


def tok(text, start, end, *, speaker=None, status=None):
    return {
        "text": text,
        "start_ms": start,
        "end_ms": end,
        "speaker": speaker,
        "translation_status": status,
    }


# --------------------------------------------------------------------------- #
# format_timestamp
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "ms,sep,expected",
    [
        (0, ",", "00:00:00,000"),
        (1600, ",", "00:00:01,600"),
        (61_001, ".", "00:01:01.001"),
        (3_723_456, ",", "01:02:03,456"),
        (-5, ",", "00:00:00,000"),  # không cho âm
    ],
)
def test_format_timestamp(ms, sep, expected):
    assert S.format_timestamp(ms, sep=sep) == expected


# --------------------------------------------------------------------------- #
# build_cues: từng quy tắc cắt
# --------------------------------------------------------------------------- #
def test_gom_token_nho_thanh_mot_cue():
    cues = S.build_cues([tok("Wh", 0, 100), tok("at", 100, 200), tok(" now", 200, 400)])
    assert len(cues) == 1
    assert cues[0].text == "What now"
    assert (cues[0].start_ms, cues[0].end_ms) == (0, 400)


def test_doi_nguoi_noi_thi_cat_cue():
    cues = S.build_cues(
        [tok("A ", 0, 100, speaker="1"), tok("B", 100, 200, speaker="2")], with_speaker=True
    )
    assert [c.text for c in cues] == ["A", "B"]
    assert [c.speaker for c in cues] == ["1", "2"]


def test_khong_bat_speaker_thi_khong_cat_theo_nguoi_noi():
    cues = S.build_cues(
        [tok("A ", 0, 100, speaker="1"), tok("B", 100, 200, speaker="2")], with_speaker=False
    )
    assert len(cues) == 1


def test_vuot_max_chars_thi_cat():
    toks = [tok("x" * 10 + " ", i * 100, i * 100 + 100) for i in range(5)]
    cues = S.build_cues(toks, max_chars=25)
    assert len(cues) > 1
    assert all(len(c.text) <= 25 for c in cues)


def test_im_lang_dai_thi_cat():
    cues = S.build_cues([tok("A ", 0, 100), tok("B", 5000, 5100)], gap_ms=700)
    assert [c.text for c in cues] == ["A", "B"]


def test_cue_qua_dai_thi_cat():
    toks = [tok(f"w{i} ", i * 1000, i * 1000 + 900) for i in range(10)]
    cues = S.build_cues(toks, max_duration_ms=3000, max_chars=1000, gap_ms=10_000)
    assert len(cues) > 1
    assert all(c.end_ms - c.start_ms <= 4000 for c in cues)


def test_het_cau_thi_cat_khi_cue_da_du_dai():
    toks = [tok("Câu thứ nhất đã khá dài rồi.", 0, 1000), tok(" Câu hai.", 1000, 2000)]
    cues = S.build_cues(toks, max_chars=1000, gap_ms=10_000)
    assert len(cues) == 2
    assert cues[0].text.endswith(".")


def test_bo_qua_token_rong():
    cues = S.build_cues([tok("", 0, 0), tok("A", 0, 100)])
    assert [c.text for c in cues] == ["A"]


def test_khong_co_token_thi_khong_co_cue():
    assert S.build_cues([]) == []


# --------------------------------------------------------------------------- #
# select_tracks
# --------------------------------------------------------------------------- #
@pytest.fixture
def mixed():
    return [
        tok("hello", 0, 500, status="original"),
        tok("xin chào", 0, 500, status="translation"),
    ]


def test_auto_uu_tien_ban_dich_khi_co(mixed):
    (stream,) = S.select_tracks(mixed, "auto")
    assert [t["text"] for t in stream] == ["xin chào"]


def test_auto_dung_nguyen_ban_khi_khong_co_dich():
    toks = [tok("hello", 0, 500)]
    (stream,) = S.select_tracks(toks, "auto")
    assert [t["text"] for t in stream] == ["hello"]


def test_track_original_va_translation(mixed):
    assert [t["text"] for t in S.select_tracks(mixed, "original")[0]] == ["hello"]
    assert [t["text"] for t in S.select_tracks(mixed, "translation")[0]] == ["xin chào"]


def test_track_both_cho_hai_luong(mixed):
    streams = S.select_tracks(mixed, "both")
    assert len(streams) == 2


def test_track_khong_hop_le():
    with pytest.raises(ValueError):
        S.select_tracks([], "khong-ton-tai")


def test_has_translation(mixed):
    assert S.has_translation(mixed) is True
    assert S.has_translation([tok("a", 0, 1)]) is False


# --------------------------------------------------------------------------- #
# merge_cues
# --------------------------------------------------------------------------- #
def test_merge_sap_xep_theo_thoi_gian():
    a = [S.Cue(1000, 1500, "sau")]
    b = [S.Cue(0, 500, "truoc")]
    assert [c.text for c in S.merge_cues([a, b])] == ["truoc", "sau"]


# --------------------------------------------------------------------------- #
# render
# --------------------------------------------------------------------------- #
def test_srt_dung_cau_truc():
    out = S.render([tok("Xin chào.", 0, 1500)], fmt="srt")
    assert out == "1\n00:00:00,000 --> 00:00:01,500\nXin chào.\n"


def test_vtt_co_header_va_dau_cham():
    out = S.render([tok("Xin chào.", 0, 1500)], fmt="vtt")
    assert out.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:01.500" in out


def test_srt_danh_so_tang_dan():
    toks = [tok("A.", 0, 500), tok("B.", 5000, 5500)]
    out = S.render(toks, fmt="srt", max_chars=5)
    assert out.startswith("1\n")
    assert "\n2\n" in out


def test_render_gan_nhan_nguoi_noi():
    out = S.render([tok("A", 0, 500, speaker="2")], fmt="srt", with_speaker=True)
    assert "Speaker 2: A" in out


def test_render_both_xen_ke_theo_thoi_gian():
    toks = [
        tok("hello", 0, 500, status="original"),
        tok("xin chào", 600, 1100, status="translation"),
    ]
    out = S.render(toks, fmt="srt", track="both")
    assert out.index("hello") < out.index("xin chào")


def test_render_rong_khong_no():
    assert S.render([], fmt="srt") == ""
    assert S.render([], fmt="vtt") == "WEBVTT\n"


# --------------------------------------------------------------------------- #
# normalize_tokens: token bản dịch không mang mốc thời gian
# --------------------------------------------------------------------------- #
def _translated_stream():
    """Đúng hình dạng Soniox trả về: đoạn nguyên bản, rồi đoạn dịch mốc 0."""
    return [
        tok("Hel", 1000, 1200, status="original", speaker="1"),
        tok("lo", 1200, 1400, status="original", speaker="1"),
        tok("Xin ", 0, 0, status="translation"),
        tok("chào", 0, 0, status="translation"),
        tok("Bye", 5000, 5600, status="original", speaker="2"),
        tok("Tạm biệt", 0, 0, status="translation"),
    ]


def test_token_dich_muon_moc_thoi_gian_cua_doan_nguyen_ban_truoc_do():
    rows = S.normalize_tokens(_translated_stream())
    dich = [r for r in rows if r["translation_status"] == "translation"]
    assert dich[0]["start_ms"] == 1000            # đầu đoạn nguyên bản
    assert dich[1]["end_ms"] == 1400              # cuối đoạn nguyên bản
    assert dich[-1]["start_ms"] == 5000           # đoạn thứ hai bám đoạn của nó
    assert dich[-1]["end_ms"] == 5600


def test_moc_thoi_gian_ban_dich_tang_dan():
    rows = S.normalize_tokens(_translated_stream())
    dich = [r for r in rows if r["translation_status"] == "translation"]
    assert all(a["end_ms"] <= b["start_ms"] + 1 for a, b in zip(dich, dich[1:]))


def test_token_dich_muon_luon_nguoi_noi():
    rows = S.normalize_tokens(_translated_stream())
    assert rows[2]["speaker"] == "1"


def test_token_nguyen_ban_khong_bi_doi_moc():
    rows = S.normalize_tokens(_translated_stream())
    goc = [r for r in rows if r["translation_status"] == "original"]
    assert (goc[0]["start_ms"], goc[0]["end_ms"]) == (1000, 1200)


def test_phu_de_ban_dich_khong_con_nam_o_giay_0():
    out = S.render(_translated_stream(), fmt="srt", track="translation")
    assert "00:00:00,000 --> 00:00:00,000" not in out
    assert "00:00:01,000" in out


def test_chi_co_token_dich_thi_khong_no():
    rows = S.normalize_tokens([tok("a", 0, 0, status="translation")])
    assert rows[0]["start_ms"] == 0


def test_normalize_chiu_duoc_object_khong_phai_dict():
    from types import SimpleNamespace

    rows = S.normalize_tokens(
        [SimpleNamespace(text="a", start_ms=5, end_ms=10, speaker=None, translation_status=None)]
    )
    assert rows[0] == {
        "text": "a", "start_ms": 5, "end_ms": 10,
        "speaker": None, "translation_status": None, "language": None,
    }


# --------------------------------------------------------------------------- #
# build_turns: lượt nói. Chỉ ngắt bởi khoảng lặng và đổi người nói.
# --------------------------------------------------------------------------- #
def test_luot_khong_cat_theo_max_chars():
    """Lượt để đọc và grep, không có màn hình nào để tràn."""
    toks = [tok(f"tu{i} ", i * 100, i * 100 + 100) for i in range(40)]
    turns = S.build_turns(toks)
    assert len(turns) == 1
    assert len(turns[0].text) > S.DEFAULT_MAX_CHARS


def test_luot_khong_cat_theo_do_dai_thoi_gian():
    toks = [tok(f"t{i} ", i * 1000, i * 1000 + 1000) for i in range(20)]
    turns = S.build_turns(toks)
    assert len(turns) == 1
    assert turns[0].end_ms - turns[0].start_ms > S.DEFAULT_MAX_DURATION_MS


def test_luot_khong_cat_o_het_cau():
    toks = [
        tok("Câu thứ nhất khá dài để vượt ngưỡng. ", 0, 1000),
        tok("Câu thứ hai cũng vậy.", 1000, 2000),
    ]
    turns = S.build_turns(toks)
    assert len(turns) == 1


def test_luot_cat_khi_im_lang_qua_nguong():
    toks = [tok("A", 0, 100), tok("B", 100 + S.DEFAULT_GAP_MS + 1, 1500)]
    assert [t.text for t in S.build_turns(toks)] == ["A", "B"]


def test_luot_cat_khi_doi_nguoi_noi():
    toks = [tok("A ", 0, 100, speaker="1"), tok("B", 100, 200, speaker="2")]
    turns = S.build_turns(toks, with_speaker=True)
    assert [(t.speaker, t.text) for t in turns] == [("1", "A"), ("2", "B")]


def test_luot_khong_bat_speaker_thi_khong_cat_theo_nguoi_noi():
    toks = [tok("A ", 0, 100, speaker="1"), tok("B", 100, 200, speaker="2")]
    assert len(S.build_turns(toks, with_speaker=False)) == 1


def test_luot_khong_co_token_thi_khong_no():
    assert S.build_turns([]) == []


def test_luot_tach_ban_dich_khoi_nguyen_ban():
    """Token dịch mượn mốc của đoạn gốc nên không có khoảng lặng nào để cắt.

    Ranh giới gốc/dịch phải cắt bằng `_runs`, nếu không hai bên dính thành một
    dòng: nguyên bản nối thẳng vào bản dịch.
    """
    toks = [
        tok("Hello", 0, 3000, status="original"),
        tok("Xin chào", 0, 0, status="translation"),
    ]
    turns = S.build_turns(toks)
    assert [(t.status, t.text) for t in turns] == [
        ("original", "Hello"),
        ("translation", "Xin chào"),
    ]
    # Mượn mốc của đoạn gốc liền trước, không nằm ở giây 0 một cách vô nghĩa.
    assert turns[1].start_ms == 0 and turns[1].end_ms == 3000


def test_luot_giu_ngon_ngu_ban_dich():
    toks = [
        {"text": "Hello", "start_ms": 0, "end_ms": 1000, "translation_status": "original"},
        {
            "text": "Xin chào",
            "start_ms": 0,
            "end_ms": 0,
            "translation_status": "translation",
            "language": "vi",
        },
    ]
    assert S.build_turns(toks)[1].language == "vi"


# --------------------------------------------------------------------------- #
# render_turns
# --------------------------------------------------------------------------- #
def test_render_turns_dat_moc_dau_dong():
    toks = [
        tok("Xin chào", 0, 1000, speaker="1"),
        tok("Vâng", 754_000, 755_000, speaker="2"),
    ]
    out = S.render_turns(S.build_turns(toks, with_speaker=True))
    assert out == "[00:00:00] Speaker 1: Xin chào\n[00:12:34] Speaker 2: Vâng"


def test_render_turns_khong_co_speaker_thi_chi_co_moc():
    assert S.render_turns(S.build_turns([tok("A", 0, 100)])) == "[00:00:00] A"


def test_render_turns_gan_nhan_ban_dich():
    """Giữ đúng nhãn mà text thuần đang dùng, chỉ thêm mốc thời gian."""
    toks = [
        {
            "text": "Hello",
            "start_ms": 0,
            "end_ms": 1000,
            "speaker": "1",
            "translation_status": "original",
        },
        {
            "text": "Xin chào",
            "start_ms": 0,
            "end_ms": 0,
            "speaker": "1",
            "translation_status": "translation",
            "language": "vi",
        },
    ]
    out = S.render_turns(S.build_turns(toks, with_speaker=True))
    assert out == "[00:00:00] [Speaker 1] Hello\n[00:00:00] [Speaker 1] → vi: Xin chào"


def test_render_turns_rong():
    assert S.render_turns([]) == ""


def test_format_timestamp_bo_mili():
    assert S.format_timestamp(754_321, millis=False) == "00:12:34"
