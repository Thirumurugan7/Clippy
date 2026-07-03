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

### G4. Platform resize presets ✅ (E2E-verified)
Veed has explicit "Resize for TikTok/Reels/Shorts/Square". We had aspect ratios
but not named platform presets.
- [x] "Resize for platform" chips in the Reframe panel: TikTok, Reels, Shorts,
      Insta 1:1, Insta 4:5, YouTube. Each sets aspect **and** caption position so
      text clears the platform's own UI (TikTok/Reels → center, others → bottom).
- [x] Active-state reflects current aspect+position; settings nested-merge keeps
      the chosen caption preset.
- [x] **Browser E2E**: TikTok → 9:16 + caption center (preset preserved);
      YouTube → 16:9, preview reshaped to landscape live, header updated.
      Frontend-only (no backend change).

### G5. Animated / richer subtitle styles ✅ (E2E-verified)
Veed "Animated Subtitles". We had static presets; added a word-pop.
- [x] `caption.animate` flag → both renderers. Active word scales up at the
      start of its window (POP_DUR 0.18s, +30%) easing back to 1.0.
- [x] Backend `captions.py`: `_draw_word_pop` renders the active word to a tile,
      scales it, composites centred (outline + fill). Frontend `captionLayout.js`:
      identical `popScale` via canvas transform — preview == export by construction.
- [x] "Animate words" toggle in the Captions panel.
- [x] 2 new caption tests; **browser E2E**: toggle persists (`caption.animate:
      true`, preset preserved) + rendered frames show the active word visibly
      popped vs the static render.

### G6. Subtitle editor ✅ (E2E-verified)
Edit caption text directly (both have it).
- [x] `backend/subtitle_edit.py` `replace_cue_words` — swaps the words under a
      cue for edited text, retiming them evenly across the cue span.
- [x] `PUT /api/videos/{id}/transcript/cue` + `db.update_transcript_words`.
- [x] `SubtitleEditor` panel (new "Subtitles" tool): per-line editable inputs
      with timecodes; saving re-fetches the transcript so captions update.
- [x] 3 tests; **browser E2E**: fixed "did"→"done" in line 1 → transcript pane
      updated AND the SRT download changed (`has_done: true, has_did: false`).
- Note: edits operate on the source transcript, so they flow to burned-in
  captions, the SRT/VTT downloads, and translations alike.

---

## Tier 2 — Real gaps, heavier but local-feasible

