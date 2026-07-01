"""Local speaker diarization — label who is speaking, with no torch, no gated
models, and no downloads.

Deliberately lean to fit Clippy's stack (faster-whisper + mediapipe + onnxruntime,
all torch-free): per Whisper segment we compute a small MFCC embedding straight
from the audio in numpy, then cluster the segments into speakers. Neural speaker
embeddings would be more accurate, but they'd drag in torch/pyannote (a ~2 GB,
gated-model rabbit hole this project has been burned by). MFCC + clustering is the
classic, fully-offline front end and separates distinct voices well enough to
label a talking-head or a 2-3 person podcast.

Pipeline: ffmpeg -> 16 kHz mono wav -> per-segment MFCC mean/std embedding ->
L2-normalise -> pick a speaker count by silhouette (defaults to 1 unless there's
real separation) -> k-means labels. Robust to missing/short audio (everyone is
speaker 0 rather than an error).
"""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 16000            # diarization sample rate (speech-band is plenty at 16 kHz)
N_MFCC = 13
N_MELS = 26
FRAME = 0.025         # 25 ms analysis window
HOP = 0.010           # 10 ms hop
_EPS = 1e-10


# ---------------------------------------------------------------------------
# audio
# ---------------------------------------------------------------------------
def extract_audio(video_path: str, ffmpeg: str = "ffmpeg") -> np.ndarray:
    """Decode the file to 16 kHz mono float32 in [-1, 1]. Empty array if silent
    or audio-less (caller treats that as a single speaker)."""
    import shutil
    import tempfile

    exe = shutil.which(ffmpeg) or ffmpeg
    with tempfile.TemporaryDirectory() as td:
        wav = str(Path(td) / "a.wav")
        cmd = [exe, "-y", "-i", str(video_path), "-vn", "-ac", "1",
               "-ar", str(SR), "-f", "wav", wav]
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if proc.returncode != 0 or not Path(wav).exists():
            return np.zeros(0, dtype=np.float32)
        return _read_wav_mono(wav)


