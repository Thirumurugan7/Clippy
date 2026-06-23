"""Worker step: run gemma4 highlight detection and persist the result.

Runs inside the worker so it is one-job-at-a-time and never overlaps whisper or
ffmpeg (the 16 GB memory rule). Stores the parsed clips, the raw model output,
and any error. Never fabricates clips: a parse failure stores clips_json=NULL
with the raw output for inspection.
"""
from __future__ import annotations

import json

from backend import db
from backend.highlights import detect_highlights


def run_highlights_job(video_id: str) -> dict:
    res = detect_highlights(video_id, n=5)
    clips = res.get("clips")
    db.save_highlights(
        video_id,
        clips_json=json.dumps(clips) if clips is not None else None,
        raw=res.get("raw"),
        model=res.get("model"),
        error=res.get("error"),
    )
    return {
        "model": res.get("model"),
        "num_clips": len(clips) if clips is not None else 0,
        "parsed": clips is not None,
        "retried": res.get("retried"),
    }
