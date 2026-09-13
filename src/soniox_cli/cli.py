"""CLI bọc Soniox SDK.

Thiết kế: chỉ phần request/response (async STT, files, TTS REST, voices, metadata).
Không bọc realtime streaming (WebSocket) vì không hợp mô hình một-lệnh-một-kết-quả.

Output mặc định là text người-đọc-được; cờ toàn cục --json in JSON đầy đủ.
Lỗi ra stderr, exit code != 0.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, NoReturn

from . import __version__, media, subtitles, update

STT_DEFAULT_MODEL = "stt-async-v5"
TTS_DEFAULT_MODEL = "tts-rt-v1"
TTS_DEFAULT_VOICE = "Adrian"
TTS_SPEED_MIN, TTS_SPEED_MAX = 0.7, 1.3

# Mọi giá trị TtsAudioFormat Soniox chấp nhận.
TTS_AUDIO_FORMATS = (
    "wav", "mp3", "flac", "opus", "aac",
    "pcm_s16le", "pcm_f32le", "pcm_mulaw", "pcm_alaw",
)

# Map đuôi file -> TtsAudioFormat hợp lệ của Soniox.
_SUFFIX_TO_FORMAT = {
    ".wav": "wav",
    ".mp3": "mp3",
    ".flac": "flac",
    ".opus": "opus",
    ".aac": "aac",
    ".pcm": "pcm_s16le",
}


# --------------------------------------------------------------------------- #
# Tiện ích chung
# --------------------------------------------------------------------------- #
def eprint(*a: Any) -> None:
    print(*a, file=sys.stderr)


def die(msg: str, code: int = 1) -> NoReturn:
    eprint(f"error: {msg}")
    raise SystemExit(code)


def get_client():
    """Khởi tạo SonioxClient từ biến môi trường.

    - `SONIOX_API_KEY` (bắt buộc): API key.
    - `SONIOX_API_BASE_URL` (tùy chọn): endpoint REST theo vùng (data residency).
    - `SONIOX_TTS_API_BASE_URL` (tùy chọn): endpoint TTS theo vùng.

    SDK chỉ tự đọc `SONIOX_API_KEY`; hai base URL phải truyền qua constructor
    nên CLI đọc env rồi chuyển tiếp.
    """
    if not os.environ.get("SONIOX_API_KEY"):
        die("chưa có SONIOX_API_KEY. Chạy: export SONIOX_API_KEY=<key>")
    from soniox import SonioxClient

    kw: dict[str, Any] = {}
    if base := os.environ.get("SONIOX_API_BASE_URL"):
        kw["api_base_url"] = base
    if tts_base := os.environ.get("SONIOX_TTS_API_BASE_URL"):
        kw["tts_api_base_url"] = tts_base
    return SonioxClient(**kw)


def jsonable(obj: Any) -> Any:
    """Chuyển model Pydantic / list model thành cấu trúc JSON-serializable."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    return obj


def wants_json(args) -> bool:
    return bool(getattr(args, "json", False))


def emit(args, data: Any, human) -> None:
    """In kết quả: --json -> JSON đầy đủ; ngược lại -> dạng người đọc.

    `human` là chuỗi, hoặc callable(data)->str.
    """
    if wants_json(args):
        print_json(data)
        return
    text = human(data) if callable(human) else human
    print(text)


# Dài hơn mức này mà không có -o thì nhắc một dòng ra stderr. Với agent, đổ cả
# transcript vào context tốn hơn nhiều so với ghi ra file rồi đọc phần cần.
BIG_OUTPUT_CHARS = 20_000


def write_out(args, text: str) -> None:
    """In ra stdout, hoặc ghi ra file nếu có -o."""
    out = getattr(args, "output", None)
    if not out:
        if len(text) > BIG_OUTPUT_CHARS:
            eprint(
                f"gợi ý: kết quả dài {len(text):,} ký tự. Lần sau thêm "
                f"-o <file> để ghi thẳng ra file thay vì đổ hết ra stdout."
            )
        print(text)
        return
    path = Path(out).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"đã ghi {len(text)} ký tự -> {path}")


def print_json(data: Any) -> None:
    print(json.dumps(jsonable(data), ensure_ascii=False, indent=2, default=str))


def run(fn, args) -> None:
    """Bọc lời gọi API: dịch mọi lỗi dự kiến thành thông báo CLI gọn.

    `httpx.HTTPError` (DNS, mất mạng, timeout tầng HTTP) không phải lớp con của
    `SonioxError` lẫn `TimeoutError`, nên phải bắt riêng, nếu không người dùng
    nhận nguyên traceback.
    """
    import httpx
    from soniox.errors import SonioxError

    try:
        fn(args)
    except SonioxError as e:  # gồm SonioxAPIError và các lớp con
        req = getattr(e, "request_id", None)
        suffix = f" (request_id={req})" if req else ""
        die(f"lỗi Soniox: {e}{suffix}")
    except TimeoutError as e:
        die(str(e) or "hết thời gian chờ")
    except media.MediaError as e:
        die(str(e))
    except update.UpdateError as e:
        die(str(e))
    except httpx.HTTPError as e:
        die(f"lỗi kết nối tới Soniox: {type(e).__name__}: {e}")
    except KeyboardInterrupt:
        die("đã hủy", code=130)


# --------------------------------------------------------------------------- #
# Dựng cấu hình STT từ flag
# --------------------------------------------------------------------------- #
def parse_translate(spec: str) -> dict:
    """`fr` -> one_way; `two-way:en,vi` -> two_way."""
    low = spec.strip()
    if low.startswith("two-way:") or low.startswith("two_way:"):
        rest = low.split(":", 1)[1]
        parts = [p.strip() for p in rest.split(",") if p.strip()]
        if len(parts) != 2:
            die("--translate two-way cần dạng: two-way:LANG_A,LANG_B (vd two-way:en,vi)")
        return {"type": "two_way", "language_a": parts[0], "language_b": parts[1]}
    return {"type": "one_way", "target_language": low}


