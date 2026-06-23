"""Highlight detection: gemma4 reads the REAL transcript text and proposes
candidate short-form clips (start, end, reason, score).

Hard rules honored here:
- The model only reads the text transcript (segments with timestamps).
- Output is strict JSON, parsed safely. On malformed/invalid output we retry
  once with a stricter prompt, then surface the raw output to the caller.
- We NEVER fabricate highlights. If parsing fails twice, `clips` is None and the
  raw model text is returned for inspection.
"""
from __future__ import annotations

import json

from backend import db
from backend.llm import get_provider

STRICTER_SUFFIX = (
    "\n\nIMPORTANT: Output ONLY the JSON object. No prose, no explanation, no "
    "markdown code fences. It must parse with a strict JSON parser."
)


def build_prompt(segments: list[dict], duration: float, n: int) -> str:
    lines = [f"[{s['start']:.2f}-{s['end']:.2f}] {s['text'].strip()}" for s in segments]
    transcript = "\n".join(lines)
    return f"""You are an expert short-form video editor. Below is the timestamped \
transcript of a {duration:.0f}-second video. Each line is "[start-end] text" in seconds.

Pick up to {n} candidate clips that would make the strongest vertical short-form \
videos: a strong hook, a self-contained idea with a clear payoff. Prefer moments \
with tension, insight, emotion, or a satisfying conclusion.

LENGTH IS IMPORTANT: each clip should be 20-60 seconds long. Combine several \
consecutive transcript lines so the clip starts at a natural hook and ends on a \
complete thought. Do NOT return clips shorter than 15 seconds. If a great moment \
is brief, extend its start/end to include the surrounding context that sets it up \
and pays it off.

Rules:
- Use ONLY timestamps that appear in the transcript above.
- For each clip: start < end, (end - start) between 15 and 75 seconds, and both \
within [0, {duration:.2f}].
- "reason" is one short sentence on why it hooks.
- "score" is your confidence from 0 to 1.

Return STRICT JSON in exactly this shape and nothing else:
{{"clips": [{{"start": <seconds>, "end": <seconds>, "reason": "<one line>", "score": <0..1>}}]}}

Transcript:
{transcript}
"""


def parse_highlights(raw: str, duration: float) -> list[dict]:
    """Parse + validate the model JSON. Raises on malformed JSON / wrong shape."""
    data = json.loads(raw)
    clips_in = data["clips"]  # KeyError if missing -> treated as parse failure
    if not isinstance(clips_in, list):
        raise ValueError("'clips' is not a list")
    out = []
    for c in clips_in:
        start = float(c["start"])
        end = float(c["end"])
        if not (0 <= start < end <= duration + 0.5):
            continue  # drop out-of-range; never invent
        score = c.get("score")
        out.append({
            "start": round(start, 2),
            "end": round(min(end, duration), 2),
            "reason": str(c.get("reason", "")).strip(),
            "score": round(float(score), 3) if score is not None else None,
        })
    out.sort(key=lambda x: x["start"])
    return out


def detect_highlights(video_id: str, n: int = 5) -> dict:
    video = db.get_video(video_id)
    if video is None:
        raise RuntimeError(f"video {video_id} not found")
    tr = db.get_transcript(video_id)
    if tr is None:
        raise RuntimeError("transcript not available; run transcription first")

    segments = json.loads(tr["segments_json"])
    duration = tr["duration_seconds"] or video["duration_seconds"] or 0.0
    provider = get_provider()
    prompt = build_prompt(segments, duration, n)

    raw = provider.complete(prompt, json_mode=True)
    try:
        clips = parse_highlights(raw, duration)
        return {"clips": clips, "raw": raw, "model": provider.name(), "retried": False}
    except Exception as first:
        raw2 = provider.complete(prompt + STRICTER_SUFFIX, json_mode=True)
        try:
            clips = parse_highlights(raw2, duration)
            return {"clips": clips, "raw": raw2, "model": provider.name(), "retried": True}
        except Exception as second:
            # Never fabricate — surface the raw output for inspection.
            return {
                "clips": None,
                "error": f"{type(first).__name__}: {first} / {type(second).__name__}: {second}",
                "raw": raw2,
                "model": provider.name(),
                "retried": True,
            }
