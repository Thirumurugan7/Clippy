"""Compute downsampled audio peaks for the timeline waveform (real ffmpeg).

Decodes the real audio track to mono 8 kHz PCM and reduces it to ~1000 peak
values (max absolute amplitude per bucket, normalised 0..1). The timeline draws
these under each clip. Stored as JSON at data/exports/<id>/waveform.json.
"""
from __future__ import annotations

import array
import json
import shutil
import subprocess

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

    proc = subprocess.run(
        [_ffmpeg(), "-v", "error", "-i", video["stored_path"],
         "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg waveform decode failed: {proc.stderr.decode()[-500:]}"
        )

    samples = array.array("h")
    samples.frombytes(proc.stdout)
    n = len(samples)
    buckets = min(PEAK_BUCKETS, max(1, n))
    size = max(1, n // buckets)

    raw = []
    for i in range(0, n, size):
        chunk = samples[i:i + size]
        raw.append(max((abs(x) for x in chunk), default=0) / 32768.0)

    # Normalise to the loudest peak so the waveform fills the timeline height
    # regardless of the recording's absolute level (clamped to [0,1]).
    loudest = max(raw, default=0.0)
    scale = (1.0 / loudest) if loudest > 0 else 0.0
    peaks = [round(min(1.0, p * scale), 4) for p in raw]

    out_dir = config.EXPORTS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "waveform.json").write_text(
        json.dumps({"peaks": peaks, "count": len(peaks)})
    )
    return {"count": len(peaks)}