def build_stt_config(args):
    """Gộp các flag STT + --config-json thành CreateTranscriptionConfig (hoặc None)."""
    cfg: dict[str, Any] = {}
    if getattr(args, "language_hints", None):
        cfg["language_hints"] = [s.strip() for s in args.language_hints.split(",") if s.strip()]
    if getattr(args, "diarize", False):
        cfg["enable_speaker_diarization"] = True
    if getattr(args, "context", None):
        cfg["context"] = {"text": args.context}
    if getattr(args, "translate", None):
        cfg["translation"] = parse_translate(args.translate)
        cfg["enable_language_identification"] = True
    from soniox.types import CreateTranscriptionConfig

    if getattr(args, "config_json", None):
        extra = _load_config_json(args.config_json)
        reject_unknown_keys(extra, CreateTranscriptionConfig, "--config-json")
        cfg.update(extra)
    if not cfg:
        return None

    try:
        return CreateTranscriptionConfig(**cfg)
    except Exception as e:  # pydantic ValidationError, ...
        die(f"cấu hình STT không hợp lệ: {e}")


def reject_unknown_keys(data: dict, model, where: str) -> None:
    """Chặn key lạ trước khi nhồi vào một model pydantic.

    Pydantic mặc định `extra="ignore"`: gõ sai tên trường (`language_hint` thiếu
    chữ s) sẽ bị bỏ im lặng, người dùng tưởng đã bật cấu hình mà thật ra không.

    Chỉ dùng cho đường đi QUA model (STT). Payload gửi thẳng API (TTS) không cần
    và không nên lọc: ở đó API mới là bên phán quyết, lọc theo model của SDK sẽ
    chặn oan trường mà API đã hỗ trợ nhưng SDK bản đang cài chưa biết.
    """
    known = set(model.model_fields)
    for field in model.model_fields.values():
        if field.alias:
            known.add(field.alias)
    unknown = sorted(set(data) - known)
    if unknown:
        die(
            f"{where}: trường không tồn tại: {', '.join(unknown)}.\n"
            f"  trường hợp lệ: {', '.join(sorted(known))}"
        )


