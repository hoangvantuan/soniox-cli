"""Dựng phụ đề SRT / WebVTT và text theo lượt từ token của Soniox.

Thuần logic, không chạm mạng: nhận danh sách token (mỗi token có `text`,
`start_ms`, `end_ms`, tùy chọn `speaker` và `translation_status`) rồi trả về
chuỗi phụ đề, hoặc text ngắt dòng theo lượt nói.

Việc khó không nằm ở định dạng mà ở **cắt cue**: token của Soniox nhỏ hơn từ
(ví dụ "Wh" + "at"), nên phải gom lại thành câu đọc kịp trên màn hình.

**Cue** và **lượt** dùng chung một vòng gom token, khác nhau ở chỗ dừng: cue
phục vụ màn hình nên bị chặn bởi số ký tự, độ dài và dấu kết câu; lượt phục vụ
đọc và `grep` nên chỉ ngắt khi đổi người nói hoặc im lặng quá ngưỡng.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

# Chuẩn phụ đề thông dụng: 2 dòng x 42 ký tự.
DEFAULT_MAX_CHARS = 84
DEFAULT_MAX_DURATION_MS = 6000
# Im lặng dài hơn mức này thì sang cue mới, dù chưa đầy dòng.
DEFAULT_GAP_MS = 700
# Gặp dấu kết câu mà cue đã đủ dài thì cắt, cho ngắt tự nhiên theo câu.
_SENTENCE_END = (".", "!", "?", "…", "。", "！", "？")
_MIN_CHARS_FOR_SENTENCE_BREAK = 24

TRACKS = ("auto", "original", "translation", "both")


@dataclass
class Cue:
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None


@dataclass
class Turn:
    """Một lượt nói: cue không bị giới hạn màn hình, có thêm nhãn bản dịch.

    Giữ riêng `status` và `language` vì lượt được in thành text chứ không lên
    màn hình, nên phải tự gắn nhãn `→ <lang>:` như đường text thuần đang làm.
    """

    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None
    status: str = "original"
    language: str | None = None


def _get(tok: Any, name: str, default=None):
    """Đọc thuộc tính token, chịu được cả object lẫn dict."""
    if isinstance(tok, dict):
        return tok.get(name, default)
    value = getattr(tok, name, default)
    return default if value is None else value


def _status(tok: Any) -> str:
    return "translation" if _get(tok, "translation_status") == "translation" else "original"


def _runs(tokens: list[Any]) -> list[tuple[str, list[Any]]]:
    """Cắt token thành các đoạn liên tiếp cùng `translation_status`."""
    runs: list[tuple[str, list[Any]]] = []
    for tok in tokens:
        st = _status(tok)
        if runs and runs[-1][0] == st:
            runs[-1][1].append(tok)
        else:
            runs.append((st, [tok]))
    return runs


def _as_dict(tok: Any) -> dict:
    return {
        "text": _get(tok, "text", ""),
        "start_ms": int(_get(tok, "start_ms", 0) or 0),
        "end_ms": int(_get(tok, "end_ms", 0) or 0),
        "speaker": _get(tok, "speaker"),
        "translation_status": _get(tok, "translation_status"),
        "language": _get(tok, "language"),
    }


def normalize_tokens(tokens: Iterable[Any]) -> list[dict]:
    """Chuẩn hóa token về dict và gán mốc thời gian cho phần bản dịch.

    Soniox trả token bản dịch với `start_ms = end_ms = 0`: dùng thẳng thì mọi
    cue phụ đề đều nằm ở giây 0. Chúng đi thành từng đoạn ngay sau đoạn nguyên
    bản tương ứng, nên mượn khoảng thời gian của đoạn đó rồi chia cho các token
    theo độ dài ký tự, để cue dài vẫn cắt ra được mốc hợp lý.
    """
    rows = [_as_dict(t) for t in tokens]
    runs = _runs(rows)

    def span(run: list[dict]) -> tuple[int, int] | None:
        times = [(t["start_ms"], t["end_ms"]) for t in run if t["end_ms"] or t["start_ms"]]
        return (min(a for a, _ in times), max(b for _, b in times)) if times else None

    for i, (status, run) in enumerate(runs):
        if status != "translation" or span(run) is not None:
            continue
        # Đoạn nguyên bản gần nhất: ưu tiên ngay trước, không có thì ngay sau.
        source = None
        for j in list(range(i - 1, -1, -1)) + list(range(i + 1, len(runs))):
            if runs[j][0] == "original":
                source = span(runs[j][1])
                if source:
                    break
        if not source:
            continue
        start, end = source
        total = sum(len(t["text"]) for t in run) or 1
        cursor = start
        for t in run:
            share = (end - start) * len(t["text"]) / total
            t["start_ms"] = int(round(cursor))
            cursor += share
            t["end_ms"] = int(round(cursor))
            if t["speaker"] is None:
                t["speaker"] = next((o["speaker"] for o in runs[i - 1][1]), None) if i else None
    return rows


def has_translation(tokens: Iterable[Any]) -> bool:
    return any(_get(t, "translation_status") == "translation" for t in tokens)


def select_tracks(tokens: list[Any], track: str) -> list[list[Any]]:
    """Chọn (các) luồng token theo `track`.

    Trả về danh sách luồng: `both` cho hai luồng, còn lại cho một.
    `auto` nghĩa là có bản dịch thì lấy bản dịch, không thì lấy nguyên bản.
    """
    if track not in TRACKS:
        raise ValueError(f"track không hợp lệ: {track}")
    original = [t for t in tokens if _get(t, "translation_status") != "translation"]
    translated = [t for t in tokens if _get(t, "translation_status") == "translation"]

    if track == "auto":
        return [translated] if translated else [original]
    if track == "original":
        return [original]
    if track == "translation":
        return [translated]
    return [s for s in (original, translated) if s]


def build_cues(
    tokens: list[Any],
    *,
    max_chars: int | None = DEFAULT_MAX_CHARS,
    max_duration_ms: int | None = DEFAULT_MAX_DURATION_MS,
    gap_ms: int = DEFAULT_GAP_MS,
    with_speaker: bool = False,
    sentence_break: bool = True,
) -> list[Cue]:
    """Gom token liên tiếp thành cue.

    Cắt cue khi gặp bất kỳ điều nào: đổi người nói, quá `max_chars`, quá
    `max_duration_ms`, im lặng quá `gap_ms`, hoặc hết câu mà cue đã đủ dài.

    Ba ràng buộc cuối chỉ có nghĩa khi cue phải nằm vừa một màn hình. `None`
    cho `max_chars` / `max_duration_ms` và `sentence_break=False` tắt chúng đi,
    còn lại đúng hai chỗ cắt của một **lượt**: đổi người nói và khoảng lặng.
    """
    cues: list[Cue] = []
    buf: list[str] = []
    start = end = 0
    speaker: str | None = None

    def flush() -> None:
        text = "".join(buf).strip()
        if text:
            cues.append(Cue(start_ms=start, end_ms=end, text=text, speaker=speaker))
        buf.clear()

    for tok in tokens:
        text = _get(tok, "text", "")
        if not text:
            continue
        t_start = int(_get(tok, "start_ms", 0) or 0)
        t_end = int(_get(tok, "end_ms", t_start) or t_start)
        t_speaker = _get(tok, "speaker") if with_speaker else None

        if buf:
            pending = "".join(buf).strip()
            too_long = max_chars is not None and len(pending) + len(text) > max_chars
            too_slow = max_duration_ms is not None and t_end - start > max_duration_ms
            silent = t_start - end > gap_ms
            if t_speaker != speaker or too_long or too_slow or silent:
                flush()

        if not buf:
            start, speaker = t_start, t_speaker
        buf.append(text)
        end = t_end

        if sentence_break and "".join(buf).strip().endswith(_SENTENCE_END):
            if len("".join(buf).strip()) >= _MIN_CHARS_FOR_SENTENCE_BREAK:
                flush()

    flush()
    return cues


def merge_cues(streams: list[list[Cue]]) -> list[Cue]:
    """Trộn nhiều luồng cue theo thứ tự thời gian (dùng cho track `both`)."""
    merged = [c for stream in streams for c in stream]
    merged.sort(key=lambda c: (c.start_ms, c.end_ms))
    return merged


def format_timestamp(ms: int, *, sep: str = ",", millis: bool = True) -> str:
    """`ms` -> `HH:MM:SS<sep>mmm`. `sep` là ',' cho SRT, '.' cho VTT.

    `millis=False` trả về `HH:MM:SS`: mốc đầu lượt chỉ cần tới giây.
    """
    ms = max(0, int(ms))
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, rest = divmod(rest, 1000)
    clock = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{clock}{sep}{rest:03d}" if millis else clock


def _cue_text(cue: Cue) -> str:
    return f"Speaker {cue.speaker}: {cue.text}" if cue.speaker else cue.text


def render_srt(cues: list[Cue]) -> str:
    blocks = []
    for i, cue in enumerate(cues, start=1):
        start = format_timestamp(cue.start_ms, sep=",")
        end = format_timestamp(cue.end_ms, sep=",")
        blocks.append(f"{i}\n{start} --> {end}\n{_cue_text(cue)}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def render_vtt(cues: list[Cue]) -> str:
    blocks = ["WEBVTT"]
    for cue in cues:
        start = format_timestamp(cue.start_ms, sep=".")
        end = format_timestamp(cue.end_ms, sep=".")
        blocks.append(f"{start} --> {end}\n{_cue_text(cue)}")
    return "\n\n".join(blocks) + "\n"


def render(
    tokens: list[Any],
    *,
    fmt: str,
    track: str = "auto",
    with_speaker: bool = False,
    max_chars: int = DEFAULT_MAX_CHARS,
    max_duration_ms: int = DEFAULT_MAX_DURATION_MS,
    gap_ms: int = DEFAULT_GAP_MS,
) -> str:
    """Đường vào chính: token -> chuỗi phụ đề."""
    tokens = normalize_tokens(tokens)
    streams = [
        build_cues(
            stream,
            max_chars=max_chars,
            max_duration_ms=max_duration_ms,
            gap_ms=gap_ms,
            with_speaker=with_speaker,
        )
        for stream in select_tracks(tokens, track)
    ]
    cues = merge_cues(streams) if len(streams) > 1 else (streams[0] if streams else [])
    return render_srt(cues) if fmt == "srt" else render_vtt(cues)


def build_turns(
    tokens: list[Any],
    *,
    gap_ms: int = DEFAULT_GAP_MS,
    with_speaker: bool = False,
) -> list[Turn]:
    """Gom token thành **lượt**: chỉ ngắt khi đổi người nói hoặc im lặng quá `gap_ms`.

    Dùng lại đúng vòng gom của `build_cues`, tắt cả ba giới hạn phục vụ màn
    hình. Ngưỡng im lặng giữ nguyên `DEFAULT_GAP_MS` của cue: cùng một cách gom
    token thì cùng một ngưỡng, đổi sau là đổi một hằng số.

    Ranh giới gốc / bản dịch cắt bằng `_runs` chứ không nhờ khoảng lặng: token
    dịch mượn mốc thời gian của đoạn gốc liền trước, nên đứng cạnh nhau chúng
    *lùi* về quá khứ chứ không hở ra khoảng nào để cắt. Giữ nguyên thứ tự token,
    không sắp lại theo thời gian, để bản dịch vẫn nằm ngay sau đoạn gốc của nó.
    """
    turns: list[Turn] = []
    for status, run in _runs(normalize_tokens(tokens)):
        language = next((t["language"] for t in run if t["language"]), None)
        turns += [
            Turn(
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                text=cue.text,
                speaker=cue.speaker,
                status=status,
                language=language,
            )
            for cue in build_cues(
                run,
                max_chars=None,
                max_duration_ms=None,
                gap_ms=gap_ms,
                with_speaker=with_speaker,
                sentence_break=False,
            )
        ]
    return turns


def _turn_label(turn: Turn, *, bracket_speaker: bool) -> str:
    """Nhãn đứng giữa mốc thời gian và nội dung, y hệt nhãn của text thuần."""
    speaker = ""
    if turn.speaker:
        speaker = (
            f"[Speaker {turn.speaker}] " if bracket_speaker else f"Speaker {turn.speaker}: "
        )
    if turn.status == "translation":
        return f"{speaker}→ {turn.language or 'dịch'}: "
    return speaker


def render_turns(turns: list[Turn]) -> str:
    """Mỗi lượt một dòng, mở đầu bằng `[HH:MM:SS]`.

    Chỉ in mốc bắt đầu, không in cả khoảng: grep được, hợp quy ước biên bản
    họp, in cả khoảng chỉ thêm nhiễu.
    """
    # Có bản dịch thì mượn luôn cách gắn nhãn của text thuần: `[Speaker 1] → vi:`.
    bracket = any(t.status == "translation" for t in turns)
    return "\n".join(
        f"[{format_timestamp(t.start_ms, millis=False)}] "
        f"{_turn_label(t, bracket_speaker=bracket)}{t.text}"
        for t in turns
    )
