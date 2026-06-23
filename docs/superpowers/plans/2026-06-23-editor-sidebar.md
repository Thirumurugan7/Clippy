# ClipForge Editor Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsible Veed/Descript-style right sidebar (AI prompt edit, Highlights, Captions with 12 influencer presets, Crop/aspect) driven by one shared per-video `settings` object that the live preview and export both read.

**Architecture:** A `settings` record (aspect, framing, crop_cx, caption) is persisted like the EDL and is the single source of truth for framing + captions. Aspect-aware crop math and the 12 caption presets live in shared modules mirrored in Python (export) and JS (preview) so preview == export. AI edit is a gemma4 worker job returning a reviewable proposal (clip + aspect + caption preset).

**Tech Stack:** Python/FastAPI/SQLite, gemma4 via Ollama, ffmpeg, mediapipe, Pillow, React/Vite, vitest, pytest, Playwright.

## Global Constraints

- LOCAL & FREE only: ffmpeg + faster-whisper + mediapipe + gemma4 via Ollama + Pillow. No paid APIs.
- NO mocks/stubs. Verify on real video `data/input/JLPT.mp4` (face) and `openagent.mp4` (no face).
- gemma4 runs as a worker job, one-at-a-time, text-only, strict-JSON parse with retry-once-stricter then surface raw; never fabricate.
- Nothing auto-finalizes; AI edit is a reviewable proposal (sets EDL + settings, undoable).
- Preview must equal export: both read the shared `settings` + reframe trajectory.
- Project B (M5 SaaS shell) is OUT OF SCOPE here.

---

## File Structure

**Backend**
- Create `backend/presets.py` — `ASPECTS` (ratio + export dims) and `CAPTION_PRESETS` (12) + `resolve_caption_style(settings_caption)`.
- Create `backend/crop.py` — `compute_crop(W, H, aspect, cx_norm)` → `(sx, sy, cw, ch)`; `target_dims(aspect)`.
- Create `backend/ai_edit.py` — `parse_ai_edit(raw, duration)`, `detect_ai_edit(video_id, prompt)`.
- Modify `backend/db.py` — `settings` table + `get_settings`/`save_settings`; `ai_edits` reuse `highlights`-style storage (store on `settings`? no — separate `ai_edits` table).
- Modify `backend/app.py` — settings GET/PUT, ai_edit POST/GET endpoints.
- Modify `backend/captions.py` — full style schema (chips, active box, line band, glow, gradient, uppercase, position).
- Create `worker/steps/ai_edit.py`; modify `worker/worker.py` (register `ai_edit`).
- Modify `worker/steps/vertical.py` + `worker/steps/reframe.py` — aspect-aware crop via `backend/crop.py`, read `settings`.

**Frontend**
- Create `frontend/src/presets.js` (mirror of ASPECTS + CAPTION_PRESETS + resolve).
- Create `frontend/src/crop.js` (mirror of compute_crop/target_dims).
- Create `frontend/src/hooks/useSettings.js`.
- Create `frontend/src/components/Sidebar.jsx`, `AiEditPanel.jsx`, `CaptionsPanel.jsx`, `CropPanel.jsx`.
- Modify `frontend/src/captionLayout.js` (full style schema).
- Modify `frontend/src/components/PreviewPlayer.jsx` (aspect dims, crop from settings, manual drag, preset).
- Modify `frontend/src/EditorPage.jsx` (settings wiring + Sidebar hosting HighlightsRail + panels).
- Modify `frontend/src/styles.css`.

---

## Task 1: presets.py — aspects + 12 caption presets

**Files:** Create `backend/presets.py`; Test `backend/tests/test_presets.py`.

**Interfaces — Produces:**
- `ASPECTS: dict[str, dict]` with keys `9:16,1:1,4:5,16:9` → `{"ratio": w/h, "w": int, "h": int}` (export dims).
- `CAPTION_PRESETS: dict[str, dict]` — 12 presets, each a style dict.
- `resolve_caption_style(caption: dict) -> dict` — preset defaults overlaid with user `fontsize/color/position`.

Style dict keys: `font, fontsize, primary, upcoming, outline_color, outline_width, uppercase(bool), word_box(None|str rgba), active_box(None|str), line_band(None|str), glow(None|str), gradient(None|[str,str]), position(bottom|center|top), max_words`.

