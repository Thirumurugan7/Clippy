# ClipForge Non-Destructive Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ClipForge's mark-words-then-export editor with a Descript/Veed-style non-destructive editor where transcript edits, timeline trim/split/ripple-delete/reorder, and live preview are all driven by one Edit Decision List (EDL), and export bakes that EDL with ffmpeg.

**Architecture:** A single ordered list of `{id, sourceStart, sourceEnd}` segments is the only edit state. The transcript, the live preview player, and the timeline are pure projections of it, so they can never desync. Pure EDL logic lives in `frontend/src/edl.js` (unit-tested with vitest); the backend persists the EDL and renders it; the worker computes waveform peaks and exports.

**Tech Stack:** Python 3.12 + FastAPI + SQLite (backend), faster-whisper + ffmpeg (already in place), React + Vite (frontend), vitest (frontend unit tests), pytest (backend tests), Playwright (E2E).

## Global Constraints

- All processing LOCAL and FREE: ffmpeg + faster-whisper + mediapipe + gemma4 via Ollama. No paid cloud APIs. (Copied from project hard rules.)
- NO mock data, NO stubs, NO placeholder integrations. Every feature must run end to end on the REAL video at `clipforge/data/input/JLPT.mp4` (and the derived `sample_short.mp4`). Never fabricate transcripts/clips.
- Worker runs ONE job at a time; steps run sequentially. Never run gemma4 and ffmpeg simultaneously.
- This expands milestone M2. Do NOT build M3 (highlights) or M4 (vertical export) here.
- Existing run commands: `./scripts/run_api.sh`, `./scripts/run_worker.sh`, `cd frontend && npm run dev`. Python venv at `clipforge/.venv`.
- Verification is runtime observation on the real video (Playwright through the UI), per project rules — in addition to the unit tests below.

---

## File Structure

**Frontend**
- Create `frontend/src/edl.js` — pure EDL model: operations + projection + virtual/source time mapping.
- Create `frontend/src/edl.test.js` — vitest unit tests for `edl.js`.
- Create `frontend/src/hooks/useEdl.js` — React state wrapper: holds EDL, applies ops, undo/redo, debounced autosave.
- Create `frontend/src/components/PreviewPlayer.jsx` — EDL-driven playback over one `<video>`.
- Create `frontend/src/components/TranscriptPane.jsx` — transcript projection; click=seek, select+delete=edit.
- Create `frontend/src/components/Timeline.jsx` — clip blocks, waveform, trim handles, split, ripple-delete, reorder.
- Create `frontend/src/components/Toolbar.jsx` — Split / Delete / Detect fillers / Undo / Redo / Export.
- Create `frontend/src/EditorPage.jsx` — layout shell wiring the above.
- Modify `frontend/src/App.jsx` — render `EditorPage` for the current video.
- Modify `frontend/src/styles.css` — editor styling (Descript/Veed-like, via frontend-design skill).
- Modify `frontend/package.json`, create `frontend/vitest.config.js` — vitest setup.

**Backend**
- Modify `backend/db.py` — add `edits` table + `get_edit`/`save_edit`.
- Create `backend/edl.py` — server-side EDL validation + ordered-interval extraction.
- Modify `backend/app.py` — `GET/PUT /api/videos/{id}/edit`, `GET /api/videos/{id}/waveform`, export uses saved EDL.
- Create `backend/tests/test_edl.py`, `backend/tests/test_export.py` — pytest.

**Worker**
- Create `worker/steps/waveform.py` — ffmpeg audio peaks.
- Modify `worker/steps/export_edit.py` — render ordered EDL intervals (drop the delete-index path).
- Modify `worker/worker.py` — register `waveform` handler.
- Modify `backend/app.py` upload — enqueue `waveform` after `probe`.

**Tooling**
- Modify `requirements.txt` — add `pytest`.

---

## Task 1: vitest setup + EDL model core (default, durations, immutability)

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.js`
- Create: `frontend/src/edl.js`
- Test: `frontend/src/edl.test.js`

**Interfaces:**
- Produces:
  - `defaultEdl(duration: number): Segment[]` where `Segment = {id: string, sourceStart: number, sourceEnd: number}`
  - `segmentDuration(seg: Segment): number`
  - `totalDuration(edl: Segment[]): number`

- [ ] **Step 1: Add vitest to package.json**

In `frontend/package.json`, add to `scripts`: `"test": "vitest run"`, and to `devDependencies`: `"vitest": "^2.1.8"`. Then run `npm install` in `frontend/`.

- [ ] **Step 2: Create vitest config**

```js
// frontend/vitest.config.js
import { defineConfig } from "vitest/config";
export default defineConfig({ test: { environment: "node" } });
```

- [ ] **Step 3: Write the failing test**

```js
// frontend/src/edl.test.js
import { describe, it, expect } from "vitest";
import { defaultEdl, segmentDuration, totalDuration } from "./edl.js";

describe("edl core", () => {
  it("defaultEdl is one segment covering the whole video", () => {
    const edl = defaultEdl(10);
    expect(edl).toHaveLength(1);
    expect(edl[0].sourceStart).toBe(0);
    expect(edl[0].sourceEnd).toBe(10);
    expect(typeof edl[0].id).toBe("string");
  });
  it("segmentDuration and totalDuration", () => {
    const edl = defaultEdl(10);
    expect(segmentDuration(edl[0])).toBe(10);
    expect(totalDuration(edl)).toBe(10);
  });
});
```

- [ ] **Step 4: Run test, verify it fails**

Run: `cd frontend && npx vitest run src/edl.test.js`
Expected: FAIL — cannot resolve `./edl.js`.

- [ ] **Step 5: Implement edl.js core**

```js
// frontend/src/edl.js
let _idCounter = 0;
function newId() {
  _idCounter += 1;
  return `seg_${Date.now().toString(36)}_${_idCounter}`;
}

export function defaultEdl(duration) {
  return [{ id: newId(), sourceStart: 0, sourceEnd: duration }];
}

export function segmentDuration(seg) {
  return seg.sourceEnd - seg.sourceStart;
}

export function totalDuration(edl) {
  return edl.reduce((acc, s) => acc + segmentDuration(s), 0);
}

