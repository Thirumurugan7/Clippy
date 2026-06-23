"""Export an edited video: delete the time spans of selected words and
concatenate the kept segments, re-encoding for frame accuracy.

Real cuts on the real timeline. The word time spans come from the stored
faster-whisper word-level timestamps. ffmpeg `trim`/`atrim` + `concat` produce a
single output in one pass; re-encoding (not stream copy) means cuts land on the
exact requested time, not the nearest keyframe.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from backend import db, config


def _bin(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"{name} not found on PATH (install ffmpeg).")
    return path


def _probe_duration(path: str) -> float:
    out = subprocess.run(
        [_bin("ffprobe"), "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def compute_kept_intervals(
    deleted_spans: list[tuple[float, float]],
    total_duration: float,
    merge_gap: float = 0.02,
) -> list[tuple[float, float]]:
    """Given spans to delete, return the complementary spans to keep within
    [0, total_duration]. Deleted spans are merged when they touch/overlap; kept
    intervals shorter than merge_gap are dropped to avoid 1-frame fragments.
    """
    if not deleted_spans:
        return [(0.0, total_duration)]

    spans = sorted((max(0.0, s), min(total_duration, e)) for s, e in deleted_spans)
    merged: list[list[float]] = []
    for s, e in spans:
        if e <= s:
            continue
        if merged and s <= merged[-1][1] + merge_gap:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    kept: list[tuple[float, float]] = []
    cursor = 0.0
    for s, e in merged:
        if s - cursor > merge_gap:
            kept.append((cursor, s))
        cursor = max(cursor, e)
    if total_duration - cursor > merge_gap:
        kept.append((cursor, total_duration))
    return kept


def _build_filtergraph(kept: list[tuple[float, float]], has_audio: bool) -> str:
    parts = []
    for n, (s, e) in enumerate(kept):
        parts.append(
            f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{n}];"
        )
        if has_audio:
            parts.append(
                f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{n}];"
            )
    if has_audio:
        streams = "".join(f"[v{n}][a{n}]" for n in range(len(kept)))
        parts.append(f"{streams}concat=n={len(kept)}:v=1:a=1[outv][outa]")
    else:
        streams = "".join(f"[v{n}]" for n in range(len(kept)))
        parts.append(f"{streams}concat=n={len(kept)}:v=1:a=0[outv]")
    return "\n".join(parts)


def run_export_edit(job) -> dict:
    video_id = job["video_id"]
    params = json.loads(job["params_json"] or "{}")
    delete_indices = set(params.get("delete_word_indices", []))

    video = db.get_video(video_id)
    if video is None:
        raise RuntimeError(f"video {video_id} not found")
    tr = db.get_transcript(video_id)
    if tr is None:
        raise RuntimeError("transcript not available; cannot map words to time")

    words = json.loads(tr["words_json"])
    total_duration = video["duration_seconds"] or _probe_duration(video["stored_path"])
    has_audio = bool(video["audio_codec"])

    deleted_spans = [
        (words[i]["start"], words[i]["end"])
        for i in delete_indices
        if 0 <= i < len(words)
    ]
    kept = compute_kept_intervals(deleted_spans, total_duration)
    if not kept:
        raise RuntimeError("Edit removes the entire video; nothing left to export.")

    out_dir = config.EXPORTS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{job['id']}.mp4"

    graph = _build_filtergraph(kept, has_audio)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write(graph)
        graph_path = f.name

    cmd = [
        _bin("ffmpeg"), "-y", "-i", video["stored_path"],
        "-filter_complex_script", graph_path,
        "-map", "[outv]",
    ]
    if has_audio:
        cmd += ["-map", "[outa]", "-c:a", "aac", "-b:a", "192k"]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-movflags", "+faststart", str(out_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    Path(graph_path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg export failed (exit {proc.returncode}): {proc.stderr[-1500:]}"
        )

    out_duration = _probe_duration(str(out_path))
    removed = sum(e - s for s, e in deleted_spans) if deleted_spans else 0.0
    return {
        "output_path": str(out_path),
        "num_words_deleted": len(delete_indices),
        "num_kept_segments": len(kept),
        "original_duration": round(total_duration, 3),
        "output_duration": round(out_duration, 3),
        "removed_seconds_estimate": round(removed, 3),
    }
