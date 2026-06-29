"""Central configuration: filesystem paths for Clippy.

Everything is derived from the project root so the same code runs unchanged on
a dev laptop or a server. No values are hard-coded to a user's home directory.
"""
from __future__ import annotations

import os
from pathlib import Path

# Project root = the directory that contains the `backend/` and `worker/` packages.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Allow overriding the data directory via env (useful when deployed to a server).
DATA_DIR = Path(os.environ.get("CLIPFORGE_DATA_DIR", PROJECT_ROOT / "data"))

# Where users can drop a file by hand during dev (delivery option "a").
INPUT_DIR = DATA_DIR / "input"
# Where the upload endpoint persists received files.
UPLOADS_DIR = DATA_DIR / "uploads"
# Where edited / rendered outputs are written.
EXPORTS_DIR = DATA_DIR / "exports"
# Local ML model assets (e.g. the mediapipe face detector).
MODELS_DIR = DATA_DIR / "models"
FACE_MODEL_PATH = MODELS_DIR / "blaze_face_short_range.tflite"
# Selfie segmentation model for background removal/blur (mediapipe Tasks API).
SEGMENT_MODEL_PATH = MODELS_DIR / "selfie_segmenter.tflite"
# SQLite database file.
DB_DIR = DATA_DIR / "db"
DB_PATH = Path(os.environ.get("CLIPFORGE_DB_PATH", DB_DIR / "clipforge.db"))


def ensure_dirs() -> None:
    """Create all data directories if they do not yet exist."""
    for d in (INPUT_DIR, UPLOADS_DIR, EXPORTS_DIR, DB_DIR):
        d.mkdir(parents=True, exist_ok=True)