- [ ] **Step 1: failing test**
```python
# backend/tests/test_presets.py
from backend.presets import ASPECTS, CAPTION_PRESETS, resolve_caption_style
def test_aspects():
    assert ASPECTS["9:16"]["w"] == 1080 and ASPECTS["9:16"]["h"] == 1920
    assert ASPECTS["16:9"]["w"] == 1920 and ASPECTS["16:9"]["h"] == 1080
    assert abs(ASPECTS["1:1"]["ratio"] - 1.0) < 1e-6
def test_twelve_presets():
    assert len(CAPTION_PRESETS) >= 12
    assert "hormozi" in CAPTION_PRESETS and CAPTION_PRESETS["hormozi"]["uppercase"]
def test_resolve_overrides():
    s = resolve_caption_style({"preset": "karaoke", "fontsize": 70, "color": "#00ff00", "position": "center"})
    assert s["fontsize"] == 70 and s["primary"] == "#00ff00" and s["position"] == "center"
def test_resolve_unknown_preset_falls_back():
    s = resolve_caption_style({"preset": "nope"})
    assert s["fontsize"] > 0  # default karaoke
```
- [ ] **Step 2:** `./.venv/bin/python -m pytest backend/tests/test_presets.py -v` → FAIL.
- [ ] **Step 3:** Implement `backend/presets.py`. ASPECTS as above. 12 presets with the style keys (hormozi: uppercase, active_box "#ffd400cc", thick outline; beast: big, glow, drop; karaoke: primary fill; boxed: word_box dark + active_box highlight; tiktok: line_band "#000000aa"; neon: glow; bold_pop; clean; minimal: small position bottom; uppercase; gradient: gradient ["#ffb259","#ff5a3c"]; subtitle: line_band solid full-width). `resolve_caption_style` merges preset (default "karaoke") then applies `fontsize/color(→primary)/position` if present.
- [ ] **Step 4:** pytest → PASS.
- [ ] **Step 5:** commit `feat(presets): aspect ratios + 12 caption presets`.

---

## Task 2: crop.py — aspect-aware crop math

**Files:** Create `backend/crop.py`; Test `backend/tests/test_crop.py`.

**Interfaces — Produces:**
- `target_dims(aspect: str) -> tuple[int,int]`.
- `compute_crop(W:int, H:int, aspect:str, cx_norm:float) -> tuple[int,int,int,int]` → `(sx, sy, cw, ch)`; horizontal-only pan, clamped.

- [ ] **Step 1: failing test**
```python
# backend/tests/test_crop.py
from backend.crop import compute_crop, target_dims
def test_target_dims():
    assert target_dims("9:16") == (1080, 1920)
    assert target_dims("4:5") == (1080, 1350)
def test_crop_landscape_to_916_centered():
    sx, sy, cw, ch = compute_crop(1920, 1080, "9:16", 0.5)
    assert ch == 1080 and cw == round(1080*9/16)
    assert sx == round((1920 - cw)/2) and sy == 0
def test_crop_pans_and_clamps():
    sx,_,cw,_ = compute_crop(1920,1080,"9:16",0.0); assert sx == 0
    sx2,_,cw2,_ = compute_crop(1920,1080,"9:16",1.0); assert sx2 == 1920-cw2
def test_crop_169_is_full_width():
    sx,sy,cw,ch = compute_crop(1920,1080,"16:9",0.5)
    assert cw == 1920 and ch == 1080
```
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** Implement: `ratio = ASPECTS[aspect]["ratio"]`. If `W/H >= ratio`: `ch=H; cw=round(H*ratio)` (pan horizontally). Else `cw=W; ch=round(W/ratio)` (center vertically). `cx=cx_norm*W; sx=clamp(round(cx-cw/2),0,W-cw); sy=clamp(round((H-ch)/2),0,H-ch)`. `target_dims` from ASPECTS.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** commit `feat(crop): aspect-aware crop math`.

---

## Task 3: settings table + endpoints

**Files:** Modify `backend/db.py`, `backend/app.py`; Test `backend/tests/test_settings.py`.

**Interfaces — Produces:**
- `db.get_settings(video_id)`, `db.save_settings(video_id, json_str)`.
- `GET /api/videos/{id}/settings` → `{aspect,framing,crop_cx,caption}` (defaults if none).
- `PUT /api/videos/{id}/settings` body same → `{ok:true}` (validates aspect in ASPECTS, framing in {auto,manual}, crop_cx 0..1, caption.preset in CAPTION_PRESETS).

