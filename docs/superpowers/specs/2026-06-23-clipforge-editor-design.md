# ClipForge Non-Destructive Editor (Expanded M2) — Design Spec

Date: 2026-06-23
Status: Approved (design); pending spec review

## Goal

Replace the current "mark words → export-only" editor with a Descript/Veed-style
non-destructive editor where:

1. **Edits update the preview live** (not just the exported file).
2. The user can **cut, trim, split, ripple-delete, and reorder** like a normal
   video editor, in addition to editing via the transcript.
3. The transcript **never desyncs** from the edit, regardless of operation
   (including reorder).
4. The UI looks and feels like Descript/Veed (dark, professional, timeline-based).

All processing stays local and free (ffmpeg + faster-whisper already in place).
No paid APIs. This expands milestone M2; M3 (highlights) and M4 (vertical export)
remain after it.

## Core Architecture: the Edit Decision List (EDL)

The single source of truth for an edit is an **ordered list of segments**:

```
EDL = [ { id, sourceStart, sourceEnd }, ... ]   # times in seconds, source = original video
```

- Initial state for a video: one segment `[0, duration]`.
- The **virtual timeline** is the concatenation of segments in list order. A
  segment's virtual position depends only on the durations of segments before it.
- Every edit operation is a pure transformation of this list:

| Operation          | Effect on EDL |
|--------------------|---------------|
| Split at virtual time t | Find the covering segment, replace it with two segments split at the mapped source time. |
| Trim (drag handle) | Adjust a segment's `sourceStart` or `sourceEnd` (clamped within neighbors / source bounds). |
| Ripple-delete      | Remove a segment from the list (downstream segments shift earlier in virtual time). |
| Reorder            | Move a segment to a new index in the list. |
| Transcript word-delete | Map the word's `[start,end]` to the covering segment(s); trim/split to excise that sub-range. |

### Derived views (pure functions of the EDL — never independent state)

- **Transcript projection:** walk segments in EDL order; for each, emit the words
  whose `[start,end]` intersect `[sourceStart, sourceEnd]`. A word straddling a
  cut boundary is included only if ≥50% of its duration remains; otherwise
  dropped. Because the transcript is computed from the EDL in list order, it
  always matches the timeline and cannot desync. After a reorder it reads in
  **timeline order**, not original chronological order (accepted consequence).
- **Player (live preview):** a controller maps `virtualTime → (segment, offset)
  → sourceTime`. During playback it seeks the original `<video>` element; when
  the playhead reaches a segment's end it jumps to the next segment's
  `sourceStart`. Reordered/cut segments cause non-contiguous seeks (small
  re-buffer stall possible — acceptable for preview; export is seamless).
- **Timeline:** each segment renders as a clip block with width ∝ its duration,
  a waveform slice underneath, drag handles for trim, a split action at the
  playhead, ripple-delete, and drag-to-reorder.

## Data & Persistence

New table:

```sql
CREATE TABLE edits (
  video_id   TEXT PRIMARY KEY REFERENCES videos(id),
  edl_json   TEXT NOT NULL,   -- the ordered segment list
  updated_at REAL NOT NULL
);
```

- The frontend holds the working EDL in React state for responsive editing and
  autosaves (debounced ~500ms) to the backend, so edits survive a page reload.
- On load: `GET /api/videos/{id}/edit` returns the saved EDL, or a default
  single-segment EDL if none exists.

## API Changes

| Endpoint | Purpose |
|---|---|
| `GET  /api/videos/{id}/edit` | Return saved EDL (or default single segment). |
| `PUT  /api/videos/{id}/edit` | Persist EDL (`{segments:[...]}`). Validated server-side. |
| `GET  /api/videos/{id}/waveform` | Return precomputed audio peaks (JSON array) for the timeline. |
| `POST /api/videos/{id}/export` | Export the **saved EDL** (segments in order) via existing ffmpeg trim+concat. |

- The existing `GET /api/videos/{id}/file` (range streaming) powers the live
  preview unchanged.
- `detect_fillers` stays; "Detect fillers" maps fillers to EDL deletions instead
  of a separate `deleted` set.

## Worker Changes

- New step **`waveform`**: on upload, decode audio to mono PCM via ffmpeg,
  downsample to ~1000 peak values, store as JSON at
  `data/exports/<id>/waveform.json`. Enqueued after `probe`. The
  `GET .../waveform` endpoint returns this file (404 → not ready, poll).
- `export_edit` updated to read the saved EDL (ordered segments) rather than a
  delete-index list. The ffmpeg trim+concat already concatenates in list order,
  so reorder/trim/split all flow through unchanged.

## Frontend Components

- `EditorPage` — layout shell (preview / transcript / timeline).
- `PreviewPlayer` — EDL-driven playback controller over a single `<video>`.
- `TranscriptPane` — renders the transcript projection; click word = seek
  (virtual time); select word range + delete = EDL edit.
- `Timeline` — clip blocks, waveform, trim handles (pointer events), split at
  playhead, ripple-delete, drag-to-reorder.
- `Toolbar` — Split, Delete, Detect fillers, Undo/Redo, Export.
- `useEdl` hook — holds EDL + operations + autosave; single place all edits go.
- Visual design via the **frontend-design** skill (dark, Descript/Veed-like).

Undo/redo: EDL is small and serialisable, so undo/redo is a snapshot stack of
EDL states (kept in the `useEdl` hook).

## Edge Cases & Rules

- **Delete everything:** export refuses (clear error) if the EDL is empty; the UI
  disables export when no segments remain.
- **Partial words at cut boundaries:** ≥50%-remaining rule for transcript display
  (above). Cuts themselves are on exact source times.
- **Trim limits:** a segment cannot be trimmed to negative/zero length; handles
  clamp to a minimum (e.g. 1 frame).
- **Splice artifact:** cutting mid-speech can make re-transcription mis-hear the
  join (known, accepted; "correct over fancy"). Not addressed in v1.

## Testing / Verification (per project rules: run on the real video, show output)

Browser-driven (Playwright) on the real video:
1. Delete a word in the transcript → preview **skips** that range during live
   playback (no export needed).
2. Split + ripple-delete a middle segment → virtual duration shrinks; transcript
   drops those words; preview plays the join.
3. Reorder two segments → transcript order updates to match; preview plays in new
   order.
4. Export → output file duration and content match the EDL (re-transcribe to
   confirm, as in M2).
5. Reload page → edit persists (EDL autosaved).

## Out of Scope (v1)

Multi-track / picture-in-picture, audio detach, transitions/crossfades, color
grading/LUTs, timeline zoom (stretch goal only), generative B-roll. M3/M4 remain
separate milestones.
```
