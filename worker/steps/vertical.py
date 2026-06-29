"""Vertical (9:16) export: reframe the edited clip with a face-tracked crop and
draw animated word-level captions, in a single frame-by-frame pass.

Stages:
  1. Render the EDL to a horizontal intermediate (shared render_segments).
  2. For each frame: detect the main face (mediapipe), smooth a horizontal pan,
     crop a 9:16 window, scale to 1080x1920, draw the karaoke caption for that
     moment (Pillow), and pipe to ffmpeg which muxes the original audio.

If faces are rarely found, the smoothed centre stays near the middle -> center
crop (the intended fallback: never produce a bad track). Simple and correct over
fancy: horizontal pan only, motion-smoothed.
"""
from __future__ import annotations

import json
import subprocess
import warnings

import cv2

from backend import db, config
from backend.edl import ordered_intervals, project_words, virtual_to_source, cx_at
from backend.crop import compute_crop, target_dims
from backend.captions import CaptionRenderer
from backend.presets import resolve_caption_style
from worker.steps.export_edit import render_segments, _bin, _probe_duration
from worker.steps.reframe import run_reframe

warnings.filterwarnings("ignore")

SMOOTH_ALPHA = 0.2  # EMA over the per-frame centre to keep the pan smooth

DEFAULT_SETTINGS = {
    "aspect": "9:16", "framing": "auto", "crop_cx": 0.5,
    "caption": {"preset": "karaoke", "fontsize": 58, "color": "#ff8a3d", "position": "bottom"},
}


def _reframe_and_caption(in_path, out_path, renderer, centers, segments, aspect, framing, crop_cx, crop_cy, segmenter=None) -> dict:
    """Crop the edited intermediate to the chosen aspect, following the
    precomputed face trajectory (auto) or a fixed centre (manual), draw captions,
    and mux audio. Same trajectory as the live preview, so export == preview.
    """
    cap = cv2.VideoCapture(in_path)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    tw, th = target_dims(aspect)

    ff = subprocess.Popen(
        [_bin("ffmpeg"), "-y",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{tw}x{th}",
         "-r", f"{fps}", "-i", "-",
         "-i", in_path,
         "-map", "0:v:0", "-map", "1:a:0?", "-shortest",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_path],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    assert ff.stdin is not None

    cur_cx = crop_cx if framing == "manual" else 0.5
    total = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        vt = total / fps
        if framing == "manual":
            cur_cx = crop_cx
            cy = crop_cy
        else:
            src_t = virtual_to_source(segments, vt)
            target = cx_at(centers, src_t) if centers else 0.5
            cur_cx += SMOOTH_ALPHA * (target - cur_cx)
            cy = 0.5
        sx, sy, cw, ch = compute_crop(W, H, aspect, cur_cx, cy)
        out = cv2.resize(frame[sy:sy + ch, sx:sx + cw], (tw, th), interpolation=cv2.INTER_AREA)
        if segmenter is not None:
            out = segmenter.apply(out)  # blur/replace background behind the person
        if renderer is not None:
            out = renderer.draw(out, vt)
        try:
            ff.stdin.write(out.tobytes())
        except BrokenPipeError:
            break
        total += 1

    cap.release()
    ff.stdin.close()
    ff.wait()
    if ff.returncode != 0:
        raise RuntimeError(f"ffmpeg reframe mux failed: {ff.stderr.read().decode()[-1200:]}")
    return {"frames": total, "width": tw, "height": th}


def load_reframe(video_id, out_dir) -> dict:
    """Face-track trajectory (shared with the live preview); compute if missing.

    Keyed by SOURCE time, so the same trajectory serves the full edit or any
    sub-range clip (batch export) without recomputation.
    """
    reframe_path = out_dir / "reframe.json"
    if not reframe_path.exists():
        run_reframe(video_id)
    return json.loads(reframe_path.read_text())


def render_vertical_clip(video, words, segments, settings, centers, intermediate, final) -> dict:
    """Render one set of EDL segments to a vertical short (reframe + captions).

    Shared by single-clip (run_vertical_export) and batch (run_export_batch)
    export so both produce identical output for the same inputs.
    """
    has_audio = bool(video["audio_codec"])
    kept = ordered_intervals(segments)
    if not kept:
        raise RuntimeError("EDL is empty; nothing to export.")

    aspect = settings.get("aspect", "9:16")
    framing = settings.get("framing", "auto")
    crop_cx = float(settings.get("crop_cx", 0.5))
    crop_cy = float(settings.get("crop_cy", 0.5))
    enhance_audio = bool(settings.get("enhance_audio"))
    bg = settings.get("background") or {}
    style = resolve_caption_style(settings.get("caption"))
    tw, th = target_dims(aspect)

    # 1. edit -> horizontal intermediate (audio cleanup applied here if enabled)
    render_segments(video["stored_path"], kept, has_audio, str(intermediate), enhance_audio=enhance_audio)

    # 2. captions on the edited timeline
    projected = project_words(segments, words)
    renderer = CaptionRenderer(projected, width=tw, height=th, style=style) if projected else None

    # Background effect (blur / colour) via selfie segmentation, if enabled.
    segmenter = None
    if bg.get("mode") in ("blur", "color"):
        from backend.segment import BackgroundSegmenter
        segmenter = BackgroundSegmenter(mode=bg["mode"], color=bg.get("color", "#10121a"))

    # 3. crop (aspect + trajectory/manual) + background + caption + mux
    try:
        _reframe_and_caption(str(intermediate), str(final), renderer, centers, segments,
                             aspect, framing, crop_cx, crop_cy, segmenter=segmenter)
    finally:
        if segmenter is not None:
            segmenter.close()
    intermediate.unlink(missing_ok=True)

    return {
        "output_path": str(final),
        "width": tw,
        "height": th,
        "aspect": aspect,
        "duration": round(_probe_duration(str(final)), 3),
        "num_caption_words": len(projected),
    }


def run_vertical_export(job) -> dict:
    video_id = job["video_id"]

    video = db.get_video(video_id)
    if video is None:
        raise RuntimeError(f"video {video_id} not found")
    tr = db.get_transcript(video_id)
    if tr is None:
        raise RuntimeError("transcript required for captions")

    edit = db.get_edit(video_id)
    segments = json.loads(edit["edl_json"]) if edit else [
        {"id": "full", "sourceStart": 0.0, "sourceEnd": video["duration_seconds"]}
    ]

    out_dir = config.EXPORTS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    intermediate = out_dir / f"{job['id']}_edit.mp4"
    final = out_dir / f"{job['id']}_vertical.mp4"

    srow = db.get_settings(video_id)
    settings = json.loads(srow["json"]) if srow else DEFAULT_SETTINGS
    rf = load_reframe(video_id, out_dir)
    words = json.loads(tr["words_json"])

    result = render_vertical_clip(video, words, segments, settings, rf.get("centers", []), intermediate, final)
    result["face_tracked"] = rf.get("tracked", False) and settings.get("framing", "auto") == "auto"
    result["face_rate"] = rf.get("face_rate", 0.0)
    return result
