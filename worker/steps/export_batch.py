"""Batch export: turn ONE long source video into MANY vertical shorts in a
single job — Clippy's headline promise ("one video -> clips", plural).

Each requested clip is a source time range `{start, end}` (typically the
highlight candidates from M3). For each, we build a single-segment EDL and reuse
the exact vertical reframe+caption pipeline (`render_vertical_clip`), so every
short is byte-for-byte what the single-clip export would produce. The shared
face-track trajectory (reframe.json, keyed by source time) is computed once and
reused across all clips.

params_json: {"clips": [{"start": float, "end": float, "reason"?: str}, ...]}
result_json: {"clips": [{"index", "start", "end", "output_path", "duration",
              "error"?}, ...], "count", "ok"}
"""
from __future__ import annotations

import json

from backend import db, config
from worker.steps.vertical import DEFAULT_SETTINGS, load_reframe, render_vertical_clip


def _normalize_clips(raw_clips, duration: float) -> list[dict]:
    """Coerce/clamp incoming ranges; drop degenerate ones. Order preserved."""
    out = []
    for c in raw_clips or []:
        try:
            start = max(0.0, float(c["start"]))
            end = min(duration, float(c["end"]))
        except (KeyError, TypeError, ValueError):
            continue
        if end - start < 0.2:  # skip sub-frame slivers
            continue
        out.append({"start": round(start, 2), "end": round(end, 2),
                    "reason": str(c.get("reason", "")).strip()})
    return out


def run_export_batch(job) -> dict:
    video_id = job["video_id"]
    params = json.loads(job["params_json"] or "{}")

    video = db.get_video(video_id)
    if video is None:
        raise RuntimeError(f"video {video_id} not found")
    tr = db.get_transcript(video_id)
    if tr is None:
        raise RuntimeError("transcript required for captions")

    clips = _normalize_clips(params.get("clips"), float(video["duration_seconds"]))
    if not clips:
        raise RuntimeError("no valid clips to export")

    out_dir = config.EXPORTS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)

    srow = db.get_settings(video_id)
    settings = json.loads(srow["json"]) if srow else DEFAULT_SETTINGS
    rf = load_reframe(video_id, out_dir)
    centers = rf.get("centers", [])
    words = json.loads(tr["words_json"])

    results = []
    for i, clip in enumerate(clips):
        segments = [{
            "id": f"clip{i}",
            "sourceStart": clip["start"],
            "sourceEnd": clip["end"],
        }]
        intermediate = out_dir / f"{job['id']}_clip{i}_edit.mp4"
        final = out_dir / f"{job['id']}_clip{i}_vertical.mp4"
        entry = {"index": i, "start": clip["start"], "end": clip["end"],
                 "reason": clip["reason"]}
        try:
            r = render_vertical_clip(video, words, segments, settings, centers, intermediate, final)
            entry.update({"output_path": r["output_path"], "duration": r["duration"],
                          "width": r["width"], "height": r["height"]})
        except Exception as exc:  # one bad clip must not sink the whole batch
            intermediate.unlink(missing_ok=True)
            entry["error"] = str(exc)
        results.append(entry)

    ok = sum(1 for r in results if "error" not in r)
    return {"clips": results, "count": len(results), "ok": ok}
