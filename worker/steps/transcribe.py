"""Transcribe a real video with faster-whisper, producing WORD-LEVEL timestamps.

This is genuine speech-to-text on the actual uploaded file. No text is ever
fabricated: if the model produces nothing, we store an empty transcript and the
caller can see that, rather than inventing words.

Model: large-v3 (configurable via CLIPFORGE_WHISPER_MODEL). Runs on CPU with
int8 compute (Apple Silicon has no CT2 GPU path). The model is loaded once per
worker process and cached, so repeated transcribe jobs do not reload weights.

faster-whisper decodes the audio track directly from the mp4 via PyAV, so no
separate audio-extraction step is needed.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from backend import db

# Default model. large-v3 gives the best accuracy (incl. non-English); ~3 GB.
DEFAULT_MODEL = os.environ.get("CLIPFORGE_WHISPER_MODEL", "large-v3")

# Benchmarked on Apple M3 (see scripts/bench_whisper.py): int8 is the fastest
# compute type on this CPU (faster than float32), and using all logical cores
# beats the default. These are the measured-best defaults, both overridable.
DEFAULT_COMPUTE_TYPE = os.environ.get("CLIPFORGE_WHISPER_COMPUTE", "int8")
DEFAULT_CPU_THREADS = int(
    os.environ.get("CLIPFORGE_WHISPER_THREADS", str(os.cpu_count() or 8))
)

# Lazy, process-wide singleton so we load the weights at most once per worker.
_model = None
_model_name: Optional[str] = None


def _get_model():
    global _model, _model_name
    if _model is None:
        from faster_whisper import WhisperModel

        _model_name = DEFAULT_MODEL
        print(
            f"[transcribe] loading whisper model '{_model_name}' "
            f"(cpu/{DEFAULT_COMPUTE_TYPE}/{DEFAULT_CPU_THREADS} threads)..."
        )
        _model = WhisperModel(
            _model_name,
            device="cpu",
            compute_type=DEFAULT_COMPUTE_TYPE,
            cpu_threads=DEFAULT_CPU_THREADS,
        )
        print("[transcribe] model loaded.")
    return _model


def run_transcribe(video_id: str, job_id: str | None = None) -> dict:
    video = db.get_video(video_id)
    if video is None:
        raise RuntimeError(f"video {video_id} not found")

    stored_path = video["stored_path"]
    model = _get_model()

    # word_timestamps=True is the whole point: we need per-word start/end.
    # vad_filter trims long silences, which reduces hallucinated text and keeps
    # timestamps tight. Language is auto-detected and surfaced for verification.
    segments_iter, info = model.transcribe(
        stored_path,
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
    )

    words: list[dict] = []
    segments: list[dict] = []
    duration = info.duration or 0.0

    for seg in segments_iter:
        # Report progress (last segment end / audio duration) so the UI can show
        # a bar — faster-whisper yields segments lazily as it decodes.
        if job_id and duration > 0:
            db.update_job_progress(job_id, min(0.99, seg.end / duration))
        word_start_idx = len(words)
        if seg.words:
            for w in seg.words:
                words.append(
                    {
                        "i": len(words),
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "prob": w.probability,
                    }
                )
        word_end_idx = len(words)  # exclusive
        segments.append(
            {
                "id": seg.id,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "word_start": word_start_idx,
                "word_end": word_end_idx,
            }
        )

    db.save_transcript(
        video_id,
        language=info.language,
        language_probability=info.language_probability,
        model=_model_name or DEFAULT_MODEL,
        duration_seconds=info.duration,
        words_json=json.dumps(words),
        segments_json=json.dumps(segments),
    )

    return {
        "language": info.language,
        "language_probability": info.language_probability,
        "model": _model_name or DEFAULT_MODEL,
        "duration_seconds": info.duration,
        "num_segments": len(segments),
        "num_words": len(words),
    }
