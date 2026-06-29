# Clippy — Feature Roadmap & Status

Tracks the gaps between Clippy's **original motive** (one long video → many
captioned vertical shorts, local + free) and what's shipped, plus parity gaps
vs. Veed and Descript. Status is updated as work lands.

Legend: ⬜ not started · 🟡 in progress · ✅ done · ⏸️ deferred (out of scope for
now)

Local AI: Ollama + `gemma4:latest` (verified running on GPU, 2026-06-29).

---

## Tier 1 — Core to Clippy's own mission (build these)

### 1. Batch multi-clip export ✅
**Why:** The headline promise is "one long video → vertical clip*s* (plural)."
Today "Use clip" narrows the editor to one range and exports one file. No
one-pass flow emits N shorts from a single source.
- [x] Backend: `export_batch` worker job (`worker/steps/export_batch.py`) —
      renders each clip range as its own 9:16 short, reusing the extracted
      `render_vertical_clip` pipeline; one bad clip can't sink the batch.
- [x] Refactor: extracted `render_vertical_clip` + `load_reframe` from
      `vertical.py` so single and batch export share identical rendering.
- [x] API: `POST /api/videos/{id}/export_batch` (clips from body or fall back to
      stored highlights) + `GET /api/exports/{job_id}/clip/{index}/file`.
- [x] DB: per-clip outputs tracked in the job's `result_json` (no schema change).
- [x] Frontend: "Export all N as 9:16 shorts" in the Highlights rail + per-clip
      download links (`HighlightsRail.jsx`, `useBatchExport`).
- [x] Tests: `test_export_batch_renders_multiple_shorts` (renders real
      1080×1920 files) + `test_normalize_clips_clamps_and_drops_slivers`.
      All 33 backend + 18 frontend tests pass; frontend build clean.

### 2. Audio enhancement / noise removal ✅
**Why:** Descript **Studio Sound** / Veed audio cleaning. Cheap to do locally
(ffmpeg `afftdn` + `loudnorm`), high perceived-quality win.
- [x] Cleanup chain (`highpass` + `afftdn` + `loudnorm` to -16 LUFS) built into
      the shared `render_segments` filtergraph (`export_edit.py`), so it applies
      to both the edited export and the vertical/batch exports.
- [x] Per-video `enhance_audio` setting (default off) in `DEFAULT_SETTINGS` +
      `SettingsBody`; threaded through every export path.
- [x] Frontend `AudioPanel` with an iOS-style toggle (new "Sound" tool group).
- [x] Test `test_export_with_audio_enhancement` (renders with the chain). Green.

### 3. Conversational / iterative AI editing ✅
**Why:** Veed **AI Copilot** / Descript **Underlord** take multi-step natural
language and give feedback. Clippy's `ai_edit.py` was one-shot only.
- [x] DB `ai_edit_turns` table (one row per turn) + `append/get` helpers.
- [x] `detect_ai_edit` now loads prior turns and includes them in the prompt so
      follow-ups refine instead of restart (`_history_block`).
- [x] Worker records every turn; new `GET …/ai_edit/turns` endpoint.
- [x] `AiEditPanel` rebuilt as a chat thread (you/AI bubbles, per-turn Apply,
      ⌘/Ctrl+Enter to send); `useAiEdit` keeps the running thread.
- [x] Tests (history block, prompt-includes-history, turns roundtrip). Verified
      end-to-end against gemma4 (2-turn refine). All 38 backend + 18 frontend green.
- Note: refinement *quality* is model/content-dependent — strong on real long
  videos, weak on the 25s sample (loose ±10s length tolerance). Plumbing is solid.

### 4. Speaker diarization ⬜
**Why:** Pairs naturally with the transcription we already do; enables
speaker-labeled cuts. Local via pyannote or whisperx.
- [ ] Diarize during/after transcription; attach speaker labels to words.
- [ ] Show speaker labels in transcript; optional per-speaker caption colour.
- [ ] Tests.

### 5. Subtitle translation / multi-language output ⬜
**Why:** Veed's strength (100+ languages). Whisper already gives us the source;
translate captions locally via gemma4 or whisper's translate task.
- [ ] Translate caption track to a target language (gemma4 or whisper translate).
- [ ] Language picker in caption settings.
- [ ] Tests.

---

## Tier 2 — Competitor parity, fits the local-first stack

### 6. In-app screen + webcam recording ✅ (build-verified)
Both Veed and Descript capture in-browser; Clippy was upload-only.
- [x] `useRecorder` hook — MediaRecorder for **webcam+mic** or **screen+mic**,
      live preview, elapsed timer, produces a webm Blob.
- [x] `RecorderModal` — source toggle, record/stop, playback, re-record, "Use
      this recording" → hands the webm to the existing upload flow (no backend
      change; ffmpeg/whisper ingest webm fine).
- [x] Entry points: "● Record" in the topbar + "Record instead" on the welcome
      screen. Removed the sidebar "soon" placeholder.
