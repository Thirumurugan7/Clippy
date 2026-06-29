"""Background removal / blur via mediapipe selfie segmentation (Tasks API).

A `BackgroundSegmenter` is created once per export and reused across frames. For
each BGR frame it produces a person-probability mask, feathers it, and composites
the person over either a blurred copy of the frame or a solid colour. Local and
free — same offline pattern as the face detector (downloaded .tflite model).
"""
from __future__ import annotations

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision, BaseOptions

from backend import config


def _hex_to_bgr(h: str) -> tuple[int, int, int]:
    h = (h or "#000000").lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b, g, r)  # OpenCV is BGR


class BackgroundSegmenter:
    """mode: "blur" (defocus), "color" (flat colour), or "image" (a custom photo)."""

    def __init__(self, mode: str = "blur", color: str = "#10121a", image_path=None):
        self.mode = mode
        self.color = _hex_to_bgr(color)
        self._bg_src = None
        self._bg_cache = None
        if mode == "image" and image_path:
            img = cv2.imread(str(image_path))
            if img is not None:
                self._bg_src = img
        opts = vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=str(config.SEGMENT_MODEL_PATH)),
            running_mode=vision.RunningMode.IMAGE,
            output_confidence_masks=True,
        )
        self._seg = vision.ImageSegmenter.create_from_options(opts)

    def _alpha(self, frame_bgr) -> np.ndarray:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = self._seg.segment(img)
        # Selfie model: one confidence mask, foreground (person) probability 0..1.
        mask = res.confidence_masks[0].numpy_view()
        if mask.shape[:2] != frame_bgr.shape[:2]:
            mask = cv2.resize(mask, (frame_bgr.shape[1], frame_bgr.shape[0]))
        # Feather the edge so the composite isn't a hard cut-out.
        mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=2.0)
        return np.clip(mask, 0.0, 1.0)[:, :, None]

    def _bg_image(self, frame_bgr) -> np.ndarray:
        """The background photo, cover-fit (scale + centre-crop) to the frame."""
        h, w = frame_bgr.shape[:2]
        if self._bg_cache is not None and self._bg_cache.shape[:2] == (h, w):
            return self._bg_cache
        src = self._bg_src
        sh, sw = src.shape[:2]
        scale = max(w / sw, h / sh)
        nw, nh = max(w, int(sw * scale)), max(h, int(sh * scale))
        resized = cv2.resize(src, (nw, nh), interpolation=cv2.INTER_AREA)
        x, y = (nw - w) // 2, (nh - h) // 2
        self._bg_cache = resized[y:y + h, x:x + w].copy()
        return self._bg_cache

    def apply(self, frame_bgr) -> np.ndarray:
        alpha = self._alpha(frame_bgr)
        if self.mode == "image" and self._bg_src is not None:
            bg = self._bg_image(frame_bgr)
        elif self.mode == "color":
            bg = np.full_like(frame_bgr, self.color, dtype=np.uint8)
        else:  # blur
            k = max(31, (min(frame_bgr.shape[:2]) // 12) | 1)
            bg = cv2.GaussianBlur(frame_bgr, (k, k), 0)
        out = frame_bgr.astype(np.float32) * alpha + bg.astype(np.float32) * (1.0 - alpha)
        return out.astype(np.uint8)

    def close(self):
        self._seg.close()