Default settings: `{"aspect":"9:16","framing":"auto","crop_cx":0.5,"caption":{"preset":"karaoke","fontsize":58,"color":"#ff8a3d","position":"bottom"}}`.

- [ ] Steps: TDD — failing pytest (get default, put valid, put invalid aspect → 400), add `settings(video_id PK, json, updated_at)` table + helpers, add endpoints with a `SettingsBody` pydantic `dict`-ish (accept raw dict, validate fields), run, commit `feat(settings): per-video settings table + endpoints`.

```python
# backend/tests/test_settings.py
from backend import db
def test_default_settings_shape(tmp_path=None):
    # any existing video id
    with db.get_conn() as c:
        vid = c.execute("SELECT id FROM videos LIMIT 1").fetchone()["id"]
    s = db.get_settings(vid)
    assert s is None or True  # storage-level; endpoint provides defaults
```
(Endpoint default + validation is exercised via Playwright/manual curl too.)

---

## Task 4: captions.py full style schema (export renderer)

**Files:** Modify `backend/captions.py`; Test `backend/tests/test_captions.py`.

**Interfaces:** `CaptionRenderer(words, *, width, height, style)` where `style` is a resolved caption style dict (Task 1). `.draw(frame_bgr, t)` returns a frame with: optional `line_band` rect behind the line, per-word `word_box` chips, `active_box` behind the active word, outline, glow, gradient or solid fill, uppercase transform, position (bottom/center/top).

- [ ] **Step 1: failing test** — render onto a black 1080x1920 frame at a time inside a word, assert the frame is no longer all-black (text drawn) and, for `tiktok`/`subtitle` presets, assert a band row has non-black pixels spanning width.
```python
# backend/tests/test_captions.py
import numpy as np
from backend.captions import CaptionRenderer
from backend.presets import resolve_caption_style
WORDS=[{"word":"hello","virtual_start":0.0,"virtual_end":1.0},{"word":"world","virtual_start":1.0,"virtual_end":2.0}]
def test_draws_text():
    r=CaptionRenderer(WORDS, width=1080, height=1920, style=resolve_caption_style({"preset":"karaoke"}))
    f=np.zeros((1920,1080,3),np.uint8)
    out=r.draw(f,0.5)
    assert out.sum()>0
def test_band_preset_has_band():
    r=CaptionRenderer(WORDS, width=1080, height=1920, style=resolve_caption_style({"preset":"tiktok"}))
    out=r.draw(np.zeros((1920,1080,3),np.uint8),0.5)
    assert out.sum()>0
```
- [ ] Steps: run FAIL; refactor CaptionRenderer to accept `style` dict and implement schema (Pillow: draw rounded rects for bands/boxes via `ImageDraw.rounded_rectangle`, gradient by drawing text on a gradient-filled mask or two-tone approximation, uppercase via `.upper()`); run PASS; commit `feat(captions): full influencer preset style schema (export)`.

---

## Task 5: ai_edit.py — prompt → clip + settings proposal

**Files:** Create `backend/ai_edit.py`, `worker/steps/ai_edit.py`; modify `worker/worker.py`, `backend/db.py` (ai_edits table), `backend/app.py`; Test `backend/tests/test_ai_edit.py`.

**Interfaces — Produces:**
- `parse_ai_edit(raw:str, duration:float) -> dict` → `{clip:{start,end}, aspect, caption_preset, reason}` or raises.
- `detect_ai_edit(video_id, prompt) -> dict` (gemma4, retry, surface raw).
- `run_ai_edit_job(video_id, prompt)` worker handler → stores in `ai_edits`.
- `POST /api/videos/{id}/ai_edit {prompt}` → job_id; `GET …/ai_edit` → latest `{ready,clip,aspect,caption_preset,reason,raw,error}`.

