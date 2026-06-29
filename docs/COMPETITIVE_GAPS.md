# Clippy vs Veed & Descript — Gap Tracker

Every feature Clippy is missing relative to **Veed** and **Descript**, derived from
a live browser walkthrough of both (2026-06-29). Worked top-down; each shipped
item is verified **end-to-end in the browser** before being marked done.

Legend: ⬜ todo · 🟡 in progress · ✅ done (E2E-verified) · ⏸️ deferred (out of
scope: not local-first, or disproportionate ML lift)

Clippy's edge over both: **fully local, free, private**. Keep every gap we close
local-first.

---

## Already at parity (shipped earlier)
Transcript editing · filler removal · AI highlights · 12 caption presets ·
face-tracked 9:16 reframe · aspect ratios · batch "export all shorts" ·
audio enhancement (denoise + loudnorm) · background blur/replace ·
in-app webcam/screen recording · conversational AI edit.

---

## Tier 1 — High leverage, local-first, ship first

### G1. Downloadable subtitles (SRT / VTT export) ✅ (E2E-verified)
Both Veed (Subtitle Editor/Converter) and Descript export caption files; Clippy
only burned captions in. We already have word/segment timestamps.
- [x] `backend/subtitles.py` builds SRT + VTT, grouping projected words into cues
      (timed on the edited/virtual timeline, so they match the export).
- [x] `GET /api/videos/{id}/subtitles.srt` + `.vtt` (attachment downloads).
- [x] ".srt / .vtt" download buttons in the Captions panel.
- [x] 5 unit tests; **browser E2E**: buttons render + endpoints return valid,
      correctly-timed cues from the real transcript (8 cues, standard format).

### G2. Translate & dub — multilingual subtitles ✅ (E2E-verified)
Both treat translation as core (Veed: 50+ langs; Descript: Translate & dub).
- [x] `backend/translate.py` — line-level cue translation via local gemma4,
      one batched strict-JSON call, timings preserved, falls back to source on
      parse failure. 12-language allowlist (no injected target strings).
- [x] `?lang=` on the subtitle endpoints + `GET /api/subtitles/languages`.
- [x] Language picker in the Captions download section.
- [x] 6 tests (incl. real gemma4 round-trip); **browser E2E**: fetched Spanish
      ("Hola, hice algo loco ayer.") and Japanese ("昨日、クレイジーな…") SRTs —
      accurate, timestamps intact, JLPT acronym preserved.
- Dub/TTS audio stays Tier 3 (generative). Subtitles done.

### G3. Use-case template / prompt-first home ✅ (E2E-verified)
Both lead with "describe what you want" + use-case templates. Clippy dropped you
straight into the editor.
- [x] `templates.js` — 4 outcomes (Talking-head reel, Podcast clip, Subtitled
      short, Square promo), each with settings + a starter AI prompt.
- [x] Home cards: select one → it configures the upload (settings merged after
      upload) and stashes a starter prompt the AI panel pre-fills.
- [x] **Browser E2E**: selected "Talking-head reel" → uploaded → new video came
      out 9:16 · blur · karaoke · enhance, AI prompt pre-filled. E2E surfaced a
      React-StrictMode bug (side effect in a useState initializer wiped the
      stash on the double-mount) — fixed to a pure read.

### G4. Platform resize presets ⬜
Veed has explicit "Resize for TikTok/Reels/Shorts/Square". We have aspect ratios
but not named platform presets.
- [ ] One-click presets mapping platform → aspect + caption defaults.

### G5. Animated / richer subtitle styles ⬜
Veed "Animated Subtitles". We have static presets; add word pop / slide-up.

### G6. Subtitle editor ⬜
Edit caption text/timing directly (both have it). We have transcript edit; expose
a caption-row editor.

---

## Tier 2 — Real gaps, heavier but local-feasible

### G7. Speaker diarization / multi-speaker labels ⬜
Descript labels speakers; enables per-speaker captions. Local via pyannote/whisperx
(gated-model risk — like the GLM pull).

### G8. Eye-contact correction ⬜
Both have it. Needs a specialized local model; heavy.

### G9. Multi-camera / Sequences ⬜
Descript multi-cam. Large editor-model change.

### G10. Teleprompter ⬜
Veed has it; pairs with the recorder. Frontend-only, easy-ish.

### G11. Text / sticker / emoji overlays, transitions, progress bar ⬜
Veed editing extras. Each is a per-frame render addition.

---

## Tier 3 — Generative / SaaS scope (deferred: not Clippy's local-first niche)
- ⏸️ AI B-roll generator, AI avatars / talking-head, text-to-video, slides-to-video
- ⏸️ Voice cloning / TTS / Overdub (generative audio)
- ⏸️ Hosting / published pages / video player
- ⏸️ Workspaces, comments, brand kit, real-time collaboration
- ⏸️ 50+ language TTS/dubbing SEO surface

---

## Changelog
- 2026-06-29 — Doc created from live Veed + Descript walkthrough. Starting G1
  (downloadable SRT/VTT subtitles).
- 2026-06-29 — ✅ G1 shipped + browser-E2E-verified (SRT/VTT builders, endpoints,
  Captions-panel download buttons, 5 tests; 45 backend tests green).
- 2026-06-29 — ✅ G2 shipped + browser-E2E-verified (local gemma4 translation,
  12 languages, language picker; 51 backend tests green).
- 2026-06-29 — ✅ G3 shipped + browser-E2E-verified (prompt-first home with 4
  use-case templates that configure the upload + pre-fill the AI prompt; E2E
  caught & fixed a StrictMode initializer bug). Next: G4 (platform resize presets).