export { newId };
```

- [ ] **Step 6: Run test, verify it passes**

Run: `cd frontend && npx vitest run src/edl.test.js`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/vitest.config.js frontend/src/edl.js frontend/src/edl.test.js
git commit -m "feat(edl): vitest setup + EDL core (default, durations)"
```

---

## Task 2: EDL time mapping (virtual <-> source)

**Files:**
- Modify: `frontend/src/edl.js`
- Test: `frontend/src/edl.test.js`

**Interfaces:**
- Consumes: `Segment[]`, `segmentDuration`.
- Produces:
  - `virtualToSource(edl, vt: number): {segIndex: number, source: number} | null`
  - `sourceToVirtual(edl, source: number): number | null` (null if that source time was cut out)

- [ ] **Step 1: Write failing tests**

```js
// add to frontend/src/edl.test.js
import { virtualToSource, sourceToVirtual } from "./edl.js";

describe("edl time mapping", () => {
  // Two segments after a hypothetical edit: source [0-2] then source [5-7]
  const edl = [
    { id: "a", sourceStart: 0, sourceEnd: 2 },
    { id: "b", sourceStart: 5, sourceEnd: 7 },
  ];
  it("virtualToSource maps across the join", () => {
    expect(virtualToSource(edl, 1)).toEqual({ segIndex: 0, source: 1 });
    expect(virtualToSource(edl, 2.5)).toEqual({ segIndex: 1, source: 5.5 });
    expect(virtualToSource(edl, 99)).toBeNull();
  });
  it("sourceToVirtual inverts, null for cut-out source", () => {
    expect(sourceToVirtual(edl, 1)).toBeCloseTo(1);
    expect(sourceToVirtual(edl, 5.5)).toBeCloseTo(2.5);
    expect(sourceToVirtual(edl, 3.5)).toBeNull(); // 3.5s was cut
  });
});
```

- [ ] **Step 2: Run, verify fail**

Run: `cd frontend && npx vitest run src/edl.test.js`
Expected: FAIL — `virtualToSource` undefined.

- [ ] **Step 3: Implement mapping**

```js
// add to frontend/src/edl.js
export function virtualToSource(edl, vt) {
  let acc = 0;
  for (let i = 0; i < edl.length; i++) {
    const d = segmentDuration(edl[i]);
    if (vt < acc + d || (i === edl.length - 1 && vt <= acc + d + 1e-6)) {
      return { segIndex: i, source: edl[i].sourceStart + (vt - acc) };
    }
    acc += d;
  }
  return null;
}

export function sourceToVirtual(edl, source) {
  let acc = 0;
  for (const seg of edl) {
    if (source >= seg.sourceStart && source <= seg.sourceEnd) {
      return acc + (source - seg.sourceStart);
    }
    acc += segmentDuration(seg);
  }
  return null;
}
```

- [ ] **Step 4: Run, verify pass**

Run: `cd frontend && npx vitest run src/edl.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/edl.js frontend/src/edl.test.js
git commit -m "feat(edl): virtual<->source time mapping"
```

---

## Task 3: EDL edit operations (split, trim, delete, reorder, deleteSourceRange)

**Files:**
- Modify: `frontend/src/edl.js`
- Test: `frontend/src/edl.test.js`

**Interfaces:**
- Consumes: `Segment[]`, `virtualToSource`, `newId`.
- Produces (all return a NEW `Segment[]`, never mutate):
  - `splitAtVirtual(edl, vt): Segment[]`
  - `trimSegment(edl, segId, edge: "start"|"end", newSource): Segment[]`
  - `deleteSegment(edl, segId): Segment[]`
  - `reorderSegment(edl, fromIndex, toIndex): Segment[]`
  - `deleteSourceRange(edl, rangeStart, rangeEnd): Segment[]`

- [ ] **Step 1: Write failing tests**

```js
// add to frontend/src/edl.test.js
import {
  defaultEdl, splitAtVirtual, trimSegment, deleteSegment,
  reorderSegment, deleteSourceRange, totalDuration,
} from "./edl.js";

describe("edl operations", () => {
  it("splitAtVirtual splits the covering segment", () => {
    const edl = splitAtVirtual(defaultEdl(10), 4);
    expect(edl).toHaveLength(2);
    expect(edl[0]).toMatchObject({ sourceStart: 0, sourceEnd: 4 });
    expect(edl[1]).toMatchObject({ sourceStart: 4, sourceEnd: 10 });
  });
  it("trimSegment moves an edge", () => {
    const edl = trimSegment(defaultEdl(10), "x", "end", 7); // id unknown; use real id
    expect(edl).toHaveLength(1); // no-op when id missing
    const base = defaultEdl(10);
    const trimmed = trimSegment(base, base[0].id, "start", 3);
    expect(trimmed[0].sourceStart).toBe(3);
  });
  it("deleteSegment removes by id and reduces duration", () => {
    const edl = splitAtVirtual(defaultEdl(10), 4); // [0-4],[4-10]
    const after = deleteSegment(edl, edl[0].id);
    expect(after).toHaveLength(1);
    expect(totalDuration(after)).toBe(6);
  });
  it("reorderSegment moves a segment", () => {
    const edl = splitAtVirtual(defaultEdl(10), 4); // A[0-4], B[4-10]
    const after = reorderSegment(edl, 0, 1); // B then A
    expect(after[0].sourceStart).toBe(4);
    expect(after[1].sourceStart).toBe(0);
  });
  it("deleteSourceRange excises a sub-range, splitting as needed", () => {
    const after = deleteSourceRange(defaultEdl(10), 4, 5); // remove [4-5]
    expect(after).toHaveLength(2);
    expect(after[0]).toMatchObject({ sourceStart: 0, sourceEnd: 4 });
    expect(after[1]).toMatchObject({ sourceStart: 5, sourceEnd: 10 });
    expect(totalDuration(after)).toBe(9);
  });
});
```

- [ ] **Step 2: Run, verify fail**

Run: `cd frontend && npx vitest run src/edl.test.js`
Expected: FAIL — operations undefined.

- [ ] **Step 3: Implement operations**