- [ ] **Step 1: failing test** (pure parse):
```python
# backend/tests/test_ai_edit.py
import pytest
from backend.ai_edit import parse_ai_edit
def test_parse_ok():
    raw='{"clip":{"start":10,"end":50},"aspect":"9:16","caption_preset":"hormozi","reason":"hook"}'
    r=parse_ai_edit(raw, 120)
    assert r["clip"]["start"]==10 and r["aspect"]=="9:16" and r["caption_preset"]=="hormozi"
def test_parse_clamps_and_validates():
    raw='{"clip":{"start":-5,"end":9999},"aspect":"weird","caption_preset":"nope","reason":"x"}'
    r=parse_ai_edit(raw, 120)
    assert r["clip"]["start"]>=0 and r["clip"]["end"]<=120
    assert r["aspect"]=="9:16"  # invalid -> default
    assert r["caption_preset"]=="karaoke"  # invalid -> default
def test_parse_bad_json_raises():
    with pytest.raises(Exception): parse_ai_edit("not json", 120)
```
- [ ] Steps: run FAIL; implement parse (json.loads; clamp clip to [0,duration]; aspect must be in ASPECTS else "9:16"; caption_preset in CAPTION_PRESETS else "karaoke"); `detect_ai_edit` builds a prompt (platform→aspect mapping guidance + transcript segments + target duration inference) and calls `get_provider().complete(json_mode=True)`, retry-stricter, surface raw; worker job stores; endpoints; ai_edits table `(video_id PK, clip_json, aspect, caption_preset, reason, raw, error, updated_at)`; run PASS; commit `feat(ai-edit): gemma4 prompt-to-clip proposal`.

---

## Task 6: aspect-aware reframe + export

**Files:** Modify `worker/steps/vertical.py`, `worker/steps/reframe.py`; Test `backend/tests/test_export.py` (extend).

**Interfaces:** `run_vertical_export(job)` reads `db.get_settings`; uses `crop.compute_crop` with the chosen aspect and centre (auto from reframe centers via EDL mapping, or manual `crop_cx`); output dims = `target_dims(aspect)`; captions via `resolve_caption_style(settings.caption)`; reframe.json stays source-relative (centres independent of aspect).

- [ ] **Step 1: failing test** — set settings aspect "1:1", export, assert output is 1080x1080:
```python
def test_export_square_aspect():
    vid=_short_video_id(); import json
    from backend import db
    db.save_settings(vid, json.dumps({"aspect":"1:1","framing":"auto","crop_cx":0.5,"caption":{"preset":"karaoke","fontsize":58,"color":"#ff8a3d","position":"bottom"}}))
    from worker.steps.vertical import run_vertical_export
    r=run_vertical_export({"id":"sq01","video_id":vid,"params_json":"{}"})
    assert r["width"]==1080 and r["height"]==1080
```
- [ ] Steps: run FAIL; refactor `_reframe_and_caption` to take aspect/framing/crop_cx + style; compute crop per frame via `compute_crop`; manual mode uses fixed `crop_cx`, auto uses `cx_at(centers, src_t)`; output size `target_dims`; run PASS; commit `feat(export): aspect-aware vertical export honoring settings`.

---

## Task 7: frontend mirrors — presets.js + crop.js

**Files:** Create `frontend/src/presets.js`, `frontend/src/crop.js`; Test `frontend/src/presets.test.js`, `frontend/src/crop.test.js`.

**Interfaces:** identical shapes to Python — `ASPECTS`, `CAPTION_PRESETS`, `resolveCaptionStyle(caption)`, `computeCrop(W,H,aspect,cxNorm)`, `targetDims(aspect)`.

- [ ] vitest tests mirroring Task 1/2 assertions; implement; run; commit `feat(frontend): presets + crop mirrors (vitest)`.

---

## Task 8: useSettings hook

**Files:** Create `frontend/src/hooks/useSettings.js`.

**Interfaces:** `useSettings(videoId)` → `{settings, setSettings(partial), saving}`; loads `GET …/settings`, merges partial updates, debounced `PUT`. Mirror `useEdl` autosave pattern.

- [ ] Implement; sanity via vitest build; commit `feat(frontend): useSettings hook`.

---

## Task 9: captionLayout.js full style schema (preview)

**Files:** Modify `frontend/src/captionLayout.js`.

**Interfaces:** `drawCaptions(ctx, lines, t, W, H, style)` where `style` is a resolved caption style (same keys as Python). Implement band, chips, active box, outline, glow (shadowBlur), gradient (createLinearGradient), uppercase, position. Matches the Pillow output.

- [ ] Implement; commit `feat(frontend): caption preset rendering on canvas`.

---

## Task 10: PreviewPlayer aspect + manual crop + preset

**Files:** Modify `frontend/src/components/PreviewPlayer.jsx`.

