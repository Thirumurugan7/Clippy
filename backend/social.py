"""Generate post-ready social copy from the transcript with the local LLM.

A hook title, a one-line description, and hashtags — what Opus Clip / Vizard /
Submagic auto-write for each clip. One strict-JSON gemma4 call; safe fallback so
a bad model response never 500s the endpoint. Text-only, never fabricated beyond
what the transcript supports.
"""
from __future__ import annotations

import json

from backend import db
from backend.llm import get_provider

STRICTER = "\n\nOutput ONLY the JSON object — no prose, no markdown fences."


def _build_prompt(text: str) -> str:
    snippet = text.strip()[:4000]
    return (
        "You are a short-form social media strategist. From the transcript below, "
        "write copy for the clip that would make someone stop scrolling.\n"
        'Return STRICT JSON: {"title": "...", "hook": "...", "description": "...", '
        '"hashtags": ["#...", ...]}\n'
        "- title: a punchy YouTube/TikTok title, <= 60 chars.\n"
        "- hook: the first line to say/show in the first 2 seconds, <= 80 chars.\n"
        "- description: one engaging sentence for the caption.\n"
        "- hashtags: 5-8 relevant lowercase hashtags, each starting with #.\n\n"
        f"Transcript:\n{snippet}"
    )


def _parse(raw: str) -> dict | None:
    try:
        d = json.loads(raw)
    except Exception:
        return None
    if not isinstance(d, dict):
        return None
    tags = d.get("hashtags") or []
    if isinstance(tags, str):
        tags = tags.split()
    tags = [("#" + t.lstrip("#")) for t in (str(x).strip() for x in tags) if t][:8]
    return {
        "title": str(d.get("title", "")).strip()[:100],
        "hook": str(d.get("hook", "")).strip()[:120],
        "description": str(d.get("description", "")).strip()[:280],
        "hashtags": tags,
    }


def generate_social(video_id: str) -> dict:
    tr = db.get_transcript(video_id)
    if tr is None:
        raise ValueError("transcript not ready")
    segments = json.loads(tr["segments_json"])
    text = " ".join(s.get("text", "") for s in segments).strip()
    if not text:
        return {"title": "", "hook": "", "description": "", "hashtags": []}
    provider = get_provider()
    prompt = _build_prompt(text)
    out = _parse(provider.complete(prompt, json_mode=True))
    if out is None:
        out = _parse(provider.complete(prompt + STRICTER, json_mode=True))
    return out or {"title": "", "hook": "", "description": "", "hashtags": []}