def _read_wav_mono(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        n, ch, sw = w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    if sw != 2:  # ffmpeg gives s16; be defensive anyway
        return np.zeros(0, dtype=np.float32)
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    return data


# ---------------------------------------------------------------------------
# MFCC (numpy)
# ---------------------------------------------------------------------------
def _mel_filterbank(n_mels: int, n_fft: int, sr: int) -> np.ndarray:
    def hz_to_mel(f):
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel_to_hz(m):
        return 700.0 * (10.0 ** (m / 2595.0) - 1.0)

    low, high = hz_to_mel(0.0), hz_to_mel(sr / 2.0)
    pts = mel_to_hz(np.linspace(low, high, n_mels + 2))
    bins = np.floor((n_fft + 1) * pts / sr).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for m in range(1, n_mels + 1):
        l, c, r = bins[m - 1], bins[m], bins[m + 1]
        for k in range(l, c):
            if c > l:
                fb[m - 1, k] = (k - l) / (c - l)
        for k in range(c, r):
            if r > c:
                fb[m - 1, k] = (r - k) / (r - c)
    return fb


def mfcc(signal: np.ndarray, sr: int = SR) -> np.ndarray:
    """Return (frames, N_MFCC) MFCCs. Empty (0, N_MFCC) if the signal is too short."""
    if signal.size < int(FRAME * sr):
        return np.zeros((0, N_MFCC), dtype=np.float32)
    signal = np.append(signal[0], signal[1:] - 0.97 * signal[:-1])  # pre-emphasis
    win = int(round(FRAME * sr))
    hop = int(round(HOP * sr))
    n_fft = 1 << (win - 1).bit_length()  # next pow2 >= win
    frames = 1 + (len(signal) - win) // hop
    if frames <= 0:
        return np.zeros((0, N_MFCC), dtype=np.float32)
    window = np.hamming(win).astype(np.float32)
    fb = _mel_filterbank(N_MELS, n_fft, sr)
    out = np.empty((frames, N_MFCC), dtype=np.float32)
    for i in range(frames):
        seg = signal[i * hop:i * hop + win] * window
        spec = np.abs(np.fft.rfft(seg, n=n_fft)) ** 2
        mel = np.log(fb @ spec + _EPS)
        cep = _dct2(mel)[:N_MFCC]
        out[i] = cep
    return out


def _dct2(x: np.ndarray) -> np.ndarray:
    n = x.shape[0]
    k = np.arange(n)
    basis = np.cos(np.pi / n * (k[:, None] + 0.5) * k[None, :])
    return basis @ x  # DCT-II (orthonormal scaling is irrelevant after normalising)


def segment_embedding(samples: np.ndarray, start: float, end: float, sr: int = SR) -> np.ndarray:
    """A fixed-length voice fingerprint for one time window: mean+std of its MFCC
    frames. Zeros if the window has no usable audio."""
    a, b = max(0, int(start * sr)), min(len(samples), int(end * sr))
    m = mfcc(samples[a:b], sr) if b > a else np.zeros((0, N_MFCC), dtype=np.float32)
    if m.shape[0] == 0:
        return np.zeros(N_MFCC * 2, dtype=np.float32)
    return np.concatenate([m.mean(axis=0), m.std(axis=0)]).astype(np.float32)


# ---------------------------------------------------------------------------
# clustering
# ---------------------------------------------------------------------------
def _l2norm(x: np.ndarray) -> np.ndarray:
    return x / (np.linalg.norm(x, axis=1, keepdims=True) + _EPS)


def _kmeans(x: np.ndarray, k: int, seed: int = 0, iters: int = 50):
    rng = np.random.default_rng(seed)
    # k-means++ init (deterministic given seed), robust to duplicate points.
    centers = [x[rng.integers(len(x))]]
    for _ in range(1, k):
        d = np.min([np.sum((x - c) ** 2, axis=1) for c in centers], axis=0)
        total = d.sum()
        if total <= _EPS:  # all remaining points coincide with a centre
            probs = np.full(len(x), 1.0 / len(x))
        else:
            probs = d / total
            probs /= probs.sum()  # guard against float drift (rng.choice is strict)
        centers.append(x[rng.choice(len(x), p=probs)])
    C = np.stack(centers)
    labels = np.zeros(len(x), dtype=int)
    for _ in range(iters):
        d = np.sum((x[:, None, :] - C[None, :, :]) ** 2, axis=2)
        new = d.argmin(axis=1)
        if np.array_equal(new, labels):
            break
        labels = new
        for j in range(k):
            pts = x[labels == j]
            if len(pts):
                C[j] = pts.mean(axis=0)
    return labels


def _silhouette(x: np.ndarray, labels: np.ndarray) -> float:
    uniq = np.unique(labels)
    if len(uniq) < 2:
        return -1.0
    D = np.sqrt(np.sum((x[:, None, :] - x[None, :, :]) ** 2, axis=2))
    scores = []
    for i in range(len(x)):
        same = labels == labels[i]
        same[i] = False
        a = D[i, same].mean() if same.any() else 0.0
        b = min(D[i, labels == c].mean() for c in uniq if c != labels[i])
        scores.append((b - a) / (max(a, b) + _EPS))
    return float(np.mean(scores))


def cluster_speakers(embeddings: np.ndarray, max_speakers: int = 4,
                     min_silhouette: float = 0.12) -> np.ndarray:
    """Assign a speaker index per embedding. Picks the speaker count by silhouette
    and stays at 1 unless there's genuine separation (avoids over-splitting one
    voice). `max_speakers` caps the search."""
    n = len(embeddings)
    if n <= 1:
        return np.zeros(n, dtype=int)
    x = _l2norm(np.asarray(embeddings, dtype=np.float32))
    best_labels = np.zeros(n, dtype=int)
    best_score = min_silhouette  # k=2+ must beat this to win over "one speaker"
    for k in range(2, min(max_speakers, n) + 1):
        labels = _kmeans(x, k)
        if len(np.unique(labels)) < k:
            continue
        s = _silhouette(x, labels)
        if s > best_score:
            best_score, best_labels = s, labels
    return _relabel_by_first_appearance(best_labels)


def _relabel_by_first_appearance(labels: np.ndarray) -> np.ndarray:
    """Speaker 0 is whoever talks first, 1 next, etc. — stable, readable labels."""
    remap, out = {}, np.empty_like(labels)
    for i, lb in enumerate(labels):
        if lb not in remap:
            remap[lb] = len(remap)
        out[i] = remap[lb]
    return out


# ---------------------------------------------------------------------------
# top-level
# ---------------------------------------------------------------------------
def diarize_segments(video_path: str, segments: list[dict], max_speakers: int = 4,
                     ffmpeg: str = "ffmpeg") -> list[int]:
    """Speaker index per transcript segment (same order as `segments`)."""
    if not segments:
        return []
    samples = extract_audio(video_path, ffmpeg=ffmpeg)
    if samples.size == 0:
        return [0] * len(segments)
    embs = np.stack([segment_embedding(samples, s["start"], s["end"]) for s in segments])
    if not np.any(embs):  # all-silent windows
        return [0] * len(segments)
    return cluster_speakers(embs, max_speakers=max_speakers).tolist()
