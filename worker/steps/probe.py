"""Probe a real video file with ffprobe and persist its metadata.

This is genuine work, not a placeholder: it reads the actual uploaded file and
extracts duration, resolution, frame rate, and codecs. Later milestones need
these values (e.g. duration to bound clip ranges, fps for caption timing).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Optional

from backend import db


def _ffprobe_path() -> str:
    path = shutil.which("ffprobe")
    if path is None:
        raise RuntimeError(
            "ffprobe not found on PATH. Install ffmpeg (brew install ffmpeg)."
        )
    return path


def _parse_fps(rate: Optional[str]) -> Optional[float]:
    """ffprobe reports frame rate as a fraction string like '30000/1001'."""
    if not rate or rate == "0/0":
        return None
    if "/" in rate:
        num, den = rate.split("/", 1)
        try:
            den_f = float(den)
            if den_f == 0:
                return None
            return float(num) / den_f
        except ValueError:
            return None
    try:
        return float(rate)
    except ValueError:
        return None


def run_probe(video_id: str) -> dict:
    """Run ffprobe on the stored file for `video_id`, persist metadata, return it."""
    video = db.get_video(video_id)
    if video is None:
        raise RuntimeError(f"video {video_id} not found")

    stored_path = video["stored_path"]
    cmd = [
        _ffprobe_path(),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        stored_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed (exit {proc.returncode}): {proc.stderr.strip()}"
        )

    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if video_stream is None:
        raise RuntimeError("No video stream found in file (is this really a video?).")

    duration = None
    if fmt.get("duration") is not None:
        try:
            duration = float(fmt["duration"])
        except (TypeError, ValueError):
            duration = None

    width = video_stream.get("width")
    height = video_stream.get("height")
    fps = _parse_fps(video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate"))
    video_codec = video_stream.get("codec_name")
    audio_codec = audio_stream.get("codec_name") if audio_stream else None

    db.update_video_metadata(
        video_id,
        duration_seconds=duration,
        width=width,
        height=height,
        fps=fps,
        video_codec=video_codec,
        audio_codec=audio_codec,
    )

    return {
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "video_codec": video_codec,
        "audio_codec": audio_codec,
        "has_audio": audio_stream is not None,
    }
