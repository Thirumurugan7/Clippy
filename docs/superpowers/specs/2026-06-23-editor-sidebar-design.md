# ClipForge Editor Sidebar (Veed/Descript-style) — Design Spec

Date: 2026-06-23
Status: Approved (design); pending spec review
Scope: Project A (editor panels). Project B (M5 SaaS shell) is a separate spec, built after.

## Goal

Add a collapsible right sidebar to the editor hosting four panels — AI prompt
edit, Highlights, Captions, Crop — matching the feel of Veed/Descript. All of
them drive a single per-video `settings` object that the live preview and the
export both read, so what you see is what you export.

Local & free only (gemma4 via Ollama, ffmpeg, mediapipe, Pillow). No paid APIs.
Nothing auto-finalizes; the AI edit is a reviewable proposal.

## Core: one shared `settings` object

A per-video settings record, persisted like the EDL (autosaved), is the single
source of truth for framing and captions:

```json
{
  "aspect": "9:16",            // one of 9:16 | 1:1 | 4:5 | 16:9
  "framing": "auto",           // auto (face-track) | manual
  "crop_cx": 0.5,              // manual horizontal centre, 0..1 (used when manual)
  "caption": {
    "preset": "karaoke",       // one of the 5 presets
    "fontsize": 58,            // in 1080-wide units
    "color": "#ff8a3d",        // highlight colour
    "position": "bottom"        // bottom | center | top
  }
}
```

- New table `settings(video_id PK, json, updated_at)`.
- `GET /api/videos/{id}/settings` → saved settings or sensible defaults.
- `PUT /api/videos/{id}/settings` → validated + stored (autosave from panels).
- Both the preview canvas (JS) and the vertical export (Python) read it.

## Aspect-aware crop (generalises the current 9:16-only code)

Constants in `backend/presets.py` (and a JS mirror): aspect → (ratio w/h, export
W×H). Export sizes: 9:16→1080×1920, 1:1→1080×1080, 4:5→1080×1350, 16:9→1920×1080.

Crop math (shared logic, used by preview + export): given source `W×H` and target
ratio `ar = tw/th`, the crop window is the largest rectangle of ratio `ar` that
fits in the source. If source is wider than `ar`: `crop_w = H*ar`, `crop_h = H`
(varies horizontally). If taller: `crop_h = W/ar`, `crop_w = W` (varies
vertically; we still only pan horizontally for v1). Horizontal centre comes from
the face-track trajectory (`framing=auto`) or `crop_cx` (`framing=manual`),
clamped to `[0, W-crop_w]`.

## Caption presets (both renderers)

`backend/presets.py` defines 5 presets; each resolves to a style dict consumed by
**both** renderers:

| Preset | Look |
|---|---|
| `clean` | White text, thin outline, no box |
| `bold_pop` | Large bold, active word in highlight colour, heavy outline |
| `karaoke` | Current default — active word filled highlight colour |
| `hype_box` | Words on a filled rounded box; active word box in highlight colour |
| `minimal` | Smaller, lower-third, subtle outline |

A resolved style = `{font, fontsize, primary (highlight), upcoming, outline,
box (none|rgba), position, max_words}`. User tweaks (`fontsize`, `color`,
`position`) override the preset's values.

- `backend/captions.py` `CaptionRenderer` (export, Pillow) extended to take a
  style and draw the optional background box + honour position.
- `frontend/src/captionLayout.js` `drawCaptions` (preview, canvas) extended the
  same way. Same presets both places → preview == export.

## AI prompt edit

`backend/ai_edit.py`: given a free-text instruction and the transcript, gemma4
returns STRICT JSON (retry-once-stricter, raw surfaced on failure, never
fabricated):

```json
{ "clip": {"start": <s>, "end": <s>},
  "aspect": "9:16", "caption_preset": "bold_pop",
  "reason": "<one line: what it made and why>" }
```

The prompt instructs the model to: infer the platform → aspect (reel/tiktok/
shorts → 9:16, square post → 1:1 or 4:5, youtube → 16:9), infer the target
duration, and choose the best self-contained clip of about that length using the
transcript timestamps.

- Worker job `ai_edit` (one-at-a-time; gemma4 only reads text). Stored result.
- `POST /api/videos/{id}/ai_edit` body `{prompt}` → job_id. `GET …/ai_edit` →
  latest proposal (or error+raw).
- Frontend **applies the proposal as a reviewable edit**: sets the EDL to the
  clip (`ops.setAll`), PUTs the settings (aspect + caption preset), shows the
  reason. The user adjusts and exports. Nothing is finalized automatically.

## Sidebar UX

Collapsible right sidebar: a vertical icon strip selects the active panel; a
collapse control hides the panel (Veed-style). Panels:

- **AI Edit** — prompt textarea + "Apply"; shows the running state and the
  applied proposal's reason; "Apply" is reversible (EDL + settings are undoable /
  re-editable).
- **Highlights** — the existing `HighlightsRail`, moved into this tab.
- **Captions** — 5 preset cards, each showing the preset name and a small styled
  text sample rendered in that preset's look, + size/colour/position tweaks.
  Writes `settings.caption`.
- **Crop** — aspect buttons (9:16 / 1:1 / 4:5 / 16:9) + Auto/Manual toggle. In
  Manual, dragging the crop overlay on the preview sets `crop_cx`. Writes
  `settings.aspect/framing/crop_cx`.

## Preview

`PreviewPlayer` canvas becomes aspect-aware: canvas dimensions from the chosen
aspect; crop centre from settings (auto trajectory vs manual `crop_cx`); caption
style from the chosen preset. In Manual framing the canvas shows a draggable crop
guide. The non-destructive EDL playback is unchanged.

## New / changed code

- Create `backend/presets.py` (aspect + caption preset constants).
- Create `backend/ai_edit.py`; create `worker/steps/ai_edit.py`.
- Modify `backend/db.py` (settings table + get/save), `backend/app.py`
  (settings + ai_edit endpoints), `backend/captions.py` (style/box/position).
- Modify `worker/steps/vertical.py` + `worker/steps/reframe.py` to be
  aspect-aware (reframe already stores per-time centres; crop uses aspect).
- Create `frontend/src/presets.js` (mirror), `frontend/src/hooks/useSettings.js`,
  `frontend/src/components/Sidebar.jsx`, `AiEditPanel.jsx`, `CaptionsPanel.jsx`,
  `CropPanel.jsx`.
- Modify `frontend/src/captionLayout.js` (style/box/position), `PreviewPlayer.jsx`
  (aspect + manual crop drag + preset), `EditorPage.jsx` (wire settings + sidebar).

## Verification (real video, per project rules)

- vitest: aspect crop math, preset resolution, settings defaults (pure logic).
- pytest: settings get/save + validation; ai_edit parse (valid/invalid JSON →
  retry/surface); aspect-aware export produces correct dimensions.
- Playwright on the real video: type an AI prompt → EDL+settings update and
  preview reframes; switch caption preset → preview changes; change aspect +
  manual crop drag → preview reframes; export → output dimensions match the
  chosen aspect and captions match the preset.

## Out of scope (this spec)

M5 (accounts, per-user isolation, queue) — separate spec. Vertical panning only
(no vertical face follow). No animated caption transitions beyond the karaoke
fill / per-word highlight. No brand kits / logos / B-roll.
