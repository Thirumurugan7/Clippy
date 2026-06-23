"""Plain-English editing: gemma4 turns an instruction like "make a 40s Instagram
reel" into a concrete proposal — a clip range, an aspect ratio, and a caption
preset — using the transcript text only. Strict JSON, retry-once-stricter, raw
surfaced on failure, never fabricated. The proposal is applied as a reviewable
edit on the frontend (sets EDL + settings); nothing is finalized automatically.
"""
from __future__ import annotations

import json

from backend import db
from backend.llm import get_provider
from backend.presets import ASPECTS, CAPTION_PRESETS

STRICTER = "\n\nOutput ONLY the JSON object — no prose, no markdown fences."


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def parse_ai_edit(raw: str, duration: float) -> dict:
    data = json.loads(raw)
    clip = data["clip"]
    start = _clamp(float(clip["start"]), 0.0, duration)
    end = _clamp(float(clip["end"]), 0.0, duration)
    if end <= start:
        raise ValueError(f"clip end {end} <= start {start}")
    aspect = data.get("aspect") if data.get("aspect") in ASPECTS else "9:16"
    preset = data.get("caption_preset") if data.get("caption_preset") in CAPTION_PRESETS else "karaoke"
    return {
        "clip": {"start": round(start, 2), "end": round(end, 2)},
        "aspect": aspect,
        "caption_preset": preset,
        "reason": str(data.get("reason", "")).strip(),
    }


def _build_prompt(prompt: str, segments: list[dict], duration: float) -> str:
    lines = [f"[{s['start']:.2f}-{s['end']:.2f}] {s['text'].strip()}" for s in segments]
    return f"""You are a short-form video editor. A creator gave this instruction:
"{prompt}"

Below is the timestamped transcript of a {duration:.0f}-second video.

Decide:
- The platform/aspect from the instruction: Instagram reel / TikTok / YouTube \
Shorts -> "9:16"; square Instagram post -> "1:1"; Instagram portrait -> "4:5"; \
YouTube landscape -> "16:9". Default "9:16".
- The target length from the instruction (e.g. "40s" -> 40 seconds). If none, ~30s.
- The single best self-contained clip. IMPORTANT: (end - start) MUST be within 10 \
seconds of the target length — combine consecutive transcript lines to reach it; \
do not return a much shorter clip. A strong hook and a clear payoff. Use ONLY \
timestamps from the transcript; 0 <= start < end <= {duration:.2f}.
- A caption preset that fits the vibe, one of: {", ".join(CAPTION_PRESETS)}.

Return STRICT JSON exactly:
{{"clip": {{"start": <s>, "end": <s>}}, "aspect": "9:16", "caption_preset": "karaoke", "reason": "<one line>"}}

Transcript:
{chr(10).join(lines)}
"""


def detect_ai_edit(video_id: str, prompt: str) -> dict:
    video = db.get_video(video_id)
    tr = db.get_transcript(video_id)
    if tr is None:
        raise RuntimeError("transcript required")
    segments = json.loads(tr["segments_json"])
    duration = tr["duration_seconds"] or (video["duration_seconds"] if video else 0.0)
    provider = get_provider()
    full = _build_prompt(prompt, segments, duration)

    raw = provider.complete(full, json_mode=True)
    try:
        out = parse_ai_edit(raw, duration)
        return {**out, "raw": raw, "model": provider.name()}
    except Exception:
        raw2 = provider.complete(full + STRICTER, json_mode=True)
        try:
            out = parse_ai_edit(raw2, duration)
            return {**out, "raw": raw2, "model": provider.name()}
        except Exception as e:
            return {"error": str(e), "raw": raw2, "model": provider.name(),
                    "clip": None, "aspect": None, "caption_preset": None, "reason": None}
