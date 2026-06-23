# Clippy

Local-first tool that turns one long video into vertical short-form clips, edited
by editing the transcript. All processing is **local and free**: ffmpeg +
faster-whisper + mediapipe + gemma4 (via Ollama). No paid cloud APIs.

This README documents the project **through the current milestone (M2)**. Later
milestones (highlight detection, vertical export, SaaS shell) are added in order
and this file grows with them.

- **M0**: upload + SQLite job queue + worker (ffprobe metadata).
- **M1**: faster-whisper transcription with word-level timestamps; transcript
  shown in the UI synced to the video player (active word highlights during
  playback; click a word to seek).
- **M2**: Descript/Veed-style non-destructive editor. All edits are driven by a
  single **Edit Decision List** (ordered `{sourceStart,sourceEnd}` segments); the
  transcript, timeline, and live preview are pure projections of it, so they
  never desync (see `docs/superpowers/specs/2026-06-23-clipforge-editor-design.md`).
  - **Transcript**: click a word to seek; drag-select or double-click + Delete to
    cut; **Detect filler words** marks fillers (um/uh/like/"you know"…) for review.
  - **Timeline**: clip cards with waveform, drag trim handles, **Split at
    playhead**, ✕ ripple-delete, drag-to-reorder. Molten-amber playhead.
  - **Live preview** reflects edits immediately (non-destructive playback across
    segments); **Undo/Redo**; edits autosave (survive reload via `?v=<id>` URL).
  - **Export** bakes the saved EDL with ffmpeg (re-encoded, frame-accurate) in
    segment order, to `data/exports/<video_id>/<job_id>.mp4`.

  Filler list overridable via `CLIPFORGE_FILLER_WORDS`. Tests: `cd frontend &&
  npm test` (vitest, EDL logic) and `./.venv/bin/python -m pytest backend/tests`.
- **M3**: gemma4 highlight detection (pluggable `backend/llm.py`). A `highlights`
  worker job reads the transcript text and proposes candidate clips
  (start/end/reason/score), shown in the Highlights rail with heat-ring scores.
  "Use clip" narrows the editor to that range to trim and export — never
  auto-finalized. Strict-JSON parse, retry-once-stricter, raw surfaced on
  failure; never fabricates.
- **M4**: vertical (9:16) export. `export_vertical` worker job renders the edit,
  then in one frame-by-frame pass: mediapipe face-tracked crop to 1080×1920
  (center-crop fallback when no face), and karaoke word-level captions drawn with
  Pillow (configurable font/size/colour/position via job params). Output plays
  with audio. "Make 9:16 short" in the toolbar.

### Transcription performance (Apple Silicon CPU)

faster-whisper runs on CPU on Apple Silicon (CTranslate2 has no Metal/GPU path).
`scripts/bench_whisper.py` measured config tradeoffs on an M3; on this machine
`int8` is the fastest compute type (faster than `float32`) and using all logical
cores helps. Measured ~1.9x realtime for `large-v3` (a 1-hour video ~= 1.9h).

Tunable via env vars (defaults shown are the measured-best on M3):

| Env var | Default | Notes |
|---|---|---|
| `CLIPFORGE_WHISPER_MODEL`   | `large-v3` | `medium`/`small` are faster, less accurate |
| `CLIPFORGE_WHISPER_COMPUTE` | `int8`     | compute type passed to CTranslate2 |
| `CLIPFORGE_WHISPER_THREADS` | all cores  | CPU threads |

Re-run the benchmark with:
`./.venv/bin/python scripts/bench_whisper.py /path/to/short.wav`

## Architecture

```
frontend/   React + Vite UI (upload, job table; grows per milestone)
backend/    FastAPI app — enqueues jobs, serves data. NO heavy work here.
  app.py      HTTP endpoints (upload, videos, jobs)
  db.py       SQLite schema + job queue (status queued/running/done/failed)
  config.py   filesystem paths (override with env for server deploys)
worker/     Separate process. Pulls one job at a time and runs it.
  worker.py   poll loop + restart-safe orphan requeue + job dispatch
  steps/      individual processing steps (M0: probe.py -> ffprobe metadata)
data/
  input/      drop a real source video here during dev
  uploads/    files received by the upload endpoint (one dir per video id)
  db/         SQLite database (clipforge.db, WAL mode)
```

The API and worker are **separate processes** sharing the SQLite database.
The worker runs exactly **one job at a time** (16 GB Apple Silicon constraint).

## Prerequisites (verified on this machine)

- ffmpeg / ffprobe 8.1.2 (`brew install ffmpeg`). Note: captions are drawn in
  Python (Pillow), so a libass-less ffmpeg build is fine.
- Python 3.12 virtualenv at `.venv` with deps from `requirements.txt`
- Ollama running with model `gemma4:latest` (used from M3 onward)
- MediaPipe face-detector model (one-time, for vertical reframe):
  ```bash
  mkdir -p data/models
  curl -L -o data/models/blaze_face_short_range.tflite \
    https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite
  ```

Recreate the Python environment if needed:

```bash
cd clipforge
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

## Run it (M0)

Open **three** terminals from the `clipforge/` directory.

1. **API** (FastAPI on http://127.0.0.1:8000):
   ```bash
   ./scripts/run_api.sh
   ```

2. **Worker** (separate process):
   ```bash
   ./scripts/run_worker.sh
   ```

3. **Frontend** (Vite dev server on http://localhost:5173):
   ```bash
   cd frontend
   npm install      # first time only
   npm run dev
   ```

Then open http://localhost:5173, choose a real video, and click **Upload**.
You will see a job appear in the table and move `queued -> running -> done`,
with the real ffprobe metadata (resolution, duration, fps, codecs) shown when
it finishes.

### Or test the API directly with curl

```bash
curl -F "file=@data/input/YOUR_VIDEO.mp4" http://127.0.0.1:8000/api/upload
curl http://127.0.0.1:8000/api/jobs
```

## Restart safety

Jobs live in SQLite, not memory. If the worker is killed mid-job, on restart it
requeues any job left in `running` (see `db.reset_orphaned_jobs`). The queue and
all video records survive an API or worker restart.

## What is NOT built yet

Per the milestone plan, only M0 (upload + job queue + worker probe step) exists.
Transcription, transcript editing, highlight detection, reframing/captions, and
the multi-user SaaS shell are added in M1–M5.
