"""Worker step: run gemma4 prompt-to-edit and persist the proposal.

Runs in the worker (one-at-a-time, text-only). Never fabricates: on parse
failure the stored row has a null clip + the raw model output + the error.
"""
from __future__ import annotations

import json

from backend import db
from backend.ai_edit import detect_ai_edit


def run_ai_edit_job(video_id: str, prompt: str) -> dict:
    res = detect_ai_edit(video_id, prompt)
    db.save_ai_edit(
        video_id,
        clip_json=json.dumps(res["clip"]) if res.get("clip") else None,
        aspect=res.get("aspect"),
        caption_preset=res.get("caption_preset"),
        reason=res.get("reason"),
        raw=res.get("raw"),
        error=res.get("error"),
    )
    return {"ok": res.get("error") is None, "aspect": res.get("aspect")}
