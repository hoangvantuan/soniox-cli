---
name: soniox
description: >-
  Speech-to-Text and Text-to-Speech via the `soniox` CLI: transcribe,
  subtitles, speaker diarization, audio translation, TTS, voice cloning.
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

| Command                                                          | What it does                                                           |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------- |
| `soniox stt transcribe <file\|url>`                              | Transcribe. By default **waits, prints the text, cleans up** on Soniox |
| `soniox stt transcribe <x> --no-wait`                            | Returns the `id` within seconds; poll later. Use when the process may not survive the wait |
| `soniox stt transcribe <x> --subtitles srt\|vtt`                 | Emit **subtitles**                                                     |
| `soniox stt transcribe <x> --timestamps`                         | Plain text broken into **speaking turns**, each line starting with `[HH:MM:SS]` |
| `soniox stt get\|transcript\|list\|count\|delete\|delete-all`    | Manage transcriptions                                                  |
| `soniox stt transcript <id>`                                     | Fetch the transcript of an existing job. Speakers and translations are rendered automatically |
| `soniox stt transcript <id> --destroy`                           | Same, then clean up the transcription **and** its file                 |
| `soniox files upload\|list\|get\|count\|delete\|delete-all`      | Uploaded audio files                                                   |
| `soniox tts generate "<text>" -o out.wav`                        | Text → audio file                                                      |
| `soniox voices list\|get\|create\|count\|recompute\|delete`      | Voice cloning                                                          |
| `soniox models [--tts]` · `usage` · `concurrency` · `auth check` | Metadata                                                               |
| `soniox update [--check]`                                        | Update the CLI to the latest version                                   |

Add `--json` to any command for the full JSON (token level: timestamp, speaker, confidence, language).

On `stt transcribe` and `stt transcript`, `--json` honours `-o` and the size warning. A two-hour meeting is roughly 16 MB of JSON, so always pair them: `--json -o /tmp/x.json`. Other commands print JSON to stdout; redirect with `>` if it could be large.

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

## Waiting: pick by process lifetime, not by audio length

The job runs on Soniox, not on this machine. The only question worth asking is: **will this process outlive the wait?**

```bash
# Process is safe for the duration (short clip, interactive shell): just wait.
soniox stt transcribe short.mp3 -o /tmp/out.txt

# Process might not survive (long upload, near a session/turn boundary, anything
# that could be torn down): take the id first, then poll. Process lifetime stops mattering.
id=$(soniox stt transcribe long.mp4 --no-wait --ref meeting-2026-09-13 --json | jq -r .id)
echo "$id" > /tmp/soniox-job.id          # write it somewhere that outlives this process
soniox stt get "$id"                      # status: queued -> processing -> completed
soniox stt transcript "$id" -o /tmp/out.txt --destroy
```

Running in the background is **not** the same as being durable: a backgrounded process dies with its parent just the same. `--no-wait` returns the id within seconds, which is what actually makes the work survivable.

The id is also printed to **stderr** the moment the transcription is created, on every path, so a captured log is a second way back in.

While `transcribe` waits, the CLI also prints a heartbeat line to stderr roughly every 30 seconds (`đang chờ <id>: 1m30s; status: processing`), plus a warning line each time a poll fails and is retried. Those are liveness signals, not failures: judge a run by its **exit code**, never by stderr being non-empty.

## Recovery: the job almost certainly survived

A dead local process does not kill the job. Get it back:

```bash
soniox stt list                                   # id, status, created_at, duration, filename
soniox stt list --json | jq '.[] | select(.client_reference_id=="meeting-2026-09-13")'
soniox stt transcript <id> -o /tmp/out.txt        # pull the transcript
soniox stt transcript <id> --destroy              # pull it, then clean up transcription + file
```

- `--ref <label>` at `transcribe` time tags **both the uploaded file and the transcription**, which is the only way back if the process died mid-upload, before any id existed. Without it, match on `created_at` + `filename` + duration by eye.
- **`--no-wait` has no auto-destroy.** Nothing is cleaned up for you. Finish with `--destroy` or the quota fills up quietly.
- Ctrl-C and SIGTERM clean up local temp files and exit, but **never delete the remote job**. The id was already printed to stderr when the job was created. The leftover job is the thing that saves you; treat it as an asset, not as garbage.
- Transcriptions are deleted by Soniox 30 days after creation. That is the recovery window.