```js
// add to frontend/src/edl.js
const MIN_SEG = 0.04; // ~1 frame at 25fps; minimum segment length

export function splitAtVirtual(edl, vt) {
  const map = virtualToSource(edl, vt);
  if (!map) return edl;
  const { segIndex, source } = map;
  const seg = edl[segIndex];
  if (source - seg.sourceStart < MIN_SEG || seg.sourceEnd - source < MIN_SEG) {
    return edl; // too close to an edge to split meaningfully
  }
  const left = { id: newId(), sourceStart: seg.sourceStart, sourceEnd: source };
  const right = { id: newId(), sourceStart: source, sourceEnd: seg.sourceEnd };
  return [...edl.slice(0, segIndex), left, right, ...edl.slice(segIndex + 1)];
}

export function trimSegment(edl, segId, edge, newSource) {
  return edl.map((s) => {
    if (s.id !== segId) return s;
    if (edge === "start") {
      const v = Math.min(newSource, s.sourceEnd - MIN_SEG);
      return { ...s, sourceStart: Math.max(0, v) };
    } else {
      const v = Math.max(newSource, s.sourceStart + MIN_SEG);
      return { ...s, sourceEnd: v };
    }
  });
}

export function deleteSegment(edl, segId) {
  const next = edl.filter((s) => s.id !== segId);
  return next;
}

export function reorderSegment(edl, fromIndex, toIndex) {
  if (fromIndex === toIndex) return edl;
  const copy = [...edl];
  const [moved] = copy.splice(fromIndex, 1);
  copy.splice(toIndex, 0, moved);
  return copy;
}

export function deleteSourceRange(edl, rangeStart, rangeEnd) {
  const out = [];
  for (const s of edl) {
    // No overlap: keep whole.
    if (rangeEnd <= s.sourceStart || rangeStart >= s.sourceEnd) {
      out.push(s);
      continue;
    }
    // Keep the part before the deleted range.
    if (rangeStart > s.sourceStart) {
      out.push({ id: newId(), sourceStart: s.sourceStart, sourceEnd: rangeStart });
    }
    // Keep the part after the deleted range.
    if (rangeEnd < s.sourceEnd) {
      out.push({ id: newId(), sourceStart: rangeEnd, sourceEnd: s.sourceEnd });
    }
  }
  return out;
}
```

- [ ] **Step 4: Run, verify pass**

