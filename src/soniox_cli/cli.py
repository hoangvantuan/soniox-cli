"""CLI bọc Soniox SDK.

Thiết kế: chỉ phần request/response (async STT, files, TTS REST, voices, metadata).
Không bọc realtime streaming (WebSocket) vì không hợp mô hình một-lệnh-một-kết-quả.

Output mặc định là text người-đọc-được; cờ toàn cục --json in JSON đầy đủ.
Lỗi ra stderr, exit code != 0.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, NoReturn

STT_DEFAULT_MODEL = "stt-async-v5"
TTS_DEFAULT_MODEL = "tts-rt-v1"
TTS_DEFAULT_VOICE = "Adrian"
EXAMPLE_AUDIO_URL = "https://soniox.com/media/examples/coffee_shop.mp3"

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
    """Khởi tạo SonioxClient. SDK tự đọc SONIOX_API_KEY từ môi trường."""
    import os

    if not os.environ.get("SONIOX_API_KEY"):
        die("chưa có SONIOX_API_KEY. Chạy: export SONIOX_API_KEY=<key>")
    from soniox import SonioxClient

    return SonioxClient()


def jsonable(obj: Any) -> Any:
    """Chuyển model Pydantic / list model thành cấu trúc JSON-serializable."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    return obj


def emit(args, data: Any, human) -> None:
    """In kết quả: --json -> JSON đầy đủ; ngược lại -> dạng người đọc.

    `human` là chuỗi, hoặc callable(data)->str.
    """
    if getattr(args, "json", False):
        print(json.dumps(jsonable(data), ensure_ascii=False, indent=2, default=str))
        return
    text = human(data) if callable(human) else human
    print(text)


def run(fn, args) -> None:
    """Bọc lời gọi API: dịch các exception Soniox thành lỗi CLI gọn."""
    from soniox.errors import SonioxError

    try:
        fn(args)
    except SonioxError as e:  # gồm SonioxAPIError và các lớp con
        req = getattr(e, "request_id", None)
        suffix = f" (request_id={req})" if req else ""
        die(f"lỗi Soniox: {e}{suffix}")
    except TimeoutError as e:
        die(str(e) or "hết thời gian chờ")


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
    if getattr(args, "config_json", None):
        extra = _load_config_json(args.config_json)
        cfg.update(extra)
    if not cfg:
        return None
    from soniox.types import CreateTranscriptionConfig

    try:
        return CreateTranscriptionConfig(**cfg)
    except Exception as e:  # pydantic ValidationError, ...
        die(f"cấu hình STT không hợp lệ: {e}")


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
def cmd_stt_transcribe(args) -> None:
    client = get_client()
    src = resolve_audio_input(args)
    cfg = build_stt_config(args)
    model = args.model or STT_DEFAULT_MODEL

    if args.no_wait:
        tr = client.stt.transcribe(model=model, config=cfg, **src)
        emit(
            args,
            tr,
            lambda d: f"id: {d.id}\nstatus: {d.status}\n"
            f"(lấy transcript sau: soniox stt transcript {d.id})",
        )
        return

    try:
        transcript = client.stt.transcribe_and_wait_with_tokens(
            model=model,
            config=cfg,
            delete_after=not args.keep,
            wait_timeout_sec=args.timeout,
            **src,
        )
    except TimeoutError:
        die(
            f"hết thời gian chờ ({args.timeout}s). Dùng --no-wait để lấy id rồi "
            f"poll bằng 'soniox stt transcript <id>', hoặc tăng --timeout."
        )
    if args.json:
        print(json.dumps(jsonable(transcript), ensure_ascii=False, indent=2, default=str))
    else:
        print(format_transcript_text(transcript, args.diarize))


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
    resp = client.stt.list(limit=args.limit)
    rows = resp.transcriptions
    emit(
        args,
        rows,
        lambda d: "\n".join(f"{t.id}  {t.status:<10}  {t.filename or ''}" for t in d)
        or "(chưa có transcription nào)",
    )


def cmd_stt_transcript(args) -> None:
    client = get_client()
    t = client.stt.get_transcript(args.id)
    if args.json:
        print(json.dumps(jsonable(t), ensure_ascii=False, indent=2, default=str))
    else:
        print(t.text)


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
    f = client.files.upload(str(p))
    emit(
        args,
        f,
        lambda d: f"id: {d.id}\nfilename: {d.filename}\nsize: {getattr(d, 'size', '?')}",
    )


def cmd_files_list(args) -> None:
    client = get_client()
    resp = client.files.list(limit=args.limit)
    emit(
        args,
        resp.files,
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
    if override:
        return override
    return _SUFFIX_TO_FORMAT.get(path.suffix.lower(), "wav")


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
        payload["speed"] = args.speed
    if args.config_json:
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


def cmd_voices_delete(args) -> None:
    client = get_client()
    _request_json(client, "DELETE", f"/voices/{args.id}")
    emit(args, {"deleted": args.id}, f"đã xóa voice {args.id}")


# --------------------------------------------------------------------------- #
# Lệnh metadata: models / usage / auth
# --------------------------------------------------------------------------- #
def cmd_models(args) -> None:
    client = get_client()
    resp = client.tts_models.list() if args.tts else client.models.list()
    models = getattr(resp, "models", resp)
    emit(
        args,
        models,
        lambda d: "\n".join(getattr(m, "id", None) or getattr(m, "name", str(m)) for m in d)
        or "(không có model)",
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
    emit(
        args,
        data,
        lambda d: json.dumps(jsonable(d), ensure_ascii=False, indent=2, default=str)
        if entries
        else f"(không có bản ghi usage trong khoảng {start} .. {end})",
    )


def cmd_auth_check(args) -> None:
    client = get_client()
    resp = client.models.list()
    n = len(getattr(resp, "models", []) or [])
    emit(args, {"ok": True, "stt_models": n}, f"OK — API key hợp lệ ({n} model STT khả dụng)")


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
def _add_json_flag(p: argparse.ArgumentParser) -> None:
    p.add_argument("--json", action="store_true", help="in JSON đầy đủ thay vì text")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="soniox",
        description="CLI Soniox: STT / TTS / Files / Voices (chỉ request-response, không realtime).",
    )
    _add_json_flag(parser)
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
    _add_json_flag(tr)
    tr.set_defaults(func=cmd_stt_transcribe)

    g = stt_sub.add_parser("get", help="lấy metadata một transcription")
    g.add_argument("id")
    _add_json_flag(g)
    g.set_defaults(func=cmd_stt_get)

    ls = stt_sub.add_parser("list", help="liệt kê transcription")
    ls.add_argument("--limit", type=int, default=100)
    _add_json_flag(ls)
    ls.set_defaults(func=cmd_stt_list)

    ts = stt_sub.add_parser("transcript", help="lấy transcript text của một transcription")
    ts.add_argument("id")
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

    up = files_sub.add_parser("upload", help="upload file audio")
    up.add_argument("path")
    _add_json_flag(up)
    up.set_defaults(func=cmd_files_upload)

    fls = files_sub.add_parser("list", help="liệt kê file")
    fls.add_argument("--limit", type=int, default=100)
    _add_json_flag(fls)
    fls.set_defaults(func=cmd_files_list)

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