## Save context: write long audio to a file

By default the result goes to **stdout**, which is fine for short clips. For long recordings, dumping the whole transcript into context is wasteful: use `-o`, then read only what you need.

```bash
soniox stt transcribe meeting-2h.mp4 --timestamps -o /tmp/meeting.txt
wc -l /tmp/meeting.txt && head -40 /tmp/meeting.txt   # preview before deciding
grep -n "budget" /tmp/meeting.txt                     # go straight to what you need
```

**Use `--timestamps` for anything you intend to grep.** Without it the transcript is a *single line* (Soniox returns `transcript.text` that way), so `wc -l` says 0, `grep -n` gives one useless hit and `diff` is unusable. `--timestamps` breaks the text into **turns** (a run of tokens with no silence over 0.7s and no speaker change) and prefixes each with `[HH:MM:SS]`, so `grep -n` lands on a readable line you can seek to in the audio.

`-o` works for plain text, `--timestamps` and `--subtitles`, and the CLI creates parent directories. If `-o` is missing and the result is longer than 20,000 characters, the CLI prints a one-line hint on stderr.

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

# Process may not survive the wait: take the id first, poll, then clean up by hand
id=$(soniox stt transcribe long.mp3 --no-wait --ref my-label --json | jq -r .id)
soniox stt get "$id"                                    # queued -> processing -> completed
soniox stt transcript "$id" -o /tmp/out.txt --destroy    # --no-wait has no auto-destroy

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

- **Auto-destroy**: `transcribe` deletes the file and the transcription from Soniox once the text is retrieved (keeps the quota clear). Use `--keep` if `get`/`transcript` will be needed later. It only fires on a **completed** run: `--no-wait`, a timeout, Ctrl-C and SIGTERM all leave the job in place on purpose, and the CLI prints the id plus the commands to fetch or clean up.
- **Speakers and translations render themselves.** Both `transcribe` and `transcript` label speakers when the tokens carry them, and interleave translations when present. Use `--flat` to suppress speaker labels. (`--group-speakers` is a deprecated no-op kept for compatibility.) `--timestamps` adds an `[HH:MM:SS]` mark and breaks the text into turns; it cannot be combined with `--subtitles` or `--no-wait`.
- **STT input**: a local audio or video file, `--file-id`, or a URL that **downloads the audio file directly**. Video can only be extracted from a local file; for a URL, Soniox downloads on its side, so fetch it locally first to extract. YouTube / Drive / web page links will break (Soniox gets HTML back and reports "Invalid audio file"): download the file first and pass the local path. Do not pass `--file-id` together with a file or URL.
- **Subtitles**: `--subtitles srt|vtt`, add `-o <file>` to write to a file. `--subtitle-track` picks `auto` (default, uses the translation when there is one), `original`, `translation`, or `both` (bilingual). Cannot be combined with `--no-wait`.
- **Long files**: timeout is rarely the problem, **process lifetime is**. Soniox is fast (one measurement, 2026-09-13: 2h40m of audio finished in under 5 minutes, so the 600s default was never close to being hit); the local time goes into extracting and uploading. What actually kills a run is the local process dying. See "Waiting" above.
- **TTS**: `-o <file>` is required; the format is inferred from the extension (`.wav`, `.mp3`, `.flac`, `.opus`, `.aac`, `.pcm`). An unknown extension is an error, force it with `--format`. `--speed` ranges from 0.7 to 1.3.
- **Rare parameters**: `--config-json '{...}'` for both STT and TTS. A wrong field name errors out with the list of valid ones.
- **Errors**: go to stderr with a non-zero exit code. Read the message (it carries a `request_id`) to diagnose. stderr also carries non-error lines (the transcription id, the waiting heartbeat, retry warnings), so a non-empty stderr on its own means nothing.

## When details go beyond the CLI

Supported language list, parameter explanations, quota limits... → **WebFetch** the Soniox docs:
`https://soniox.com/docs/stt/concepts/supported-languages`, `https://soniox.com/docs/sdk/python-SDK`,
`https://soniox.com/docs/api-reference`. Dynamic data (models, voices) comes straight from: `soniox models`, `soniox voices list`.