def _load_config_json(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        die(f"--config-json không phải JSON hợp lệ: {e}")
    if not isinstance(data, dict):
        die("--config-json phải là một object JSON, vd '{\"language_hints\":[\"vi\"]}'")
    return data


def resolve_audio_input(args) -> dict:
    """Xác định nguồn audio: --file-id, URL, hay file local. Trả kwargs cho SDK."""
    if getattr(args, "file_id", None):
        if getattr(args, "input", None):
            die("không dùng đồng thời --file-id và đầu vào file/URL; chọn một")
        return {"file_id": args.file_id}
    value = args.input
    if value is None:
        die("thiếu đầu vào: đường dẫn file, URL công khai, hoặc --file-id")
    if value.startswith(("http://", "https://")):
        return {"audio_url": value}
    p = Path(value).expanduser()
    if p.is_file():
        return {"file": str(p)}
    die(f"'{value}' không phải URL và cũng không phải file tồn tại")


def diarization_on(args, cfg) -> bool:
    """Diarization có bật không, tính cả khi bật qua --config-json.

    Chỉ nhìn `args.diarize` sẽ bỏ sót người dùng escape hatch: token có `speaker`
    nhưng output lại in phẳng.
    """
    return bool(getattr(args, "diarize", False) or getattr(cfg, "enable_speaker_diarization", False))


def format_transcript_text(transcript, diarize: bool) -> str:
    """Text người-đọc-được.

    - Có dịch: dựng lại từ token (vì `transcript.text` chỉ chứa bản gốc), xen
      kẽ gốc và bản dịch theo thứ tự, gắn nhãn "→ <lang>:".
    - Có diarization: gộp theo speaker.
    - Còn lại: dùng thẳng `transcript.text`.
    """
    tokens = getattr(transcript, "tokens", None) or []
    has_translation = any(getattr(t, "translation_status", None) == "translation" for t in tokens)
    has_speaker = any(getattr(t, "speaker", None) for t in tokens)

    if has_translation:
        return _format_translation(tokens, diarize and has_speaker)
    if diarize and has_speaker:
        return _group_tokens_by(
            tokens, key=lambda t: getattr(t, "speaker", None) or "?", label=lambda k: f"Speaker {k}: "
        )
    return transcript.text


def _group_tokens_by(tokens, key, label) -> str:
    """Gom token liên tiếp cùng `key(t)` thành một dòng, prefix bởi `label(key)`."""
    lines: list[str] = []
    cur = object()
    buf: list[str] = []
    for t in tokens:
        k = key(t)
        if k != cur:
            if buf:
                lines.append(f"{label(cur)}{''.join(buf).strip()}")
            cur, buf = k, []
        buf.append(t.text)
    if buf:
        lines.append(f"{label(cur)}{''.join(buf).strip()}")
    return "\n".join(lines)


def _format_translation(tokens, with_speaker: bool) -> str:
    """Xen kẽ gốc / bản dịch theo thứ tự token; bản dịch gắn nhãn ngôn ngữ."""

    def label(t) -> str:
        sp = f"[Speaker {t.speaker}] " if with_speaker and getattr(t, "speaker", None) else ""
        if getattr(t, "translation_status", None) == "translation":
            return f"{sp}→ {getattr(t, 'language', None) or 'dịch'}: "
        return sp

    def keyof(t):
        return (
            getattr(t, "translation_status", None),
            getattr(t, "speaker", None) if with_speaker else None,
        )

    # Gom token liên tiếp cùng (translation_status, speaker) thành từng nhóm.
    groups: list[tuple[Any, list]] = []
    for t in tokens:
        k = keyof(t)
        if not groups or groups[-1][0] != k:
            groups.append((k, [t]))
        else:
            groups[-1][1].append(t)

    lines: list[str] = []
    for _key, group in groups:
        text = "".join(tok.text for tok in group).strip()
        if text:
            lines.append(f"{label(group[0])}{text}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Lệnh STT
# --------------------------------------------------------------------------- #
@contextmanager
def _upload_ready(args, src: dict):
    """Tách audio khỏi video trước khi upload; không phải file local thì để yên.

    File tạm nằm trong thư mục tạm của hệ thống và bị xóa khi ra khỏi khối này.
    """
    path = src.get("file")
    if not path:
        yield src
        return
    with media.prepared_upload(
        Path(path),
        extract=not args.no_extract_audio,
        keep=args.keep_extracted,
        log=eprint,
    ) as ready:
        yield {**src, "file": str(ready)}


def _try_destroy(client, transcription_id: str, quiet: bool = False) -> None:
    """Dọn transcription + file đính kèm. Nuốt lỗi: đây là bước dọn, không phải kết quả."""
    try:
        client.stt.destroy(transcription_id)
    except Exception as e:  # noqa: BLE001 - dọn dẹp không được che lấp lỗi gốc
        if not quiet:
            eprint(f"cảnh báo: không dọn được transcription {transcription_id}: {e}")


def cmd_stt_transcribe(args) -> None:
    """Tạo transcription rồi (mặc định) chờ xong, in text và dọn khỏi Soniox.

    Tự chờ thay vì dùng `transcribe_and_wait_with_tokens` để luôn nắm được id:
    khi hết giờ hoặc người dùng Ctrl-C, còn chỗ bám để dọn hoặc lấy lại kết quả,
    thay vì bỏ mồ côi dữ liệu trên Soniox.
    """
    client = get_client()
    src = resolve_audio_input(args)
    cfg = build_stt_config(args)
    model = args.model or STT_DEFAULT_MODEL

    if args.no_wait and args.subtitles:
        die("--subtitles cần transcript nên không dùng chung với --no-wait; "
            "poll xong rồi chạy: soniox stt transcript <id> --subtitles " + args.subtitles)

    with _upload_ready(args, src) as src:
        tr = client.stt.transcribe(model=model, config=cfg, **src)

    if args.no_wait:
        emit(
            args,
            tr,
            lambda d: f"id: {d.id}\nstatus: {d.status}\n"
            f"(lấy transcript sau: soniox stt transcript {d.id})",
        )
        return

    try:
        tr = client.stt.wait(tr.id, timeout_sec=args.timeout)
    except TimeoutError:
        die(
            f"hết thời gian chờ ({args.timeout}s); transcription {tr.id} vẫn đang chạy.\n"
            f"  lấy kết quả sau: soniox stt transcript {tr.id}\n"
            f"  hoặc dọn đi:     soniox stt delete {tr.id} --destroy\n"
            f"  (hoặc tăng --timeout, hoặc dùng --no-wait ngay từ đầu)"
        )
    except KeyboardInterrupt:
        if args.keep:
            eprint(f"đã hủy; transcription {tr.id} vẫn còn trên Soniox.")
        else:
            eprint(f"đã hủy; đang dọn transcription {tr.id}...")
            _try_destroy(client, tr.id)
        raise

    if tr.status == "error":
        detail = getattr(tr, "error_message", None) or "không rõ nguyên nhân"
        if not args.keep:
            _try_destroy(client, tr.id, quiet=True)
        die(f"Soniox xử lý thất bại (transcription {tr.id}): {detail}")

    transcript = client.stt.get_transcript(tr.id)
    if not args.keep:
        _try_destroy(client, tr.id)

    emit_transcript(args, transcript, diarize=diarization_on(args, cfg))


def emit_transcript(args, transcript, *, diarize: bool) -> None:
    """In transcript theo đúng dạng người dùng yêu cầu: JSON, phụ đề, hay text."""
    if wants_json(args):
        print_json(transcript)
        return
    fmt = getattr(args, "subtitles", None)
    if fmt:
        tokens = getattr(transcript, "tokens", None) or []
        if not tokens:
            die("transcript không có token nên không dựng được phụ đề")
        write_out(
            args,
            subtitles.render(
                tokens,
                fmt=fmt,
                track=args.subtitle_track,
                with_speaker=diarize,
                max_chars=args.subtitle_max_chars,
            ),
        )
        return
    write_out(args, format_transcript_text(transcript, diarize))


def cmd_stt_get(args) -> None:
    client = get_client()
    tr = client.stt.get(args.id)
    emit(
        args,
        tr,
        lambda d: (
            f"id: {d.id}\nstatus: {d.status}\nmodel: {d.model}\n"
            f"filename: {d.filename}\nduration_ms: {d.audio_duration_ms}\n"
            f"error: {d.error_message or '-'}"
        ),
    )


def cmd_stt_list(args) -> None:
    client = get_client()
    rows = _rows(client, "stt", args)
    if rows is None:
        rows = client.stt.list(limit=args.limit).transcriptions
    emit(
        args,
        rows,
        lambda d: "\n".join(f"{t.id}  {t.status:<10}  {t.filename or ''}" for t in d)
        or "(chưa có transcription nào)",
    )


def _rows(client, namespace, args):
    """Lấy danh sách: `--all` thì phân trang hết, không thì một trang `--limit`."""
    ns = getattr(client, namespace)
    if getattr(args, "all", False):
        return list(ns.list_all(limit=args.limit))
    return None


def cmd_stt_count(args) -> None:
    client = get_client()
    data = _request_json(client, "GET", "/transcriptions/count")
    emit(args, data, lambda d: f"tổng: {d.get('total')}  (api: {d.get('public_api')}, playground: {d.get('playground')})")


def cmd_stt_delete_all(args) -> None:
    client = get_client()
    total = _request_json(client, "GET", "/transcriptions/count").get("total", 0)
    if not total:
        emit(args, {"deleted": 0}, "không có transcription nào để xóa")
        return
    if not args.yes:
        kem = " và file đính kèm" if args.destroy else ""
        die(f"sẽ xóa {total} transcription{kem}. Thêm --yes để xác nhận.")
    if args.destroy:
        client.stt.destroy_all(limit=args.limit)
    else:
        client.stt.delete_all(limit=args.limit)
    emit(
        args,
        {"deleted": total, "destroy": args.destroy},
        f"đã xóa {total} transcription" + (" và file đính kèm" if args.destroy else ""),
    )


def cmd_stt_transcript(args) -> None:
    client = get_client()
    t = client.stt.get_transcript(args.id)
    if not wants_json(args) and not args.subtitles:  # noqa: SIM102 - đường nhanh cho text thuần
        write_out(args, t.text)
        return
    emit_transcript(args, t, diarize=args.group_speakers)


def cmd_stt_delete(args) -> None:
    client = get_client()
    if args.destroy:
        client.stt.destroy(args.id)
    else:
        client.stt.delete(args.id)
    emit(
        args,
        {"deleted": args.id, "destroy": args.destroy},
        f"đã xóa transcription {args.id}" + (" và file đính kèm" if args.destroy else ""),
    )


# --------------------------------------------------------------------------- #
# Lệnh Files
# --------------------------------------------------------------------------- #
def cmd_files_upload(args) -> None:
    client = get_client()
    p = Path(args.path).expanduser()
    if not p.is_file():
        die(f"không thấy file: {args.path}")
    with media.prepared_upload(
        p, extract=not args.no_extract_audio, keep=args.keep_extracted, log=eprint
    ) as ready:
        f = client.files.upload(str(ready))
    emit(
        args,
        f,
        lambda d: f"id: {d.id}\nfilename: {d.filename}\nsize: {getattr(d, 'size', '?')}",
    )


def cmd_files_count(args) -> None:
    client = get_client()
    data = _request_json(client, "GET", "/files/count")
    emit(args, data, lambda d: f"tổng: {d.get('total')}  (api: {d.get('public_api')}, playground: {d.get('playground')})")


def cmd_files_delete_all(args) -> None:
    client = get_client()
    total = _request_json(client, "GET", "/files/count").get("total", 0)
    if not total:
        emit(args, {"deleted": 0}, "không có file nào để xóa")
        return
    if not args.yes:
        die(f"sẽ xóa {total} file đã upload. Thêm --yes để xác nhận.")
    client.files.delete_all(limit=args.limit)
    emit(args, {"deleted": total}, f"đã xóa {total} file")


def cmd_files_list(args) -> None:
    client = get_client()
    rows = _rows(client, "files", args)
    if rows is None:
        rows = client.files.list(limit=args.limit).files
    emit(
        args,
        rows,
        lambda d: "\n".join(f"{f.id}  {f.filename}" for f in d) or "(chưa có file nào)",
    )


def cmd_files_get(args) -> None:
    client = get_client()
    f = client.files.get(args.id)
    emit(args, f, lambda d: f"id: {d.id}\nfilename: {d.filename}\nsize: {getattr(d, 'size', '?')}")


def cmd_files_delete(args) -> None:
    client = get_client()
    client.files.delete(args.id)
    emit(args, {"deleted": args.id}, f"đã xóa file {args.id}")


# --------------------------------------------------------------------------- #
# Lệnh TTS (raw POST tới {tts_api_base_url}/tts để hỗ trợ đầy đủ speed)
# --------------------------------------------------------------------------- #
def read_tts_text(args) -> str:
    if args.text is not None:
        return args.text
    if args.text_file:
        return Path(args.text_file).expanduser().read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def fmt_from_output(path: Path, override: str | None) -> str:
    """Suy định dạng từ đuôi file, hoặc lấy `--format` nếu có.

    Không âm thầm rơi về wav: ghi byte WAV vào file `.ogg` tệ hơn một lỗi rõ ràng.
    """
    if override:
        if override not in TTS_AUDIO_FORMATS:
            die(f"--format '{override}' không hợp lệ. Chọn: {', '.join(TTS_AUDIO_FORMATS)}")
        return override
    fmt = _SUFFIX_TO_FORMAT.get(path.suffix.lower())
    if fmt is None:
        known = ", ".join(sorted(_SUFFIX_TO_FORMAT))
        die(
            f"không suy được định dạng từ đuôi '{path.suffix or path.name}'. "
            f"Dùng đuôi quen thuộc ({known}) hoặc chỉ định --format."
        )
    return fmt


def cmd_tts_generate(args) -> None:
    client = get_client()
    text = read_tts_text(args)
    if not text.strip():
        die("thiếu text. Truyền trực tiếp, dùng --text-file, hoặc pipe qua stdin.")
    out_path = Path(args.output).expanduser()
    audio_format = fmt_from_output(out_path, args.format)

    payload: dict[str, Any] = {
        "text": text,
        "model": args.model or TTS_DEFAULT_MODEL,
        "voice": args.voice or TTS_DEFAULT_VOICE,
        "language": args.language,
        "audio_format": audio_format,
    }
    if args.sample_rate:
        payload["sample_rate"] = args.sample_rate
    if args.bitrate:
        payload["bitrate"] = args.bitrate
    if args.speed is not None:
        if not TTS_SPEED_MIN <= args.speed <= TTS_SPEED_MAX:
            die(f"--speed phải trong khoảng {TTS_SPEED_MIN} đến {TTS_SPEED_MAX}")
        payload["speed"] = args.speed
    if args.config_json:
        # Không lọc key ở đây: payload đi thẳng lên API chứ không qua model
        # pydantic, nên không có gì bị bỏ im lặng. Lọc theo model của SDK sẽ
        # chặn oan các trường API đã hỗ trợ mà SDK bản đang cài chưa biết.
        payload.update(_load_config_json(args.config_json))

    resp = client.request("POST", f"{client.tts_api_base_url}/tts", json=payload)
    if resp.status_code != 200:
        _raise_http(resp)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = out_path.write_bytes(resp.content)
    emit(
        args,
        {"output": str(out_path), "bytes": written, "audio_format": audio_format},
        f"đã ghi {written} bytes -> {out_path}",
    )


def _raise_http(resp) -> "None":
    """Dịch phản hồi HTTP lỗi thành thông báo CLI."""
    try:
        body = resp.json()
        msg = body.get("message") or body.get("error_type") or resp.text
        req = body.get("request_id")
    except Exception:
        msg, req = resp.text[:300], None
    suffix = f" (request_id={req})" if req else ""
    die(f"lỗi Soniox [{resp.status_code}]: {msg}{suffix}")


# --------------------------------------------------------------------------- #
# Lệnh Voices (raw request: SDK 2.3.2 chưa wrap namespace voices)
# --------------------------------------------------------------------------- #
def _request_json(client, method: str, path: str, **kw) -> Any:
    resp = client.request(method, path, **kw)
    if resp.status_code >= 400:
        _raise_http(resp)
    if not resp.content:
        return {}
    return resp.json()


def cmd_voices_list(args) -> None:
    client = get_client()
    data = _request_json(client, "GET", "/voices")
    voices = data.get("voices", [])
    emit(
        args,
        voices,
        lambda d: "\n".join(f"{v.get('id')}  {v.get('name')}" for v in d)
        or "(chưa có voice nào)",
    )


def cmd_voices_create(args) -> None:
    client = get_client()
    p = Path(args.sample).expanduser()
    if not p.is_file():
        die(f"không thấy file mẫu: {args.sample}")
    with p.open("rb") as fh:
        data = _request_json(
            client,
            "POST",
            "/voices",
            data={"name": args.name},
            files={"file": (p.name, fh)},
        )
    emit(
        args,
        data,
        lambda d: f"đã tạo voice: id={d.get('id')} name={d.get('name')}",
    )


def _voice_models(models) -> str:
    """`models` là danh sách {model, status, ...}, không phải danh sách chuỗi."""
    parts = []
    for m in models or []:
        if isinstance(m, dict):
            name = m.get("model") or "?"
            status = m.get("status")
            parts.append(f"{name} ({status})" if status else str(name))
        else:
            parts.append(str(m))
    return ", ".join(parts) or "-"


def _voice_line(v: dict) -> str:
    return (
        f"id: {v.get('id')}\nname: {v.get('name')}\n"
        f"filename: {v.get('filename')}\ncreated_at: {v.get('created_at')}\n"
        f"models: {_voice_models(v.get('models'))}"
    )


def cmd_voices_get(args) -> None:
    client = get_client()
    emit(args, _request_json(client, "GET", f"/voices/{args.id}"), _voice_line)


def cmd_voices_count(args) -> None:
    client = get_client()
    data = _request_json(client, "GET", "/voices/count")
    emit(args, data, lambda d: f"tổng: {d.get('total')}")


def cmd_voices_recompute(args) -> None:
    client = get_client()
    # Bỏ model thì vẫn phải gửi object rỗng; gửi `null` bị API từ chối 400.
    body = {"model": args.model} if args.model else {}
    data = _request_json(client, "POST", f"/voices/{args.id}/recompute", json=body)
    emit(args, data, _voice_line)


def cmd_voices_delete(args) -> None:
    client = get_client()
    _request_json(client, "DELETE", f"/voices/{args.id}")
    emit(args, {"deleted": args.id}, f"đã xóa voice {args.id}")


# --------------------------------------------------------------------------- #
# Lệnh metadata: models / usage / auth
# --------------------------------------------------------------------------- #
def _model_line(m) -> str:
    """Một dòng đủ để chọn model: id, chế độ, số ngôn ngữ, khả năng dịch."""
    mid = getattr(m, "id", None) or getattr(m, "name", str(m))
    bits = []
    mode = getattr(m, "transcription_mode", None)
    if mode:
        bits.append(str(mode))
    langs = getattr(m, "languages", None)
    if langs:
        bits.append(f"{len(langs)} ngôn ngữ")
    trans = [
        name
        for name, attr in (("one-way", "one_way_translation"), ("two-way", "two_way_translation"))
        if getattr(m, attr, None)
    ]
    if trans:
        bits.append("dịch " + "/".join(trans))
    voices = getattr(m, "voices", None)
    if voices:
        bits.append(f"{len(voices)} voice")
    if getattr(m, "supports_speed_adjustment", False):
        bits.append("chỉnh tốc độ")
    return f"{mid:<22} {'  '.join(bits)}".rstrip()


def cmd_models(args) -> None:
    client = get_client()
    resp = client.tts_models.list() if args.tts else client.models.list()
    models = getattr(resp, "models", resp)
    emit(
        args,
        models,
        lambda d: "\n".join(_model_line(m) for m in d) or "(không có model)",
    )


def _limits_block(title: str, d: dict) -> str:
    """Ghép `current` và `limits` thành từng dòng `đang dùng / giới hạn`."""
    current = d.get("current") or {}
    limits = d.get("limits") or {}
    keys = sorted(set(current) | set(limits))
    if not keys:
        return f"{title}: (không có dữ liệu)"
    lines = [f"{title}:"]
    for k in keys:
        cap = limits.get(k)
        lines.append(f"  {k:<24} {current.get(k, 0)} / {'không giới hạn' if cap is None else cap}")
    return "\n".join(lines)


def cmd_concurrency(args) -> None:
    client = get_client()
    data = _request_json(client, "GET", "/concurrency-limits")
    emit(
        args,
        data,
        lambda d: _limits_block("project", d.get("project") or {})
        + "\n"
        + _limits_block("organization", d.get("organization") or {}),
    )


def cmd_usage(args) -> None:
    client = get_client()
    now = datetime.now(timezone.utc)
    end = args.end or now.strftime("%Y-%m-%dT%H:%M:%SZ")
    start = args.start or (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = _request_json(
        client,
        "GET",
        "/usage-logs",
        params={"start_time": start, "end_time": end, "limit": args.limit},
    )
    entries = data.get("entries") or data.get("usage_logs") or data.get("logs") or []
    emit(args, data, lambda _d: _usage_summary(entries, start, end))


def _fmt_duration(ms: float) -> str:
    seconds = int(round(ms / 1000))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def _num(value: Any) -> float:
    """Ép về số. API trả `cost_usd` dạng chuỗi ("0.1956645000"), đừng tin kiểu."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _usage_summary(entries: list, start: str, end: str) -> str:
    """Tổng hợp theo model thay vì đổ nguyên JSON ra màn hình."""
    if not entries:
        return f"(không có bản ghi usage trong khoảng {start} .. {end})"

    per_model: dict[str, dict[str, float]] = {}
    for e in entries:
        row = per_model.setdefault(
            e.get("model") or "(không rõ)", {"n": 0, "audio_ms": 0.0, "cost": 0.0}
        )
        row["n"] += 1
        row["audio_ms"] += _num(e.get("input_audio_duration_ms")) + _num(
            e.get("output_audio_duration_ms")
        )
        row["cost"] += _num(e.get("cost_usd"))

    lines = [f"{start} .. {end}", ""]
    lines.append(f"{'model':<22} {'request':>8} {'audio':>10} {'USD':>10}")
    for name in sorted(per_model, key=lambda k: -per_model[k]["cost"]):
        r = per_model[name]
        lines.append(
            f"{name:<22} {int(r['n']):>8} {_fmt_duration(r['audio_ms']):>10} {r['cost']:>10.4f}"
        )
    total_n = sum(r["n"] for r in per_model.values())
    total_ms = sum(r["audio_ms"] for r in per_model.values())
    total_cost = sum(r["cost"] for r in per_model.values())
    lines.append(f"{'TỔNG':<22} {int(total_n):>8} {_fmt_duration(total_ms):>10} {total_cost:>10.4f}")
    lines.append("")
    lines.append("(--json để xem từng bản ghi)")
    return "\n".join(lines)


def cmd_update(args) -> None:
    """Báo có bản mới không, và (mặc định) gọi trình quản lý gói cập nhật."""
    if args.check and args.no_check:
        die("--check và --no-check ngược nhau, chọn một")
    kind, detail = update.read_source()

    latest = None
    if not args.no_check:
        latest = update.fetch_latest_version()
        state = (
            f"có bản mới: {latest}"
            if update.is_newer(latest, __version__)
            else "đang là bản mới nhất"
        )
        eprint(f"đang dùng {__version__}, trên GitHub là {latest} — {state}")
    eprint(f"cách cài: {update.describe_source(kind, detail)}")

    if args.check:
        emit(
            args,
            {"current": __version__, "latest": latest, "source": kind, "detail": detail},
            lambda _d: "(--check nên dừng ở đây, chưa cập nhật gì)",
        )
        return

    if latest is not None and not update.is_newer(latest, __version__) and not args.force:
        emit(
            args,
            {"current": __version__, "latest": latest, "updated": False},
            "không có gì để cập nhật. Dùng --force để cài lại bản hiện tại.",
        )
        return

    if kind not in ("uv", "uv-git"):
        # uv-dir: uv sẽ cài lại từ thư mục local, không kéo được commit mới về.
        die(update.manual_instructions(kind, detail))

    code = update.run_upgrade(eprint, force=args.force)
    if code != 0:
        die(f"lệnh nâng cấp thất bại (mã {code})", code=code)
    print("đã cập nhật. Kiểm tra: soniox --version")


def cmd_auth_check(args) -> None:
    client = get_client()
    resp = client.models.list()
    n = len(getattr(resp, "models", []) or [])
    emit(args, {"ok": True, "stt_models": n}, f"OK — API key hợp lệ ({n} model STT khả dụng)")


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def _add_json_flag(p: argparse.ArgumentParser, *, top: bool = False) -> None:
    """Thêm cờ --json.

    Ở cấp subcommand phải dùng SUPPRESS: nếu để default=False, argparse sẽ ghi đè
    giá trị --json mà người dùng đã đặt trước tên subcommand.
    """
    kwargs: dict[str, Any] = {} if top else {"default": argparse.SUPPRESS}
    p.add_argument("--json", action="store_true", help="in JSON đầy đủ thay vì text", **kwargs)


def _add_upload_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--no-extract-audio",
        action="store_true",
        help="upload nguyên file thay vì tách audio khỏi video trước",
    )
    p.add_argument(
        "--keep-extracted",
        action="store_true",
        help="giữ lại file audio đã tách trong thư mục tạm và in đường dẫn",
    )


def _add_subtitle_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--subtitles",
        choices=("srt", "vtt"),
        help="xuất phụ đề thay vì text thuần",
    )
    p.add_argument(
        "--subtitle-track",
        choices=subtitles.TRACKS,
        default="auto",
        help="luồng dùng cho phụ đề khi có bản dịch (mặc định auto: có dịch thì lấy bản dịch)",
    )
    p.add_argument(
        "--subtitle-max-chars",
        type=int,
        default=subtitles.DEFAULT_MAX_CHARS,
        help=f"số ký tự tối đa mỗi cue (mặc định {subtitles.DEFAULT_MAX_CHARS})",
    )
    p.add_argument("-o", "--output", help="ghi ra file thay vì in ra stdout")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="soniox",
        description="CLI Soniox: STT / TTS / Files / Voices (chỉ request-response, không realtime).",
    )
    parser.add_argument("--version", action="version", version=f"soniox-cli {__version__}")
    _add_json_flag(parser, top=True)
    sub = parser.add_subparsers(dest="group", required=True)

    # ---- stt ----
    stt = sub.add_parser("stt", help="Speech-to-Text (async)")
    stt_sub = stt.add_subparsers(dest="action", required=True)

    tr = stt_sub.add_parser("transcribe", help="phiên âm file/URL (mặc định chờ xong + tự dọn)")
    tr.add_argument("input", nargs="?", help="đường dẫn file local hoặc URL công khai")
    tr.add_argument("--file-id", help="dùng file đã upload trước đó thay cho input")
    tr.add_argument("--model", help=f"model STT (mặc định {STT_DEFAULT_MODEL})")
    tr.add_argument("--language-hints", help="gợi ý ngôn ngữ, phân tách bởi dấu phẩy (vd vi,en)")
    tr.add_argument("--diarize", action="store_true", help="bật tách người nói")
    tr.add_argument(
        "--translate",
        metavar="SPEC",
        help="dịch: 'fr' (một chiều) hoặc 'two-way:en,vi' (hai chiều)",
    )
    tr.add_argument("--context", help="ngữ cảnh/thuật ngữ để tăng độ chính xác")
    tr.add_argument("--config-json", help="JSON gộp thẳng vào CreateTranscriptionConfig")
    tr.add_argument("--no-wait", action="store_true", help="không chờ; trả về id để poll sau")
    tr.add_argument("--keep", action="store_true", help="không tự xóa transcription/file sau khi xong")
    tr.add_argument("--timeout", type=float, default=600.0, help="giới hạn chờ (giây), mặc định 600")
    _add_upload_flags(tr)
    _add_subtitle_flags(tr)
    _add_json_flag(tr)
    tr.set_defaults(func=cmd_stt_transcribe)

    g = stt_sub.add_parser("get", help="lấy metadata một transcription")
    g.add_argument("id")
    _add_json_flag(g)
    g.set_defaults(func=cmd_stt_get)

    ls = stt_sub.add_parser("list", help="liệt kê transcription")
    ls.add_argument("--limit", type=int, default=100, help="số bản ghi mỗi trang")
    ls.add_argument("--all", action="store_true", help="phân trang lấy hết, không dừng ở --limit")
    _add_json_flag(ls)
    ls.set_defaults(func=cmd_stt_list)

    sc = stt_sub.add_parser("count", help="đếm transcription đang có")
    _add_json_flag(sc)
    sc.set_defaults(func=cmd_stt_count)

    sda = stt_sub.add_parser("delete-all", help="xóa TOÀN BỘ transcription (cần --yes)")
    sda.add_argument("--destroy", action="store_true", help="xóa kèm file đã upload")
    sda.add_argument("--yes", action="store_true", help="xác nhận thật sự muốn xóa hết")
    sda.add_argument("--limit", type=int, default=100, help="số bản ghi mỗi trang khi duyệt")
    _add_json_flag(sda)
    sda.set_defaults(func=cmd_stt_delete_all)

    ts = stt_sub.add_parser("transcript", help="lấy transcript của một transcription")
    ts.add_argument("id")
    ts.add_argument(
        "--group-speakers",
        action="store_true",
        help="gộp output theo người nói (chỉ có tác dụng nếu transcript đã có diarization)",
    )
    _add_subtitle_flags(ts)
    _add_json_flag(ts)
    ts.set_defaults(func=cmd_stt_transcript)

    de = stt_sub.add_parser("delete", help="xóa một transcription")
    de.add_argument("id")
    de.add_argument("--destroy", action="store_true", help="xóa kèm file đã upload")
    _add_json_flag(de)
    de.set_defaults(func=cmd_stt_delete)

    # ---- files ----
    files = sub.add_parser("files", help="quản lý file audio đã upload")
    files_sub = files.add_subparsers(dest="action", required=True)

    up = files_sub.add_parser("upload", help="upload file audio (video sẽ được tách audio trước)")
    up.add_argument("path")
    _add_upload_flags(up)
    _add_json_flag(up)
    up.set_defaults(func=cmd_files_upload)

    fls = files_sub.add_parser("list", help="liệt kê file")
    fls.add_argument("--limit", type=int, default=100, help="số bản ghi mỗi trang")
    fls.add_argument("--all", action="store_true", help="phân trang lấy hết, không dừng ở --limit")
    _add_json_flag(fls)
    fls.set_defaults(func=cmd_files_list)

    fc = files_sub.add_parser("count", help="đếm file đã upload")
    _add_json_flag(fc)
    fc.set_defaults(func=cmd_files_count)

    fda = files_sub.add_parser("delete-all", help="xóa TOÀN BỘ file đã upload (cần --yes)")
    fda.add_argument("--yes", action="store_true", help="xác nhận thật sự muốn xóa hết")
    fda.add_argument("--limit", type=int, default=100, help="số bản ghi mỗi trang khi duyệt")
    _add_json_flag(fda)
    fda.set_defaults(func=cmd_files_delete_all)

    fg = files_sub.add_parser("get", help="metadata một file")
    fg.add_argument("id")
    _add_json_flag(fg)
    fg.set_defaults(func=cmd_files_get)

    fd = files_sub.add_parser("delete", help="xóa một file")
    fd.add_argument("id")
    _add_json_flag(fd)
    fd.set_defaults(func=cmd_files_delete)

    # ---- tts ----
    tts = sub.add_parser("tts", help="Text-to-Speech (REST)")
    tts_sub = tts.add_subparsers(dest="action", required=True)

    gen = tts_sub.add_parser("generate", help="sinh audio từ text ra file")
    gen.add_argument("text", nargs="?", help="text cần đọc (hoặc dùng --text-file / stdin)")
    gen.add_argument("-o", "--output", required=True, help="đường dẫn file audio đầu ra (bắt buộc)")
    gen.add_argument("--text-file", help="đọc text từ file")
    gen.add_argument("--voice", help=f"voice (mặc định {TTS_DEFAULT_VOICE})")
    gen.add_argument("--language", default="en", help="mã ngôn ngữ (vd vi, en)")
    gen.add_argument("--model", help=f"model TTS (mặc định {TTS_DEFAULT_MODEL})")
    gen.add_argument("--speed", type=float, help="tốc độ đọc 0.7–1.3 (1.0 = bình thường)")
    gen.add_argument("--format", help="định dạng audio (mặc định suy từ đuôi -o)")
    gen.add_argument("--sample-rate", type=int, help="sample rate Hz")
    gen.add_argument("--bitrate", type=int, help="bitrate cho định dạng nén")
    gen.add_argument("--config-json", help="JSON gộp thẳng vào payload TTS")
    _add_json_flag(gen)
    gen.set_defaults(func=cmd_tts_generate)

    # ---- voices ----
    voices = sub.add_parser("voices", help="voice cloning")
    voices_sub = voices.add_subparsers(dest="action", required=True)

    vls = voices_sub.add_parser("list", help="liệt kê voice")
    _add_json_flag(vls)
    vls.set_defaults(func=cmd_voices_list)

    vc = voices_sub.add_parser("create", help="tạo voice từ clip audio mẫu")
    vc.add_argument("sample", help="file audio mẫu")
    vc.add_argument("--name", required=True, help="tên voice (duy nhất trong project)")
    _add_json_flag(vc)
    vc.set_defaults(func=cmd_voices_create)

    vg = voices_sub.add_parser("get", help="chi tiết một voice")
    vg.add_argument("id")
    _add_json_flag(vg)
    vg.set_defaults(func=cmd_voices_get)

    vcnt = voices_sub.add_parser("count", help="đếm voice")
    _add_json_flag(vcnt)
    vcnt.set_defaults(func=cmd_voices_count)

    vr = voices_sub.add_parser("recompute", help="chuẩn bị voice cho model nó chưa sẵn sàng")
    vr.add_argument("id")
    vr.add_argument("--model", help="chỉ chuẩn bị cho một model (mặc định: mọi model còn thiếu)")
    _add_json_flag(vr)
    vr.set_defaults(func=cmd_voices_recompute)

    vd = voices_sub.add_parser("delete", help="xóa voice")
    vd.add_argument("id")
    _add_json_flag(vd)
    vd.set_defaults(func=cmd_voices_delete)

    # ---- models ----
    md = sub.add_parser("models", help="liệt kê model khả dụng")
    md.add_argument("--tts", action="store_true", help="liệt kê model TTS thay vì STT")
    _add_json_flag(md)
    md.set_defaults(func=cmd_models)

    # ---- usage ----
    us = sub.add_parser("usage", help="usage logs (mặc định 24h gần nhất, tối đa 91 ngày)")
    us.add_argument("--start", help="thời điểm bắt đầu ISO (vd 2026-07-01T00:00:00Z)")
    us.add_argument("--end", help="thời điểm kết thúc ISO")
    us.add_argument("--limit", type=int, default=1000)
    _add_json_flag(us)
    us.set_defaults(func=cmd_usage)

    # ---- update ----
    up_ = sub.add_parser("update", help="cập nhật soniox-cli lên bản mới nhất")
    up_.add_argument("--check", action="store_true", help="chỉ báo có bản mới không, không cài")
    up_.add_argument(
        "--no-check", action="store_true", help="bỏ qua bước hỏi GitHub, cập nhật luôn"
    )
    up_.add_argument("--force", action="store_true", help="cài lại kể cả khi đã là bản mới nhất")
    _add_json_flag(up_)
    up_.set_defaults(func=cmd_update)

    # ---- concurrency ----
    cc = sub.add_parser("concurrency", help="phiên đồng thời đang dùng và giới hạn cấu hình")
    _add_json_flag(cc)
    cc.set_defaults(func=cmd_concurrency)

    # ---- auth ----
    au = sub.add_parser("auth", help="kiểm tra xác thực")
    au_sub = au.add_subparsers(dest="action", required=True)
    ac = au_sub.add_parser("check", help="xác nhận API key hợp lệ")
    _add_json_flag(ac)
    ac.set_defaults(func=cmd_auth_check)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    run(args.func, args)


if __name__ == "__main__":
    main()
