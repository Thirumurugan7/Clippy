"""Translate caption cues into another language with the local LLM (gemma4).

Line-level (not word-level): each subtitle cue is translated as a unit and keeps
its original timing, which is how subtitles work anyway — this sidesteps the
word-karaoke timing problem entirely. One batched, strict-JSON call per request;
falls back to the original text rather than failing a download.
"""
from __future__ import annotations

import json

from backend.llm import get_provider

# Curated allowlist so the target language can't be an arbitrary injected string.
LANGUAGES = {
    "es": "Spanish", "hi": "Hindi", "fr": "French", "de": "German",
    "pt": "Portuguese", "ja": "Japanese", "zh": "Chinese (Simplified)",
    "ar": "Arabic", "ko": "Korean", "it": "Italian", "ru": "Russian", "ta": "Tamil",
}

STRICTER = "\n\nOutput ONLY the JSON object — no prose, no markdown fences."


def _parse(raw: str, n: int):
    try:
        data = json.loads(raw)
    except Exception:
        return None
    lines = data.get("lines") if isinstance(data, dict) else data
    if not isinstance(lines, list) or not lines:
        return None
    lines = [str(x) for x in lines]
    if len(lines) < n:
        lines += [""] * (n - len(lines))
    return lines[:n]


def _build_prompt(lines: list[str], language: str) -> str:
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(lines))
    return (
        f"Translate each numbered subtitle line into {language}. Keep it natural "
        f"and concise (these are short video captions). Preserve names/acronyms.\n"
        f'Return STRICT JSON: {{"lines": ["...", ...]}} with EXACTLY {len(lines)} '
        f"strings, in the same order, each the translation of the matching line "
        f"(translation only, no numbering).\n\nLines:\n{numbered}"
    )


def translate_lines(lines: list[str], lang_code: str) -> list[str]:
    language = LANGUAGES.get(lang_code)
    if not language or not lines:
        return list(lines)
    provider = get_provider()
    prompt = _build_prompt(lines, language)
    out = _parse(provider.complete(prompt, json_mode=True), len(lines))
    if out is None:
        out = _parse(provider.complete(prompt + STRICTER, json_mode=True), len(lines))
    if out is None:
        return list(lines)  # never fail the download; just return source text
    return [t or src for t, src in zip(out, lines)]


def translate_cues(cues: list[dict], lang_code: str) -> list[dict]:
    translated = translate_lines([c["text"] for c in cues], lang_code)
    return [{**c, "text": t} for c, t in zip(cues, translated)]