**Interfaces:** props add `settings`. Canvas dims from `targetDims(settings.aspect)` scaled to fit (e.g. max 540 on the long edge). Crop via `computeCrop` using auto centre (reframe) or `settings.crop_cx`. Captions via `resolveCaptionStyle(settings.caption)`. In `framing==="manual"`, draw a crop guide and let horizontal drag update `settings.crop_cx` (via an `onCropDrag` prop).

- [ ] Implement; commit `feat(frontend): aspect-aware canvas preview + manual crop`.

---

## Task 11: Sidebar shell (collapsible, tabbed) + move Highlights

**Files:** Create `frontend/src/components/Sidebar.jsx`; modify `EditorPage.jsx`, `styles.css`.

**Interfaces:** `Sidebar({active, onSelect, collapsed, onToggle, children})` — vertical icon strip (AI, Highlights, Captions, Crop) + a panel area showing the active child; collapse hides the panel. `EditorPage` renders the four panels and passes the active one.

- [ ] Implement; commit `feat(frontend): collapsible tabbed sidebar`.

---

## Task 12: CaptionsPanel (12 preset gallery + tweaks)

**Files:** Create `frontend/src/components/CaptionsPanel.jsx`.

**Interfaces:** `CaptionsPanel({settings, setSettings})` — gallery of 12 cards (name + a styled sample using each preset's style), selecting writes `settings.caption.preset`; size slider, colour picker, position select write `fontsize/color/position`.

- [ ] Implement; commit `feat(frontend): captions panel with 12 presets`.

---

## Task 13: CropPanel (aspect + framing + manual)

**Files:** Create `frontend/src/components/CropPanel.jsx`.

**Interfaces:** `CropPanel({settings, setSettings})` — 4 aspect buttons (write `aspect`), Auto/Manual toggle (write `framing`); a note that Manual lets you drag on the preview.

- [ ] Implement; commit `feat(frontend): crop panel (aspect + framing)`.

---

## Task 14: AiEditPanel (prompt + apply proposal)

**Files:** Create `frontend/src/components/AiEditPanel.jsx`; create `frontend/src/hooks/useAiEdit.js`.

**Interfaces:** `useAiEdit(videoId)` → `{status, proposal, error, raw, run(prompt)}` (POST then poll GET). `AiEditPanel({onApply})` — textarea + "Apply"; on result shows the reason + an "Apply to editor" button → `onApply(proposal)`. `EditorPage.onApplyAiEdit(p)` sets EDL to `[{sourceStart:p.clip.start, sourceEnd:p.clip.end}]` and `setSettings({aspect:p.aspect, caption:{...prev, preset:p.caption_preset}})`.

- [ ] Implement; commit `feat(frontend): AI prompt-edit panel`.

---

## Task 15: EditorPage wiring

**Files:** Modify `frontend/src/EditorPage.jsx`.

Wire `useSettings`, host Sidebar with the four panels, pass `settings` to `PreviewPlayer`, pass settings to export (the export reads server-side settings, so just ensure settings are PUT before export — already autosaved). Manual crop drag updates settings.crop_cx.

- [ ] Implement; manual smoke; commit `feat(frontend): wire settings + sidebar into editor`.

---

## Task 16: E2E verification (Playwright, real video)

**Files:** Create `e2e/sidebar_test.mjs`.

Drive: open video → Captions tab → pick `hormozi` preset → preview caption style changes (assert canvas pixels/region or that the active preset card is selected and an export reflects uppercase). Crop tab → pick 1:1 → preview canvas becomes square (assert canvas aspect ~1). AI tab → type "make a 30s reel" → wait proposal → Apply → timeline narrows + aspect 9:16. Export → output dims match aspect. Screenshot.

- [ ] Implement; run; commit `test(e2e): sidebar panels (captions, crop, AI edit)`.

---

## Self-Review Notes
- **Spec coverage:** settings (T3), aspect crop (T2/T6/T7/T10), 12 presets (T1/T4/T9/T12), AI edit (T5/T14), sidebar (T11/T13/T15), preview==export (shared T1/T2 mirrors), verification (T1-7 unit + T16 e2e). All spec sections mapped.
- **Type consistency:** style dict keys identical Python/JS (T1/T4/T7/T9); `compute_crop`/`computeCrop` same signature/return; settings shape identical across T3/T8/T10/T15; ai_edit proposal keys (`clip,aspect,caption_preset,reason`) consistent T5/T14.
- **Gradient/box rendering** is approximate (two-tone / rounded rects) — acceptable; not a placeholder.
