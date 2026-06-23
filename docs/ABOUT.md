# Clippy — Project Write-up

Clippy turns one long video into short, captioned, vertical clips — and lets you
edit by editing the transcript instead of scrubbing a timeline. Everything runs
locally and free (no paid cloud APIs).

## What it does
Upload a long video (podcast, talk, UGC, screen recording). Clippy transcribes
it locally, an AI proposes the strongest moments (and understands plain-English
instructions like "make a 40s Instagram reel"), you trim by deleting words or
dragging clips, choose a caption style and aspect ratio, and export a captioned,
face-tracked 9:16 short. Your media never leaves your machine.

## The problem it solves
Creators spend hours finding good moments in long footage, reframing 16:9 → 9:16,
and hand-timing captions. The tools that automate this (Opus Clip, Veed,
Descript) are cloud SaaS — you upload raw footage to someone else's servers and
pay per minute. Clippy does the same job **locally and free**: media stays
private, and the same stack can be self-hosted on a server later. Transcript-first
editing also lowers the skill floor — cutting a sentence is easier than scrubbing
a waveform.

## Tech used
- **Backend:** Python + FastAPI, SQLite (WAL) for state and a job queue.
- **Worker:** a separate process running one job at a time
  (probe → transcribe → waveform → highlights → reframe → export).
- **Transcription:** faster-whisper (`large-v3`) with word-level timestamps.
- **AI (highlights + plain-English edits):** gemma4 via Ollama — text-only,
  strict-JSON, behind a pluggable provider.
- **Video:** ffmpeg (cut/concat, re-encode), mediapipe (face detection),
  OpenCV + Pillow (frame-by-frame reframe + caption rendering).
- **Frontend:** React + Vite — a canvas compositor for the live preview and a
  custom timeline.
- **Tests:** pytest (26), vitest (18), Playwright E2E on the real video.

## How it's built — the two ideas that hold it together
1. **The EDL (Edit Decision List).** All editing state is one ordered list of
   `{sourceStart, sourceEnd}` segments. The transcript, timeline, and live
   preview are **pure projections** of it, so they can never disagree. Deleting
   words, splitting, ripple-deleting, and drag-reordering are all transforms of
   this list. Because the transcript is computed from the EDL in list order,
   reordering clips never corrupts it.
2. **"Preview == Export."** One per-video `settings` object (aspect, framing,
   caption preset) and one precomputed face-track trajectory are read by **both**
   the in-browser canvas preview and the server-side ffmpeg export — so what you
   see while editing is exactly what renders.

Everything heavy is a **worker job** persisted in SQLite, so the app survives
restarts, never blocks the request thread, and never runs gemma4 / whisper /
ffmpeg at the same time (a hard constraint on a 16 GB machine).

## Challenges I ran into
- **Whisper was ~7× too slow.** `large-v3` on CPU ran ~7× slower than realtime.
  Benchmarking showed it used only ~2 threads, and that `int8` (not `float32`) is
  fastest on Apple Silicon. Pinning 8 threads + int8 reached ~1.9× realtime — a
  3.7× speedup with identical output.
- **mediapipe's API had changed.** The installed build only exposed the new Tasks
  API (not `mp.solutions`), which needs a downloaded `.tflite` model — found and
  wired that up.
- **ffmpeg had no libass.** Burning ASS/subtitle captions failed because this
  ffmpeg lacked subtitle filters. Pivoted to drawing captions **per-frame with
  Pillow** during the reframe pass — better in the end: full karaoke control, no
  external dependency, server-portable.
- **Preview didn't match export.** Captions and the vertical crop only appeared
  after exporting. Fixed with a **canvas compositor** that shows crop + captions
  live, plus a precomputed face-track trajectory shared by preview and export.
  Bonus: moving detection out of the export loop made export **6.6× faster**
  (106 s → 16 s).
- **Subtle state bugs caught by verification:** a degenerate `[0,0]` EDL when the
  editor mounted before probe set the duration; reload losing the open video
  (fixed with a `?v=` URL); a racy transcript click-vs-select; an autosave that
  silently rejected sub-frame sliver segments. All found by driving the real
  browser, not by reading code.
- **AI under-targeting length.** gemma4 returned ~20 s clips for "40 s" requests
  until the prompt was tightened to enforce the target within ±10 s.

## What we learned
- **One source of truth beats syncing.** Making the transcript/timeline/preview
  projections of the EDL (and preview/export read one settings object) removed
  whole classes of "they drifted apart" bugs.
- **Verify by running the real thing.** Every milestone was proven by uploading
  the actual video and driving the real UI with Playwright — that's what surfaced
  the degenerate-EDL, reload, and autosave bugs.
- **Constraints force better design.** "No libass" → per-frame Pillow captions;
  "16 GB, one job at a time" → a clean sequential worker; "local-only" → a
  reproducible, private pipeline.
- **Measure before optimizing.** Both the whisper and export speedups came from a
  quick benchmark exposing the real bottleneck (thread count, redundant
  detection), not from guessing.
- **Milestones with real output keep scope honest.** Each stage (upload →
  transcript → edit → highlights → vertical → sidebar) shipped something
  demonstrably working before the next began.

## How it was built (milestones)
- **M0** — upload + SQLite job queue + worker (ffprobe metadata).
- **M1** — faster-whisper transcription, word-level timestamps, transcript synced
  to playback.
- **M2** — transcript + timeline editing (cut/split/ripple-delete/reorder), live
  non-destructive preview, filler-word removal, EDL export.
- **M3** — gemma4 highlight detection (candidate clips with reasons/scores).
- **M4** — 9:16 face-tracked vertical export with karaoke captions, live WYSIWYG
  preview.
- **Sidebar** — Veed/Descript-style panels: AI prompt-edit, 12 influencer caption
  presets, aspect ratios + auto/manual crop.
- **M5 (planned)** — multi-user SaaS shell (accounts, per-user isolation, queue).
