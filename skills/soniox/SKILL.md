---
name: soniox
description: >-
  Speech-to-Text and Text-to-Speech for ANY AUDIO FILE via Soniox, using the
  `soniox` CLI. Trigger when the task needs: transcription / turning audio into
  text ("transcribe", "phiên âm", "bóc băng", "audio to text", "make subtitles",
  "tạo phụ đề", "chuyển ghi âm thành chữ"); speaker separation (diarization);
  translating audio content into another language; speech synthesis / reading
  text aloud ("text to speech", "TTS", "đọc thành giọng nói", "tạo file audio
  từ text"); voice cloning; or when "soniox" is named directly. Accepts a local
  audio OR video FILE (audio is extracted before upload) and a direct-download
  audio URL, unlike skills that only fetch a platform's existing captions.
  CANNOT download from YouTube / Drive / web pages: fetch the file first. NOT
  for realtime microphone streaming.
---

# Soniox CLI

The `soniox` CLI wraps the Soniox SDK for STT / TTS / Files / Voice cloning. Runs locally, handles local audio files directly.

## Setup (once)

```bash
soniox auth check
```

- If the `soniox` command does not exist: `uv tool install git+https://github.com/hoangvantuan/soniox-cli`
- If it reports a missing key: `export SONIOX_API_KEY=<key>` (get one at https://console.soniox.com).
- If a flag documented here reports `unrecognized arguments`: the installed CLI is out of date, run `soniox update`.

## Command table

| Command | What it does |
|---|---|
| `soniox stt transcribe <file\|url>` | Transcribe. By default **waits, prints the text, cleans up** on Soniox |
| `soniox stt transcribe <x> --no-wait` | Returns the `id` right away (long jobs); poll later |
| `soniox stt transcribe <x> --subtitles srt\|vtt` | Emit **subtitles** |
| `soniox stt get\|transcript\|list\|count\|delete\|delete-all` | Manage transcriptions |
| `soniox stt transcript <id> --group-speakers` | Regroup by speaker (if the transcript has them) |
| `soniox files upload\|list\|get\|count\|delete\|delete-all` | Uploaded audio files |
| `soniox tts generate "<text>" -o out.wav` | Text → audio file |
| `soniox voices list\|get\|create\|count\|recompute\|delete` | Voice cloning |
| `soniox models [--tts]` · `usage` · `concurrency` · `auth check` | Metadata |
| `soniox update [--check]` | Update the CLI to the latest version |

Add `--json` to any command for the full JSON (token level: timestamp, speaker, confidence, language).

## Video: pass it straight in, do not convert it yourself

```bash
soniox stt transcribe meeting.mp4     # extracts audio, cleans up the temp file
```

The CLI detects a video stream with `ffprobe`, extracts the audio into a temp directory (stream copy, no re-encoding, so no quality loss), uploads only the audio, then **deletes the temp file in a `finally`**. Only what is needed gets uploaded:

```
tách audio khỏi video (aac) trước khi upload...
upload 55 KB thay vì 224 KB (meeting.m4a)
```

(The CLI's progress messages are in Vietnamese: "extracting audio from video (aac) before upload", "uploading 55 KB instead of 224 KB".)

**Do not run `ffmpeg` yourself and then clean up by hand.** The CLI already does it, and manual cleanup is the step most often missed when something fails midway.

- If `ffmpeg` is missing the CLI says so and how to install it. To run without ffmpeg anyway: `--no-extract-audio` (uploads the whole video; Soniox still accepts `mp4`/`webm`, it just costs bandwidth).
- To keep the extracted audio: `--keep-extracted`, the CLI prints the path and does **not** delete it. Delete it by hand when done.
- Familiar audio extensions (`.mp3`, `.wav`, `.m4a`, ...) go straight through, ffmpeg is never touched.

## Save context: write long audio to a file

By default the result goes to **stdout**, which is fine for short clips. For long recordings, dumping the whole transcript into context is wasteful: use `-o`, then read only what you need.

```bash
soniox stt transcribe meeting-2h.mp4 -o /tmp/meeting.txt
wc -l /tmp/meeting.txt && head -40 /tmp/meeting.txt   # preview before deciding
grep -n "budget" /tmp/meeting.txt                     # go straight to what you need
```

`-o` works for plain text and for `--subtitles`, and the CLI creates parent directories. If `-o` is missing and the result is longer than 20,000 characters, the CLI prints a one-line hint on stderr.

**Rule**: audio longer than roughly 10 minutes, or when only a summary / one excerpt is needed, write to a file first. Put temp files in `/tmp` and delete them afterwards.

## Updating

```bash
soniox update --check    # is there a newer version?
soniox update            # update if there is
```

`update` never overwrites its own install directory. It reads `uv-receipt.toml` to see how the CLI was installed, then calls the package manager's own command: `uv tool upgrade soniox-cli` for a git install. Installed some other way, it stops and prints the command to run instead of guessing.

`--force` adds `--reinstall`, for when `uv` believes the tool is already current and reports `Nothing to upgrade`.

## Common examples

```bash
# Transcribe a local file, get the text (auto-removed from Soniox afterwards)
soniox stt transcribe recording.mp3

# Video: pass it straight in, the CLI extracts audio and cleans up the temp file
soniox stt transcribe meeting.mp4 --diarize

# Long recording: write to a file, then read only what you need
soniox stt transcribe long-meeting.mp4 -o /tmp/meeting.txt && head -40 /tmp/meeting.txt

# Speaker separation + language hints (printed as "Speaker 1: ...")
soniox stt transcribe meeting.mp3 --diarize --language-hints vi,en

# Translate audio into Vietnamese (original and "→ vi: ..." interleaved)
soniox stt transcribe english.mp3 --translate vi
# Two-way translation
soniox stt transcribe call.mp3 --translate two-way:en,vi

# Long job: do not wait
id=$(soniox stt transcribe long.mp3 --no-wait --json | jq -r .id)
soniox stt transcript "$id"          # once status=completed

# SRT subtitles with speaker separation
soniox stt transcribe meeting.mp3 --diarize --subtitles srt -o meeting.srt
# Vietnamese subtitles for English audio (picks up the translation automatically)
soniox stt transcribe english.mp3 --translate vi --subtitles vtt -o english.vtt
# Bilingual subtitles
soniox stt transcribe english.mp3 --translate vi --subtitles srt --subtitle-track both

# Text-to-Speech
soniox tts generate "Xin chào" -o hello.mp3 --language vi --speed 1.1
echo "Long passage..." | soniox tts generate -o out.wav --language en   # read from stdin

# Voice cloning: build a voice from a sample clip, then use it when generating
soniox voices create sample.wav --name my_voice
soniox tts generate "Voice test" -o test.mp3 --voice <voice_id> --language en

# Update the CLI itself
soniox update --check

# Check quota and clean up
soniox usage                            # last 24h cost, grouped by model
soniox stt count && soniox files count  # what is still on Soniox
soniox stt delete-all --destroy --yes   # wipe everything (--yes required)
soniox concurrency                      # concurrent sessions and limits, to diagnose 429
```

## Important notes

- **Auto-destroy**: `transcribe` deletes the file and the transcription from Soniox once the text is retrieved (keeps the quota clear). Use `--keep` if `get`/`transcript` will be needed later. On `--timeout` (default 600s) the CLI prints the id plus the commands to fetch the result or clean up by hand.
- **STT input**: a local audio or video file, `--file-id`, or a URL that **downloads the audio file directly**. Video can only be extracted from a local file; for a URL, Soniox downloads on its side, so fetch it locally first to extract. YouTube / Drive / web page links will break (Soniox gets HTML back and reports "Invalid audio file"): download the file first and pass the local path. Do not pass `--file-id` together with a file or URL.
- **Subtitles**: `--subtitles srt|vtt`, add `-o <file>` to write to a file. `--subtitle-track` picks `auto` (default, uses the translation when there is one), `original`, `translation`, or `both` (bilingual). Cannot be combined with `--no-wait`.
- **Long files**: waits up to 600s by default. Longer than that, raise `--timeout`, or use `--no-wait` and poll with `stt transcript <id>`. On timeout the CLI prints the id plus the command to fetch the result.
- **TTS**: `-o <file>` is required; the format is inferred from the extension (`.wav`, `.mp3`, `.flac`, `.opus`, `.aac`, `.pcm`). An unknown extension is an error, force it with `--format`. `--speed` ranges from 0.7 to 1.3.
- **Rare parameters**: `--config-json '{...}'` for both STT and TTS. A wrong field name errors out with the list of valid ones.
- **Errors**: go to stderr with a non-zero exit code. Read the message (it carries a `request_id`) to diagnose.

## When details go beyond the CLI

Supported language list, parameter explanations, quota limits... → **WebFetch** the Soniox docs:
`https://soniox.com/docs/stt/concepts/supported-languages`, `https://soniox.com/docs/sdk/python-SDK`,
`https://soniox.com/docs/api-reference`. Dynamic data (models, voices) comes straight from: `soniox models`, `soniox voices list`.
