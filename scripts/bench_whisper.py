"""Benchmark faster-whisper config (cpu_threads x compute_type) on a real audio
slice, to find a usable speed for large-v3 on Apple Silicon CPU.

Measures transcription wall time (excluding one-time model load) and reports the
realtime factor = transcribe_seconds / audio_seconds. Lower is better.

Usage: ./.venv/bin/python scripts/bench_whisper.py /tmp/jlpt_30s.wav
"""
import sys
import time

from faster_whisper import WhisperModel

AUDIO = sys.argv[1]
MODEL = "large-v3"

# (compute_type, cpu_threads) combinations to try.
CONFIGS = [
    ("int8", 4),          # ~ current default behaviour
    ("int8", 8),
    ("int8_float32", 8),
    ("float32", 8),
    ("float32", 4),
]


def audio_duration(path: str) -> float:
    import wave

    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


def run(compute_type: str, threads: int, dur: float):
    t0 = time.time()
    model = WhisperModel(MODEL, device="cpu", compute_type=compute_type, cpu_threads=threads)
    load_s = time.time() - t0

    t1 = time.time()
    segments, info = model.transcribe(
        AUDIO, word_timestamps=True, vad_filter=True, beam_size=5
    )
    words = 0
    text_head = ""
    for seg in segments:  # generator -> force full work
        if seg.words:
            words += len(seg.words)
        if not text_head:
            text_head = seg.text.strip()[:60]
    transcribe_s = time.time() - t1
    rtf = transcribe_s / dur
    print(
        f"  compute={compute_type:13s} threads={threads}  "
        f"load={load_s:5.1f}s  transcribe={transcribe_s:6.1f}s  "
        f"RTF={rtf:4.2f}x  words={words}  | {text_head!r}"
    )
    return rtf


def main():
    dur = audio_duration(AUDIO)
    print(f"audio: {AUDIO}  duration={dur:.1f}s  model={MODEL}")
    print("(RTF = transcribe_time / audio_time; <1.0 means faster than realtime)")
    results = []
    for ct, th in CONFIGS:
        try:
            rtf = run(ct, th, dur)
            results.append((rtf, ct, th))
        except Exception as e:
            print(f"  compute={ct} threads={th}  FAILED: {e}")
    if results:
        results.sort()
        best = results[0]
        print(f"\nBEST: compute={best[1]} threads={best[2]}  RTF={best[0]:.2f}x")


if __name__ == "__main__":
    main()