### G7. Speaker diarization / multi-speaker labels ✅
Descript labels speakers; enables per-speaker captions. Shipped **torch-free /
download-free** to dodge the pyannote/whisperx gated-model wall (the GLM-pull risk).
- [x] `backend/diarize.py` — ffmpeg → 16 kHz mono → per-segment **MFCC** embedding
      (mean+std) in pure numpy → L2-normalise → silhouette-picked **k-means**
      (stays at 1 speaker unless there's real separation; caps at `max_speakers`).
      No new deps (numpy + stdlib `wave` only), no model download.
- [x] `POST /api/videos/{id}/diarize` tags each transcript segment with a
      `speaker` index (synchronous — clustering is fast) and persists it onto
      `segments_json`; the transcript GET returns it.
- [x] Subtitle panel: **Detect speakers** button + per-line speaker chips
      (S1/S2… in distinct brand-family colours) + a speaker count.
- [x] Tests: MFCC shape, embedding, k-means **separates two synthetic voices**
      AND keeps one voice together, relabel-by-appearance, no-audio fallback,
      plus a **real end-to-end** endpoint test on the seeded short. 80 backend green.
- Optional follow-on: burned-in **per-speaker caption colour** in the export
  (needs speaker on projected words + preview parity in `captionLayout.js`);
  deferred to keep preview==export and this slice fully verified.

### G8. Eye-contact correction ⬜
Both have it. Needs a specialized local model; heavy.

### G9. Multi-camera / Sequences ⬜
Descript multi-cam. Large editor-model change.

### G10. Teleprompter ✅ (E2E-verified)
Veed has it; pairs with the recorder. Frontend-only.
- [x] Script textarea + scroll-speed slider in the recorder.
- [x] `Teleprompter` component — state-driven `translateY` scroll (survives
      StrictMode), loops at the end. Rehearsal mode in the modal (no camera
      needed) + auto-scrolls as an overlay during actual recording.
- [x] **Browser E2E**: typed a script, rehearsed — text scrolled smoothly from
      intro → tips → outro across captures. E2E caught a scrollTop+rAF stall
      under StrictMode; fixed with the state-driven transform.

### G11. Overlays — progress bar ✅ (E2E-verified) · text/stickers/transitions ⬜
Veed editing extras. Each is a per-frame render addition.
- [x] **Progress bar** in both renderers: a bar that fills with playback.
      Backend draws it on the BGR frame in `_reframe_and_caption` (clip duration
      from the kept EDL); preview draws the matching bar on the canvas.
- [x] `progress_bar` setting (enabled/color/position) + new "Overlays" panel/tool.
- [x] 2 tests; **browser E2E**: toggle + live preview bar (zoom-confirmed) +
      exported frames showing the bar at ~20% then ~80% width. 58 backend green.
### G11b. Overlays — text, colour emoji, fade transition ✅ (E2E-verified)
- [x] `backend/overlays.py` `build_overlay_layer` — renders all text overlays
      once to an RGBA layer (static), returned as (BGR, alpha); the export loop
      blends it onto every frame (cheap). Outlined, centred, top/center/bottom,
      size = fraction of height, colour.
- [x] Preview parity: `drawTextOverlays` on the canvas (same anchors).
- [x] `text_overlays` setting (list) + Overlays-panel UI: add / edit text /
      position / size / colour / remove.
- [x] 3 tests; **browser E2E**: added an overlay, edited it to "3 EDITING TIPS"
      → showed live in the preview → baked frame shows it at the top. 61 backend
      green.
- [x] **Colour-emoji bake**: overlay text is split into emoji/text runs (no RAQM
      fallback here), text drawn with DejaVu, emoji with the macOS colour-emoji
      font at a fixed strike then scaled, composed into the layer. E2E: a baked
      frame shows "🔥 HOT TAKE 🔥" with real colour fire emoji.
- [x] **Fade transition** (`transition.fade`): ffmpeg `fade=in/out` on the export
      + a matching canvas dim in the preview. E2E: faded-start frame measured
      31.5 mean brightness vs 132.3 mid-clip. Toggle in the Overlays panel.
- Cross-segment crossfades (xfade between EDL clips) remain a larger future item.

---

## Market scan — AI features rivals have that Clippy lacks (2026-07-01)

A fresh look at the most popular AI editors — **Opus Clip, Submagic, Vizard/Klap,
CapCut, Descript, Veed** — to find AI features we're still missing. Grouped by
whether they fit Clippy's **local-first, torch-free, gemma4-on-device** stack.
Legend as above. Sources listed at the bottom of this section.

### Group A — Local-first & feasible (this is where to concentrate)
These need no cloud, no gated models, no generative video — mostly gemma4 (already
running) + ffmpeg/opencv (already used). High leverage, on-brand.

- **A1. Virality / engagement score per clip ✅** (2026-07-03) — highlights now
  rank by gemma4 `score` (strongest hook first) in `parse_highlights`, feeding the
  existing heat-ring gauge. Future polish: score explicitly on hook/emotion/payoff
  axes rather than one confidence number.
- **A2. One-click "Auto-Edit" (agentic) ✅** (2026-07-03) — `autoEdit()` in
  `EditorPage`: picks the top-ranked highlight → sets the EDL to it → applies good
  defaults (9:16 auto-reframe, blur bg, karaoke+pop captions, enhance audio) →
  removes silences + fillers → opens the Captions panel. Surfaced as a ✨ Auto-Edit
  button in the Toolbar **and** a new **Publish** tool/panel. Reuses every existing
  step; no backend job needed.
- **A3. Silence / dead-air removal ✅** (2026-07-01) — Descript Magic Cut,
  Submagic. `backend/silences.py`: ffmpeg `silencedetect` → parsed ranges, padded
  inward so cuts don't clip speech, slivers dropped. `GET …/silences` returns
  source-time ranges + total; "Remove silences" button in the Toolbar drops them
  from the EDL (same review-then-apply flow as filler removal). 7 tests (parser,
  padding, open-ended, real seeded short). 87 backend + 18 frontend green.
- **A4. AI hook title + social copy ✅** (2026-07-03) — `backend/social.py` +
  `POST …/social`: one strict-JSON gemma4 call → title / hook / description /
  hashtags (normalised, clamped, safe fallback). Shown in the **Publish** panel as
  click-to-copy cards. Verified live on the seeded JLPT clip. 4 tests.
- **A5. Keyword-highlight captions ✅** (2026-07-03) — `is_keyword` heuristic
  (content word 4+ chars, not a stopword; offline, deterministic) in both
  renderers; `caption.emphasis` + `caption.emphasis_color` recolour the punchy
  words. Panel toggle + colour picker. Tests for keyword detection + fill.
- **A6. Auto-emoji captions ⬜** *(remaining — second wave)* — Vizard/Submagic drop
  a contextual emoji on the right beat. *Local plan:* a keyword→emoji dictionary
  (or gemma4 per cue) → append an emoji per caption line; we already bake colour
  emoji (G11b), so the render path exists. Touch: `captions.py` line render +
  `captionLayout.js` + a `caption.auto_emoji` setting + panel toggle + tests.
- **A7. Auto-zoom / punch-in ⬜** *(remaining — second wave)* — Submagic/Vizard
  push in on emphasis beats. *Local plan:* deterministic scale-keyframes (ease in/
  out) on the active caption line or scene changes, applied in the vertical export
  frame loop (`_reframe_and_caption` crop rect) + a matching preview transform;
  `caption`/`settings.zoom` toggle + intensity. No model needed.
- **A8. Chapters / show notes / timestamps ⬜** *(remaining — second wave)* —
  podcast staple. *Local plan:* gemma4 over the transcript → `{chapters:[{t,title}],
  summary}`; `POST …/chapters`; show in the Publish panel (copyable), optionally
  export as a YouTube-style timestamp list. Cheap add-on next to `social.py`.
- **A9. Studio-sound-grade audio (de-reverb / stem split) 🟡** *(remaining)* —
  Descript Studio Sound 4.0 separates voice/music and removes reverb. We denoise +
  loudnorm only. *Local:* de-reverb is doable in ffmpeg (`afftdn` tuning / an
  arnndn model); true stem separation wants an onnx Demucs-style model — heavier,
  evaluate before committing. Lower priority.

### Caption polish shipped alongside (2026-07-02/03)
Not from the original scan, but done while in the caption engine — worth logging:
- **Caption types (reveal)** ✅ — Highlight / Word build / One word / Clean line
  (Descript Karaoke/Clean/word-by-word). `caption.reveal`, both renderers.
- **Caption motion** ✅ — None/Pop/Bounce/Scale in/Float up/Drop in/Slide in/Stomp/
  Pulse (Veed's named animations). `caption.animation` + `word_anim` in both
  renderers (scale+offset+alpha), preview==export. Panel "Motion" chips.
- **Caption fonts** ✅ — Impact / Arial Black / Trebuchet / Verdana / Georgia +
  Default. `presets.FONTS` (existence-checked TTF + CSS family), `caption.font`.
- **Per-speaker caption colour** ✅ — pairs with diarization; `caption.speaker_colors`
  colours words by speaker in burn-in + preview (`attach_speakers` + `project_words`).

### Group B — Generative / cloud-heavy (stays deferred, not Clippy's niche)
Real features, but they need big generative models, stock libraries, or a cloud
account — against the local-first promise. Tracked, not planned.

- **B1. Auto B-roll ⬜** — Opus/Submagic/Vizard/CapCut insert contextual stock or
  AI-generated B-roll. Needs a stock library or a generative video model. (Note:
  even Opus's is unreliable — coffee-cup B-roll on a podcast-gear clip.)
- **B2. AI avatars / talking-head from script ⬜** — CapCut, Veed, Submagic Avatar
  Studio, HeyGen. Generative human synthesis.
- **B3. Script-to-video / text-to-video ⬜** — CapCut, Veed Gen-AI Studio, Runway,
  Pika. Full generative pipeline.
- **B4. Voice cloning / AI dubbing / TTS ⬜** — Veed (125+ langs), Descript
  Overdub 3.0, CapCut (269 voices). We translate *captions* locally; translated
  *spoken audio* in a cloned voice is generative. Big model + ethics surface.
- **B5. AI thumbnails ⬜** — Submagic ThumbMagic. Generative image.
- **B6. Generative outpaint / aspect expansion ⬜** — fill new pixels when changing
  aspect instead of cropping. Generative.
- **B7. Social scheduler / publishing ⬜** — Vizard/CapCut post to TikTok/Reels/
  Shorts. Cloud/account surface, not editing.

### Group C — Known non-generative gaps already tracked
- **Eye-contact correction (G8)** — specialized local model; **on hold** per
  current decision.
- **Multi-camera / sequences (G9)** — large editor change; on hold.
- **Cross-segment crossfades** — small, still open (see G11b note).

### ⭐ NEXT WAVE — pick up here (all local-first, scoped)
The concrete backlog to resume with. Ordered rough priority.
1. **A6 Auto-emoji captions** — keyword→emoji dict (or gemma4/cue); append per
   caption line; `caption.auto_emoji` toggle. Render path exists (colour-emoji bake).
2. **A7 Auto-zoom / punch-in** — scale-keyframes on emphasis beats in the export
   crop loop + preview transform; `settings.zoom` toggle + intensity.
3. **A8 Chapters / show notes** — `POST …/chapters` (gemma4) → chapters + summary
   in the Publish panel; optional YouTube timestamp export. Sits next to `social.py`.
4. **Drag caption position** — drag the caption block in the preview to set
   `caption.x`/`caption.y` offsets (both renderers honour them); replaces the
   bottom/center/top dropdown as the primary control.
5. **Timeline zoom + snapping** — zoom control on the timeline dock; snap trims/
   splits to word boundaries. Builds on the ruler already shipped.
6. **Per-platform export presets** — one-click "Export for TikTok/Reels/Shorts"
   in the export menu (aspect + caption position + safe-area already exist via
   CropPanel platform chips; wire them into export).
7. **A9 Studio-sound de-reverb** — ffmpeg dereverb tuning; stem split needs a model
   (evaluate). Lower priority.
8. **A1 score axes** — score highlights on explicit hook/emotion/payoff axes, not
   one confidence number.
- Housekeeping: **a large body of work is uncommitted on `main`** (translation,
  diarization, silence removal, redesign + icons + bright theme, caption
  types/motion/fonts/emphasis/speaker colour, Auto-Edit, social copy, keyboard
  shortcuts). Branch + commit before the next wave.

**Sources:** [Opus Clip](https://www.opus.pro/) · [Opus AI B-Roll](https://www.opus.pro/ai-b-roll) ·
[Submagic](https://www.submagic.co/) · [Vizard top clipping tools 2026](https://vizard.ai/blog/top-5-ai-clipping-tools-2026) ·
[CapCut 2026 AI suite](https://bibigpt.co/en/features/capcut-2026-ai-suite-explained) ·
[Descript Underlord](https://www.descript.com/underlord) · [Descript Eye Contact](https://www.descript.com/tools/ai-eye-contact) ·
[VEED](https://www.veed.io/) · [VEED AI dubbing](https://www.veed.io/tools/voice-dubber/ai-dubbing) ·
[AI editing trends 2026 (Metricool)](https://metricool.com/ai-video-editor-trends/)

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
  caught & fixed a StrictMode initializer bug).
- 2026-06-29 — Cleaned up the two E2E test videos (e2e_sample, g3_template_test)
  + their files from the account.
- 2026-06-29 — ✅ G4 shipped + browser-E2E-verified (platform resize presets:
  6 chips → aspect + caption position, preview reshapes live).
- 2026-06-29 — ✅ G5 shipped + browser-E2E-verified (animated subtitles: word-pop
  in both renderers, "Animate words" toggle; 53 backend tests green; rendered
  frames confirm the pop).
- 2026-06-29 — ✅ G6 shipped + browser-E2E-verified (subtitle editor: per-line
  text edit retimes words, flows to captions + SRT; 56 backend tests green).
  **Tier-1 (G1–G6) complete.**
- 2026-06-29 — ✅ G10 (Tier-2) shipped + browser-E2E-verified (teleprompter in
  the recorder: script + speed + scrolling overlay/rehearsal).
- 2026-06-29 — ✅ G11 progress bar shipped + browser-E2E-verified (both
  renderers, Overlays panel; exported frames show 20%→80% fill; 58 backend green).
- 2026-06-29 — ✅ G11b text overlays shipped + browser-E2E-verified (render-once
  layer composited per frame, preview parity, add/edit/position/size/colour).
- 2026-06-29 — ✅ G11b COMPLETED: colour-emoji bake (emoji/text run-splitting +
  Apple Color Emoji) and fade-in/out transition, both browser-E2E-verified
  (baked "🔥 HOT TAKE 🔥" + fade brightness 31.5→132.3; 62 backend green).
  Remaining gaps are all heavy ML: G7 diarization / G8 eye-contact / G9 multi-cam.
- 2026-07-01 — ✅ G7 speaker diarization shipped **torch-free / download-free**
  (numpy MFCC + silhouette k-means, `POST …/diarize`, transcript speaker chips +
  Detect button). 80 backend + 18 frontend green; build clean. Real-audio E2E
  test on the seeded short. Browser E2E of the panel pending (no Chrome this
  session). Remaining heavy-ML gaps: G8 eye-contact, G9 multi-cam.
- 2026-07-01 — Market scan added (see "AI features rivals have that Clippy lacks"):
  surveyed Opus Clip, Submagic, Vizard/Klap, CapCut, Descript, Veed. Split the
  gaps into Group A (local-first & feasible — virality score, one-click Auto-Edit,
  silence removal, hook-title/social-copy, keyword-highlight & auto-emoji captions,
  auto-zoom, chapters, studio-sound) vs Group B (generative/cloud — B-roll,
  avatars, text-to-video, voice cloning/dub, thumbnails, outpaint, scheduler).
  G8/G9 on hold. Awaiting a call on where to concentrate.
- 2026-07-02/03 — Big batch shipped (110 backend + 18 frontend green): caption
  **types** (reveal) + **motion** (9 Veed animations) + **fonts** + **keyword
  emphasis** + **per-speaker colour**; **A1** score ranking, **A2** one-click
  Auto-Edit, **A4** social copy (Publish panel); **A3** silence removal; editor
  **keyboard shortcuts** + **timeline ruler/scrub**; full **UI redesign** (bright
  theme + line-icon set). Remaining "next wave" list added above (A6/A7/A8, drag
  caption position, timeline zoom, export presets, A9). All still uncommitted on main.
- 2026-07-01 — ✅ A3 silence/dead-air removal shipped (`silences.py` +
  `GET …/silences` + Toolbar "Remove silences"; ffmpeg silencedetect, padded,
  review-then-apply). 87 backend + 18 frontend green. Group A remaining: A1
  virality score, A2 one-click Auto-Edit, A4 hook/social copy, A5/A6 caption AI,
  A7 auto-zoom, A8 chapters, A9 studio-sound.