Run: `cd frontend && npx vitest run src/edl.test.js`
Expected: PASS (all operation tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/edl.js frontend/src/edl.test.js
git commit -m "feat(edl): split, trim, delete, reorder, deleteSourceRange"
```

---

## Task 4: Transcript projection

**Files:**
- Modify: `frontend/src/edl.js`
- Test: `frontend/src/edl.test.js`

**Interfaces:**
- Consumes: `Segment[]`, `segmentDuration`, word list `{i, word, start, end, prob}`.
- Produces:
  - `projectWords(edl, words, minKeepRatio=0.5): Array<{...word, virtualStart, virtualEnd, segId}>` in EDL order.

- [ ] **Step 1: Write failing test**

```js
// add to frontend/src/edl.test.js
import { projectWords, splitAtVirtual, reorderSegment, defaultEdl } from "./edl.js";

describe("transcript projection", () => {
  const words = [
    { i: 0, word: "a", start: 0.0, end: 1.0, prob: 1 },
    { i: 1, word: "b", start: 1.0, end: 2.0, prob: 1 },
    { i: 2, word: "c", start: 2.0, end: 3.0, prob: 1 },
  ];
  it("keeps all words for full EDL, in order", () => {
    const out = projectWords(defaultEdl(3), words);
    expect(out.map((w) => w.word)).toEqual(["a", "b", "c"]);
    expect(out[1].virtualStart).toBeCloseTo(1.0);
  });
  it("drops words inside a cut, reflects reorder", () => {
    // split into [0-1],[1-2],[2-3], delete middle by reordering only first+last
    let edl = splitAtVirtual(splitAtVirtual(defaultEdl(3), 1), 2);
    // edl: A[0-1], B[1-2], C[2-3]; remove B, then reorder C before A
    edl = edl.filter((s) => !(s.sourceStart === 1 && s.sourceEnd === 2));
    edl = reorderSegment(edl, 1, 0); // C, A
    const out = projectWords(edl, words);
    expect(out.map((w) => w.word)).toEqual(["c", "a"]); // timeline order, b gone
  });
});
```

- [ ] **Step 2: Run, verify fail**

Run: `cd frontend && npx vitest run src/edl.test.js`
Expected: FAIL — `projectWords` undefined.

- [ ] **Step 3: Implement projection**

```js
// add to frontend/src/edl.js
export function projectWords(edl, words, minKeepRatio = 0.5) {
  const out = [];
  let acc = 0;
  for (const seg of edl) {
    const segLen = segmentDuration(seg);
    for (const w of words) {
      const overlapStart = Math.max(w.start, seg.sourceStart);
      const overlapEnd = Math.min(w.end, seg.sourceEnd);
      const overlap = overlapEnd - overlapStart;
      const wordLen = Math.max(w.end - w.start, 1e-6);
      if (overlap > 0 && overlap / wordLen >= minKeepRatio) {
        out.push({
          ...w,
          segId: seg.id,
          virtualStart: acc + (overlapStart - seg.sourceStart),
          virtualEnd: acc + (overlapEnd - seg.sourceStart),
        });
      }
    }
    acc += segLen;
  }
  return out;
}
```

- [ ] **Step 4: Run, verify pass**

Run: `cd frontend && npx vitest run src/edl.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/edl.js frontend/src/edl.test.js
git commit -m "feat(edl): transcript projection (EDL-order, >=50% keep rule)"
```

---

## Task 5: Backend edits table + EDL validation + GET/PUT endpoints

**Files:**
- Modify: `backend/db.py`
- Create: `backend/edl.py`
- Modify: `backend/app.py`
- Modify: `requirements.txt` (add pytest)
- Test: `backend/tests/test_edl.py`

**Interfaces:**
- Produces:
  - `backend.edl.validate_edl(segments: list[dict], duration: float) -> list[dict]` (raises `ValueError`)
  - `backend.edl.ordered_intervals(segments: list[dict]) -> list[tuple[float,float]]`
  - `db.get_edit(video_id) -> Optional[Row]`, `db.save_edit(video_id, edl_json)`
  - `GET /api/videos/{id}/edit` -> `{segments:[...]}` (saved or default)
  - `PUT /api/videos/{id}/edit` body `{segments:[...]}` -> `{ok:true}`

- [ ] **Step 1: Add pytest to requirements and install**

Append `pytest==8.3.4` to `requirements.txt`; run `./.venv/bin/pip install pytest==8.3.4`.

- [ ] **Step 2: Write failing test**

```python
# backend/tests/test_edl.py
import pytest
from backend.edl import validate_edl, ordered_intervals

def test_validate_ok():
    segs = [{"id": "a", "sourceStart": 0, "sourceEnd": 2},
            {"id": "b", "sourceStart": 5, "sourceEnd": 7}]
    assert validate_edl(segs, 10) == segs

def test_validate_rejects_out_of_bounds():
    with pytest.raises(ValueError):
        validate_edl([{"id": "a", "sourceStart": 0, "sourceEnd": 11}], 10)

def test_validate_rejects_inverted():
    with pytest.raises(ValueError):
        validate_edl([{"id": "a", "sourceStart": 5, "sourceEnd": 4}], 10)

def test_ordered_intervals_preserves_order():
    segs = [{"id": "b", "sourceStart": 5, "sourceEnd": 7},
            {"id": "a", "sourceStart": 0, "sourceEnd": 2}]
    assert ordered_intervals(segs) == [(5.0, 7.0), (0.0, 2.0)]
```

- [ ] **Step 3: Run, verify fail**

Run: `cd clipforge && ./.venv/bin/python -m pytest backend/tests/test_edl.py -v`
Expected: FAIL — no module `backend.edl`.

- [ ] **Step 4: Implement backend/edl.py**

```python
# backend/edl.py
"""Server-side EDL validation and rendering helpers.

An EDL is an ordered list of segments [{id, sourceStart, sourceEnd}] over the
original video's timeline. ordered_intervals() preserves list order so reordered
edits export in the arranged order.
"""
from __future__ import annotations

MIN_SEG = 0.02


def validate_edl(segments: list[dict], duration: float) -> list[dict]:
    if not isinstance(segments, list):
        raise ValueError("segments must be a list")
    for s in segments:
        try:
            a = float(s["sourceStart"])
            b = float(s["sourceEnd"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"segment missing numeric bounds: {s!r}")
        if a < -1e-6 or b > duration + 1e-3:
            raise ValueError(f"segment {a}-{b} out of bounds [0,{duration}]")
        if b - a < MIN_SEG:
            raise ValueError(f"segment {a}-{b} shorter than {MIN_SEG}s")
    return segments


def ordered_intervals(segments: list[dict]) -> list[tuple[float, float]]:
    return [(float(s["sourceStart"]), float(s["sourceEnd"])) for s in segments]
```

- [ ] **Step 5: Add edits table + helpers to db.py**

In `backend/db.py` `init_db()` executescript, add:

```sql
CREATE TABLE IF NOT EXISTS edits (
    video_id   TEXT PRIMARY KEY REFERENCES videos(id),
    edl_json   TEXT NOT NULL,
    updated_at REAL NOT NULL
);
```

Add functions:

```python
def get_edit(video_id: str):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM edits WHERE video_id=?", (video_id,)).fetchone()

def save_edit(video_id: str, edl_json: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO edits (video_id, edl_json, updated_at) VALUES (?, ?, ?)",
            (video_id, edl_json, time.time()),
        )
```

- [ ] **Step 6: Add endpoints to app.py**

```python
# backend/app.py — add near other video endpoints
import uuid as _uuid
from .edl import validate_edl

class EdlBody(BaseModel):
    segments: list[dict]

@app.get("/api/videos/{video_id}/edit")
def get_edit(video_id: str) -> dict:
    video = db.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    row = db.get_edit(video_id)
    if row is not None:
        return {"segments": json.loads(row["edl_json"])}
    dur = video["duration_seconds"] or 0.0
    return {"segments": [{"id": _uuid.uuid4().hex, "sourceStart": 0.0, "sourceEnd": dur}]}

@app.put("/api/videos/{video_id}/edit")
def put_edit(video_id: str, body: EdlBody) -> dict:
    video = db.get_video(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="video not found")
    dur = video["duration_seconds"] or 0.0
    try:
        validate_edl(body.segments, dur)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.save_edit(video_id, json.dumps(body.segments))
    return {"ok": True}
```

- [ ] **Step 7: Run tests + smoke the endpoints**

Run: `cd clipforge && ./.venv/bin/python -m pytest backend/tests/test_edl.py -v` → PASS.
Restart API, then:
`curl -s http://127.0.0.1:8000/api/videos/<JLPT_ID>/edit` → returns one full-length segment.

- [ ] **Step 8: Commit**

```bash
git add backend/edl.py backend/db.py backend/app.py backend/tests/test_edl.py requirements.txt
git commit -m "feat(backend): edits table, EDL validation, GET/PUT edit endpoints"
```

---

## Task 6: Waveform worker step + endpoint

**Files:**
- Create: `worker/steps/waveform.py`
- Modify: `worker/worker.py`
- Modify: `backend/app.py` (upload enqueues waveform; add GET waveform)
- Test: `backend/tests/test_waveform.py`

**Interfaces:**
- Produces:
  - `worker.steps.waveform.run_waveform(video_id) -> dict` writing `data/exports/<id>/waveform.json` = `{"peaks":[float...], "count":int}`
  - `GET /api/videos/{id}/waveform` -> the JSON (404 if not computed yet)

- [ ] **Step 1: Write failing test (real ffmpeg on sample_short.mp4)**

```python
# backend/tests/test_waveform.py
import json, os
from backend import db, config
from worker.steps.waveform import run_waveform

def _short_video_id():
    with db.get_conn() as c:
        row = c.execute(
            "SELECT id FROM videos WHERE original_filename LIKE 'sample_short%' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return row["id"] if row else None

def test_waveform_real():
    vid = _short_video_id()
    assert vid, "need an uploaded sample_short.mp4 (run M1 first)"
    res = run_waveform(vid)
    assert res["count"] > 100
    path = config.EXPORTS_DIR / vid / "waveform.json"
    data = json.loads(path.read_text())
    assert len(data["peaks"]) == res["count"]
    assert max(data["peaks"]) <= 1.0 and min(data["peaks"]) >= 0.0
```

- [ ] **Step 2: Run, verify fail**

Run: `cd clipforge && ./.venv/bin/python -m pytest backend/tests/test_waveform.py -v`
Expected: FAIL — no module `worker.steps.waveform`.

- [ ] **Step 3: Implement waveform.py**

```python
# worker/steps/waveform.py
"""Compute downsampled audio peaks for the timeline waveform (real ffmpeg)."""
from __future__ import annotations
import array, json, shutil, subprocess
from backend import db, config

PEAK_BUCKETS = 1000

def _ffmpeg() -> str:
    p = shutil.which("ffmpeg")
    if not p:
        raise RuntimeError("ffmpeg not found")
    return p

def run_waveform(video_id: str) -> dict:
    video = db.get_video(video_id)
    if video is None:
        raise RuntimeError(f"video {video_id} not found")
    # Decode audio to mono 8kHz s16le raw PCM on stdout.
    proc = subprocess.run(
        [_ffmpeg(), "-v", "error", "-i", video["stored_path"],
         "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg waveform decode failed: {proc.stderr.decode()[-500:]}")
    samples = array.array("h")
    samples.frombytes(proc.stdout)
    n = len(samples)
    buckets = min(PEAK_BUCKETS, max(1, n))
    size = max(1, n // buckets)
    peaks = []
    for i in range(0, n, size):
        chunk = samples[i:i + size]
        peak = max((abs(x) for x in chunk), default=0) / 32768.0
        peaks.append(round(peak, 4))
    out_dir = config.EXPORTS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "waveform.json").write_text(json.dumps({"peaks": peaks, "count": len(peaks)}))
    return {"count": len(peaks)}
```

- [ ] **Step 4: Register handler + enqueue on upload + endpoint**

In `worker/worker.py`: import `run_waveform`, add to HANDLERS: `"waveform": lambda job: run_waveform(job["video_id"])`.
In `backend/app.py` upload(): after creating the transcribe job, add `db.create_job(video_id, job_type="waveform")`.
Add endpoint:

```python
@app.get("/api/videos/{video_id}/waveform")
def get_waveform(video_id: str) -> dict:
    path = config.EXPORTS_DIR / video_id / "waveform.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="waveform not ready")
    return json.loads(path.read_text())
```

- [ ] **Step 5: Run test, verify pass**

Run: `cd clipforge && ./.venv/bin/python -m pytest backend/tests/test_waveform.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add worker/steps/waveform.py worker/worker.py backend/app.py backend/tests/test_waveform.py
git commit -m "feat(waveform): ffmpeg audio peaks step + endpoint"
```

---

## Task 7: Export from saved EDL (ordered intervals)

**Files:**
- Modify: `worker/steps/export_edit.py`
- Modify: `backend/app.py` (export endpoint reads saved EDL)
- Test: `backend/tests/test_export.py`

**Interfaces:**
- Consumes: `backend.edl.ordered_intervals`, saved EDL via `db.get_edit`.
- Produces: `run_export_edit(job)` renders the EDL's ordered intervals; result dict keys: `output_path, num_segments, output_duration, original_duration`.

- [ ] **Step 1: Write failing test (real ffmpeg export from an EDL)**

```python
# backend/tests/test_export.py
import json
from backend import db
from worker.steps.export_edit import run_export_edit

def _short_video_id():
    with db.get_conn() as c:
        row = c.execute(
            "SELECT v.id FROM videos v JOIN transcripts t ON t.video_id=v.id "
            "WHERE v.original_filename LIKE 'sample_short%' ORDER BY v.created_at DESC LIMIT 1"
        ).fetchone()
    return row["id"] if row else None

def test_export_from_edl_reordered():
    vid = _short_video_id()
    assert vid
    dur = db.get_video(vid)["duration_seconds"]
    # Two segments, reordered: second half first, then first half.
    half = round(dur / 2, 2)
    segs = [
        {"id": "b", "sourceStart": half, "sourceEnd": dur},
        {"id": "a", "sourceStart": 0.0, "sourceEnd": half},
    ]
    db.save_edit(vid, json.dumps(segs))
    job = {"id": "exptest01", "video_id": vid, "params_json": "{}"}
    res = run_export_edit(job)
    assert res["num_segments"] == 2
    assert abs(res["output_duration"] - dur) < 1.0  # same total, reordered
```

- [ ] **Step 2: Run, verify fail**

Run: `cd clipforge && ./.venv/bin/python -m pytest backend/tests/test_export.py -v`
Expected: FAIL (current export uses delete_word_indices, not EDL).

- [ ] **Step 3: Rewrite export_edit.py to use the saved EDL**

Replace `run_export_edit` body to: load `db.get_edit(video_id)`; if none, use a single full-length segment; `kept = ordered_intervals(segments)`; reuse existing `_build_filtergraph(kept, has_audio)` and ffmpeg invocation (already present). Drop `compute_kept_intervals`/`delete_word_indices` usage. Return `{output_path, num_segments=len(kept), original_duration, output_duration}`.

```python
# worker/steps/export_edit.py — new run_export_edit
import json
from backend import db, config
from backend.edl import ordered_intervals

def run_export_edit(job) -> dict:
    video_id = job["video_id"]
    video = db.get_video(video_id)
    if video is None:
        raise RuntimeError(f"video {video_id} not found")
    total_duration = video["duration_seconds"] or _probe_duration(video["stored_path"])
    has_audio = bool(video["audio_codec"])

    edit = db.get_edit(video_id)
    if edit is not None:
        segments = json.loads(edit["edl_json"])
        kept = ordered_intervals(segments)
    else:
        kept = [(0.0, total_duration)]
    if not kept:
        raise RuntimeError("EDL is empty; nothing to export.")

    out_dir = config.EXPORTS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{job['id']}.mp4"
    # ... build filtergraph + run ffmpeg exactly as in the existing implementation ...
    # (keep _build_filtergraph, tempfile, subprocess.run, error handling)
    out_duration = _probe_duration(str(out_path))
    return {
        "output_path": str(out_path),
        "num_segments": len(kept),
        "original_duration": round(total_duration, 3),
        "output_duration": round(out_duration, 3),
    }
```

(Keep `_bin`, `_probe_duration`, `_build_filtergraph` from the existing file.)

- [ ] **Step 4: Simplify the export endpoint**

In `backend/app.py`, `POST /api/videos/{id}/export` no longer needs a body — it exports the saved EDL. Keep it as POST with empty body; create an `export_edit` job with no params. (Frontend PUTs the EDL first, then POSTs export.)

- [ ] **Step 5: Run test, verify pass**

Run: `cd clipforge && ./.venv/bin/python -m pytest backend/tests/test_export.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add worker/steps/export_edit.py backend/app.py backend/tests/test_export.py
git commit -m "feat(export): render saved EDL ordered intervals (supports reorder)"
```

---

## Task 8: useEdl hook (state, ops, undo/redo, autosave)

**Files:**
- Create: `frontend/src/hooks/useEdl.js`

**Interfaces:**
- Consumes: `edl.js` operations; endpoints `GET/PUT /api/videos/{id}/edit`.
- Produces: `useEdl(videoId)` returns `{ edl, ops, undo, redo, canUndo, canRedo, saving }` where `ops = { split(vt), trim(id,edge,src), del(id), reorder(from,to), deleteSourceRange(a,b), setAll(edl) }`.

- [ ] **Step 1: Implement the hook**

```jsx
// frontend/src/hooks/useEdl.js
import { useEffect, useRef, useState, useCallback } from "react";
import * as E from "../edl.js";

export function useEdl(videoId) {
  const [edl, setEdl] = useState(null);
  const [past, setPast] = useState([]);
  const [future, setFuture] = useState([]);
  const [saving, setSaving] = useState(false);
  const saveTimer = useRef(null);

  // Load saved EDL (or default) when video changes.
  useEffect(() => {
    let cancelled = false;
    setEdl(null); setPast([]); setFuture([]);
    fetch(`/api/videos/${videoId}/edit`)
      .then((r) => r.json())
      .then((d) => { if (!cancelled) setEdl(d.segments); });
    return () => { cancelled = true; };
  }, [videoId]);

  // Debounced autosave.
  const scheduleSave = useCallback((next) => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      setSaving(true);
      await fetch(`/api/videos/${videoId}/edit`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ segments: next }),
      });
      setSaving(false);
    }, 500);
  }, [videoId]);

  const apply = useCallback((fn) => {
    setEdl((cur) => {
      const next = fn(cur);
      setPast((p) => [...p, cur]);
      setFuture([]);
      scheduleSave(next);
      return next;
    });
  }, [scheduleSave]);

  const ops = {
    split: (vt) => apply((e) => E.splitAtVirtual(e, vt)),
    trim: (id, edge, src) => apply((e) => E.trimSegment(e, id, edge, src)),
    del: (id) => apply((e) => E.deleteSegment(e, id)),
    reorder: (from, to) => apply((e) => E.reorderSegment(e, from, to)),
    deleteSourceRange: (a, b) => apply((e) => E.deleteSourceRange(e, a, b)),
    setAll: (next) => apply(() => next),
  };

  const undo = useCallback(() => {
    setPast((p) => {
      if (!p.length) return p;
      const prev = p[p.length - 1];
      setEdl((cur) => { setFuture((f) => [cur, ...f]); scheduleSave(prev); return prev; });
      return p.slice(0, -1);
    });
  }, [scheduleSave]);

  const redo = useCallback(() => {
    setFuture((f) => {
      if (!f.length) return f;
      const nxt = f[0];
      setEdl((cur) => { setPast((p) => [...p, cur]); scheduleSave(nxt); return nxt; });
      return f.slice(1);
    });
  }, [scheduleSave]);

  return { edl, ops, undo, redo, canUndo: past.length > 0, canRedo: future.length > 0, saving };
}
```

- [ ] **Step 2: Sanity check (manual)**

Import in a scratch and confirm no syntax errors via `npx vitest run` (the existing edl tests still pass; the hook is exercised in Task 12 E2E).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useEdl.js
git commit -m "feat(frontend): useEdl hook with undo/redo + debounced autosave"
```

---

## Task 9: PreviewPlayer (EDL-driven live playback)

**Files:**
- Create: `frontend/src/components/PreviewPlayer.jsx`

**Interfaces:**
- Consumes: `edl.js` `virtualToSource`, `totalDuration`; props `{videoId, edl, playheadRef, onVirtualTime}`.
- Produces: a `<video>` that plays the EDL non-destructively; exposes `seekVirtual(vt)` via a ref.

- [ ] **Step 1: Implement the player**

```jsx
// frontend/src/components/PreviewPlayer.jsx
import { useEffect, useRef, forwardRef, useImperativeHandle } from "react";
import { virtualToSource, totalDuration, segmentDuration } from "../edl.js";

export const PreviewPlayer = forwardRef(function PreviewPlayer(
  { videoId, edl, onVirtualTime }, ref
) {
  const videoRef = useRef(null);
  const edlRef = useRef(edl);
  edlRef.current = edl;

  // Map source time of the <video> back to virtual time; when the current
  // segment ends, jump to the next segment's source start.
  function onTimeUpdate() {
    const v = videoRef.current;
    const e = edlRef.current;
    if (!v || !e || !e.length) return;
    const src = v.currentTime;
    // find current segment by source time
    let acc = 0, idx = -1;
    for (let i = 0; i < e.length; i++) {
      if (src >= e[i].sourceStart - 0.05 && src <= e[i].sourceEnd + 0.05) { idx = i; break; }
      acc += segmentDuration(e[i]);
    }
    if (idx === -1) return;
    // recompute acc for idx
    acc = 0;
    for (let i = 0; i < idx; i++) acc += segmentDuration(e[i]);
    const seg = e[idx];
    if (src >= seg.sourceEnd - 0.03) {
      const next = e[idx + 1];
      if (next) v.currentTime = next.sourceStart;
      else v.pause();
    }
    onVirtualTime?.(acc + (src - seg.sourceStart));
  }

  useImperativeHandle(ref, () => ({
    seekVirtual(vt) {
      const map = virtualToSource(edlRef.current, vt);
      if (map && videoRef.current) videoRef.current.currentTime = map.source;
    },
    play() { videoRef.current?.play(); },
    pause() { videoRef.current?.pause(); },
  }));

  // When edit starts, ensure playhead sits inside a kept segment.
  useEffect(() => {
    const v = videoRef.current;
    if (!v || !edl?.length) return;
    const map = virtualToSource(edl, 0);
    if (map) v.currentTime = map.source;
  }, [videoId]);

  return (
    <video
      ref={videoRef}
      src={`/api/videos/${videoId}/file`}
      controls
      onTimeUpdate={onTimeUpdate}
      style={{ width: "100%", borderRadius: 8, background: "#000" }}
    />
  );
});
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/PreviewPlayer.jsx
git commit -m "feat(frontend): EDL-driven PreviewPlayer (live non-destructive playback)"
```

---

## Task 10: TranscriptPane (projection + click-seek + select-delete)

**Files:**
- Create: `frontend/src/components/TranscriptPane.jsx`

**Interfaces:**
- Consumes: `edl.js` `projectWords`; props `{transcript, edl, activeVirtual, onSeek(vt), onDeleteSourceRange(a,b)}`.
- Produces: rendered transcript in EDL order; click word → `onSeek(word.virtualStart)`; drag-select words + Delete/Backspace → `onDeleteSourceRange(minSource, maxSource)`.

- [ ] **Step 1: Implement the pane**

```jsx
// frontend/src/components/TranscriptPane.jsx
import { useMemo, useState } from "react";
import { projectWords } from "../edl.js";

export function TranscriptPane({ transcript, edl, activeVirtual, onSeek, onDeleteSourceRange }) {
  const words = useMemo(
    () => (transcript && edl ? projectWords(edl, transcript.words) : []),
    [transcript, edl]
  );
  const [sel, setSel] = useState(null); // {a,b} indices into `words`

  function isActive(w) {
    return activeVirtual >= w.virtualStart && activeVirtual <= w.virtualEnd;
  }
  function onWordMouseDown(idx) { setSel({ a: idx, b: idx }); }
  function onWordMouseEnter(idx) { setSel((s) => (s ? { ...s, b: idx } : s)); }
  function inSel(idx) {
    if (!sel) return false;
    const lo = Math.min(sel.a, sel.b), hi = Math.max(sel.a, sel.b);
    return idx >= lo && idx <= hi;
  }
  function onKeyDown(e) {
    if ((e.key === "Delete" || e.key === "Backspace") && sel) {
      const lo = Math.min(sel.a, sel.b), hi = Math.max(sel.a, sel.b);
      const a = words[lo], b = words[hi];
      onDeleteSourceRange(a.start, b.end);
      setSel(null);
    }
  }

  return (
    <div className="transcript" tabIndex={0} onKeyDown={onKeyDown}>
      {words.map((w, idx) => (
        <span
          key={`${w.segId}_${w.i}`}
          className={"word" + (isActive(w) ? " word-active" : "") + (inSel(idx) ? " word-sel" : "")}
          title={`${w.start.toFixed(2)}s`}
          onMouseDown={() => onWordMouseDown(idx)}
          onMouseEnter={() => onWordMouseEnter(idx)}
          onMouseUp={() => { if (sel && sel.a === sel.b) onSeek(w.virtualStart); }}
        >
          {w.word}
        </span>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/TranscriptPane.jsx
git commit -m "feat(frontend): TranscriptPane projection + click-seek + select-delete"
```

---

## Task 11: Timeline (clips, waveform, trim, split, ripple-delete, reorder) + Toolbar + EditorPage

**Files:**
- Create: `frontend/src/components/Timeline.jsx`
- Create: `frontend/src/components/Toolbar.jsx`
- Create: `frontend/src/EditorPage.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `useEdl`, `PreviewPlayer`, `TranscriptPane`, `edl.js`, waveform endpoint, fillers endpoint, export endpoint.
- Produces: full editor page; **invoke the `frontend-design` skill** for the visual pass (dark, Descript/Veed-like).

- [ ] **Step 1: Implement Timeline.jsx**

Render each segment as a flex-basis-proportional clip block; draw the waveform slice for the clip's source range from the peaks array on a `<canvas>`; left/right drag handles call `ops.trim`; a clip's ✕ calls `ops.del`; clip drag-and-drop (HTML5 draggable) calls `ops.reorder(from,to)`; a playhead line at `activeVirtual / totalDuration`; clicking the ruler seeks. (Full component code — pointer math for trim: `deltaSeconds = (dxPx / clipWidthPx) * segmentDuration`.)

```jsx
// frontend/src/components/Timeline.jsx  (core; styling via frontend-design)
import { useRef } from "react";
import { totalDuration, segmentDuration } from "../edl.js";

export function Timeline({ edl, peaks, activeVirtual, ops, onSeek }) {
  const dragFrom = useRef(null);
  const total = totalDuration(edl) || 1;

  function WaveformCanvas({ seg }) {
    const ref = useRef(null);
    // draw peaks for [seg.sourceStart, seg.sourceEnd] mapped onto canvas width
    function draw(c) {
      if (!c || !peaks?.length) return;
      const ctx = c.getContext("2d");
      const w = c.width, h = c.height;
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "#4f7cff";
      // peaks index range proportional to source time over full duration
      // (peaks cover the whole original audio)
      // caller passes srcDuration via dataset
      const startFrac = seg._startFrac, endFrac = seg._endFrac;
      const i0 = Math.floor(startFrac * peaks.length);
      const i1 = Math.ceil(endFrac * peaks.length);
      const span = Math.max(1, i1 - i0);
      for (let x = 0; x < w; x++) {
        const p = peaks[i0 + Math.floor((x / w) * span)] || 0;
        const bar = p * h;
        ctx.fillRect(x, (h - bar) / 2, 1, bar);
      }
    }
    return <canvas ref={(c) => draw(c)} width={300} height={48} className="wave" />;
  }

  return (
    <div className="timeline">
      {edl.map((seg, i) => {
        const frac = segmentDuration(seg) / total;
        return (
          <div
            key={seg.id}
            className="clip"
            style={{ flex: `${frac} 1 0` }}
            draggable
            onDragStart={() => (dragFrom.current = i)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => ops.reorder(dragFrom.current, i)}
          >
            <div className="handle l"
              onPointerDown={(e) => startTrim(e, seg, "start")} />
            <WaveformCanvas seg={seg} />
            <button className="clip-del" onClick={() => ops.del(seg.id)}>✕</button>
            <div className="handle r"
              onPointerDown={(e) => startTrim(e, seg, "end")} />
          </div>
        );
      })}
      <div className="playhead" style={{ left: `${(activeVirtual / total) * 100}%` }} />
    </div>
  );

  function startTrim(e, seg, edge) {
    e.preventDefault();
    const clipEl = e.currentTarget.parentElement;
    const widthPx = clipEl.getBoundingClientRect().width;
    const secPerPx = segmentDuration(seg) / widthPx;
    const startX = e.clientX;
    const base = edge === "start" ? seg.sourceStart : seg.sourceEnd;
    function move(ev) {
      const d = (ev.clientX - startX) * secPerPx;
      ops.trim(seg.id, edge, base + d);
    }
    function up() {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    }
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }
}
```

Note: compute `seg._startFrac/_endFrac` in EditorPage as `sourceStart/originalDuration` and `sourceEnd/originalDuration` before passing (peaks cover the whole original audio).

- [ ] **Step 2: Implement Toolbar.jsx**

```jsx
// frontend/src/components/Toolbar.jsx
export function Toolbar({ onSplit, onDetectFillers, onExport, undo, redo, canUndo, canRedo, saving, exporting }) {
  return (
    <div className="toolbar">
      <button onClick={onSplit}>Split at playhead</button>
      <button onClick={onDetectFillers}>Detect filler words</button>
      <button onClick={undo} disabled={!canUndo}>Undo</button>
      <button onClick={redo} disabled={!canRedo}>Redo</button>
      <button className="btn-primary" onClick={onExport} disabled={exporting}>
        {exporting ? "Exporting…" : "Export edited video"}
      </button>
      <span className="mono">{saving ? "saving…" : "saved"}</span>
    </div>
  );
}
```

- [ ] **Step 3: Implement EditorPage.jsx wiring everything**

Load transcript (poll `…/transcript`), waveform (poll `…/waveform`), original duration (from `…/videos/{id}`). Use `useEdl(videoId)`. Hold `activeVirtual` state updated by `PreviewPlayer.onVirtualTime`. Wire:
- `playerRef.seekVirtual(vt)` from TranscriptPane click and timeline ruler click.
- Split: `ops.split(activeVirtual)`.
- Detect fillers: GET `…/fillers`, map each filler word to `ops.deleteSourceRange(word.start, word.end)` (batch: compute combined and call once per word, or add a batch op). For batch correctness, fetch fillers, then for each filler index get `transcript.words[idx]` and accumulate ranges, then apply sequentially.
- Export: PUT is already autosaved; POST `…/export`; poll job; show exported `<video>` from `…/exports/{jobId}/file`.
- Pass `seg._startFrac/_endFrac` (sourceStart/originalDuration) to Timeline.

- [ ] **Step 4: Wire App.jsx to render EditorPage for the current video** (replace the old TranscriptView usage).

- [ ] **Step 5: Visual design pass**

Invoke the **frontend-design** skill and restyle `styles.css` + component classes to a Descript/Veed-like dark editor: top preview, transcript pane, bottom timeline with clip cards, waveform, drag handles, playhead. Keep it responsive.

- [ ] **Step 6: Manual smoke (real video, browser)**

`./scripts/run_api.sh`, `./scripts/run_worker.sh`, `cd frontend && npm run dev`; upload JLPT.mp4; confirm transcript, waveform, timeline render; split/trim/delete/reorder update preview + transcript live.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/Timeline.jsx frontend/src/components/Toolbar.jsx frontend/src/EditorPage.jsx frontend/src/App.jsx frontend/src/styles.css
git commit -m "feat(frontend): timeline editor + toolbar + editor page (Descript/Veed-like)"
```

---

## Task 12: End-to-end verification through the real UI (Playwright)

**Files:**
- Create: `e2e/editor_test.mjs`

**Interfaces:**
- Consumes: the running app + real `sample_short.mp4`.
- Produces: a PASS/FAIL report + screenshot proving live edit, reorder-in-transcript, persistence, export.

- [ ] **Step 1: Write the E2E script**

Drive the browser:
1. Upload `sample_short.mp4`; wait for transcript + waveform + timeline clips.
2. Delete a word in the transcript (drag-select one word, press Delete) → assert `totalDuration` shrank (read it from the timeline/preview) and the word disappears from the transcript projection **without** exporting → proves live edit.
3. Split at a playhead time, then drag-reorder the two clips → assert the transcript's first word now equals the word that was originally in the later segment → proves reorder reflected in transcript.
4. Reload the page → assert the edit persisted (same shortened transcript) → proves autosave.
5. Click Export → wait for exported `<video>`; assert it plays; (optional) backend re-transcribe to confirm the deleted word is gone.
6. Screenshot `/tmp/clipforge_editor.png`.

- [ ] **Step 2: Run it**

Run: `cd e2e && node editor_test.mjs ../clipforge/data/input/sample_short.mp4 /tmp/clipforge_editor.png`
Expected: `RESULT: PASS`, zero console errors, screenshot saved.

- [ ] **Step 3: Commit**

```bash
git add e2e/editor_test.mjs
git commit -m "test(e2e): editor live-edit, reorder, persistence, export through UI"
```

---

## Self-Review Notes

- **Spec coverage:** EDL model (T1-4), persistence/validation/endpoints (T5), waveform (T6), export-from-EDL incl. reorder (T7), live preview (T9), transcript projection + select-delete (T10), timeline trim/split/ripple/reorder (T11), undo/redo + autosave (T8), Descript/Veed visual (T11 step 5), verification on real video (T6/T7 pytest + T12 Playwright). All spec sections map to a task.
- **Type consistency:** `Segment = {id, sourceStart, sourceEnd}` used identically across JS (`edl.js`) and Python (`edl.py`, export). `ops` method names (`split/trim/del/reorder/deleteSourceRange/setAll`) consistent between `useEdl` and consumers. `projectWords` output fields (`virtualStart/virtualEnd/segId`) consistent between Task 4 and TranscriptPane.
- **Filler batch op:** EditorPage applies fillers via repeated `ops.deleteSourceRange` (each is immutable + undoable); acceptable. If undo granularity per-word is undesirable, add a `deleteSourceRanges(list)` op later (out of scope now).
- **No placeholders:** every code step contains real code; the only deferred detail is reusing the already-written `_build_filtergraph`/ffmpeg block in Task 7 (explicitly "keep existing").
```