- [x] Frontend build + vitest green.
- Note: needs a live camera/screen test (this session has no device/browser);
      the MediaRecorder logic is standard and compiles clean.

### 7. Background removal / green screen ✅ (incl. custom image / green-screen)
Local via mediapipe selfie-segmentation; composite over a colour, blur, or photo.
- [x] Downloaded `selfie_segmenter.tflite`; `SEGMENT_MODEL_PATH` in config.
- [x] `backend/segment.py` `BackgroundSegmenter` (Tasks API ImageSegmenter):
      per-frame person mask, feathered, composited over blurred frame or a flat
      colour. Runs on the M3 GPU (Metal).
- [x] Wired into the vertical export frame loop (`_reframe_and_caption`), created
      once per render from the `background` setting and closed after.
- [x] `background` setting (mode none/blur/color + color) in `DEFAULT_SETTINGS`
      + `SettingsBody`.
- [x] `BackgroundPanel` (Keep/Blur/Color + colour picker) in the Style tool group.
- [x] Tests: segmenter shape test + full 1080×1920 export with blur. 40 backend
      tests green. **Verified live in the browser** (panel, mode switch, picker).
- [x] **Image / green-screen replace** (2026-06-29): `BackgroundSegmenter` gained
      an `image` mode — composites the speaker over a custom photo (cover-fit,
      cached). `POST/GET /api/videos/{id}/background_image` store + serve it;
      BackgroundPanel gained an **Image** card + upload + thumbnail. Test +
      **browser E2E**: uploaded a gradient photo → export shows the speaker over
      it (original background gone). 63 backend tests green.

### 8. Eye-contact correction ⬜
Both competitors have it. Heavier ML lift; evaluate local models.

---

## UI — Veed/Descript-grade editor shell ✅ (this pass)
Goal: every feature discoverable, like Veed/Descript but more distinctive.
- [x] **Left tool rail** (`Sidebar.jsx`) replacing the old right tabs — grouped
      Create / Style / Sound / More, each tool labeled, active-tool accent bar.
- [x] **All features surfaced**: AI edit, Highlights (+ Export all), Captions,
      Reframe, Audio; "More" group shows Translate / Record / Background as
      visible **soon** entries so the roadmap reads as one surface.
- [x] **Export menu** (`Toolbar.jsx`) gathering 9:16 short + edited video in one
      place, with a pointer to batch export.
- [x] **AudioPanel** with toggle + iOS switch; CSS polish (violet-on-charcoal
      identity kept — not a generic AI default).
- [ ] Live screenshot verification still pending (Chrome extension not connected
      this session); build + vitest green.

---

## Tier 3 — Broader SaaS scope (deferred — not Clippy's niche)

- ⏸️ Stock media library, music, transitions, B-roll, animated overlays
- ⏸️ Generative AI video (script → rough cut with stock + AI voiceover)
- ⏸️ Voice cloning / TTS / Overdub (add-audio, not just cut)
- ⏸️ Multi-camera / Sequences
- ⏸️ Collaboration: shared workspaces, commenting, brand kits
- ⏸️ Hosting / publishing / sharing
- ⏸️ Concurrent multi-user processing (worker is intentionally one-job-at-a-time
      on 16 GB) — revisit only for a real server deployment

---

## Changelog
- 2026-06-29 — File created. Verified Ollama + gemma4 running locally. Started
  Tier-1 #1 (batch multi-clip export).
- 2026-06-29 — ✅ Tier-1 #1 batch multi-clip export shipped (backend job + API +
  per-clip download + frontend rail action + tests, all green).
- 2026-06-29 — ✅ Tier-1 #2 audio enhancement shipped (ffmpeg cleanup chain in
  the shared filtergraph, per-video toggle, AudioPanel, test). 34 backend + 18
  frontend tests green.
- 2026-06-29 — ✅ UI redesign: Veed/Descript-style left tool rail surfacing every
  feature + grouped tools + Export menu + Audio panel. Build clean.
- 2026-06-29 — GLM abandoned: local `glm4` pull truncates ~5 MB from done every
  time (network/registry wall, 3 attempts); `glm-5.2:cloud` is 403 subscription-
  gated. UI was built without it.
- 2026-06-29 — ✅ Tier-1 #3 conversational AI editing (ai_edit_turns table,
  history-aware prompt, chat-thread panel, tests; verified vs gemma4).
- 2026-06-29 — ✅ Tier-2 #6 in-app recording (webcam/screen MediaRecorder modal
  → existing upload). Build-verified; needs a live device test.
- 2026-06-29 — ✅ Tier-2 #7 background removal (mediapipe selfie segmentation,
  blur/colour, BackgroundPanel). 40 backend tests green; verified live in browser.
- 2026-06-29 — Browser verification pass: tool rail, Audio toggle, Export menu,
  Highlights "Export all 5", conversational AI edit (real gemma4 round-trip),
  Background panel — all confirmed working in the running app.
- Still open: Tier-1 #4 diarization, #5 translation; Tier-2 #8 eye-contact —
  heavier ML / rabbit-hole-prone; flagged for a focused pass.
