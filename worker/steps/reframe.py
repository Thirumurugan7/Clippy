"""Precompute the face-track crop trajectory for a video (mediapipe).

Samples the source at a few fps, records the main face's normalized horizontal
centre over time, and stores it as JSON. Both the live vertical preview (canvas,
in the browser) and the vertical export read this same trajectory, so the
preview is WYSIWYG and the export doesn't re-run detection.
"""
from __future__ import annotations

import json

import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

from backend import db, config

SAMPLE_FPS = 6.0


def run_reframe(video_id: str) -> dict:
    video = db.get_video(video_id)
    if video is None:
        raise RuntimeError(f"video {video_id} not found")

    cap = cv2.VideoCapture(video["stored_path"])
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps / SAMPLE_FPS))

    opts = vision.FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=str(config.FACE_MODEL_PATH)),
        running_mode=vision.RunningMode.IMAGE,
        min_detection_confidence=0.4,
    )
    detector = vision.FaceDetector.create_from_options(opts)

    centers = []  # {t, cx} with cx normalized 0..1 (None when no face)
    detected = 0
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = detector.detect(img)
            cx = None
            if res.detections:
                detected += 1
                b = max(res.detections, key=lambda d: d.bounding_box.width).bounding_box
                cx = (b.origin_x + b.width / 2.0) / W
            centers.append({"t": round(i / fps, 3), "cx": (round(cx, 4) if cx is not None else None)})
        i += 1
    cap.release()
    detector.close()

    face_rate = round(detected / max(1, len(centers)), 3)
    out_dir = config.EXPORTS_DIR / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reframe.json").write_text(json.dumps({
        "width": W, "height": H, "fps": fps,
        "face_rate": face_rate, "tracked": face_rate >= 0.15,
        "centers": centers,
    }))
    return {"samples": len(centers), "face_rate": face_rate, "tracked": face_rate >= 0.15}
