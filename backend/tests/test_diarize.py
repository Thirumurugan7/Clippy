import numpy as np

from backend.diarize import (
    mfcc, segment_embedding, cluster_speakers, diarize_segments,
    _relabel_by_first_appearance, SR, N_MFCC,
)


def _tone(freqs, dur=1.0, sr=SR):
    """A stack of sine partials — a crude but stable 'voice' with a fixed timbre."""
    t = np.linspace(0, dur, int(dur * sr), endpoint=False)
    sig = sum(np.sin(2 * np.pi * f * t) for f in freqs)
    return (sig / len(freqs)).astype(np.float32)


def test_mfcc_shape_and_finite():
    m = mfcc(_tone([150, 300, 450], dur=0.5))
    assert m.ndim == 2 and m.shape[1] == N_MFCC
    assert m.shape[0] > 10  # ~0.5s at 10ms hop
    assert np.isfinite(m).all()


def test_mfcc_too_short_is_empty():
    assert mfcc(np.zeros(10, dtype=np.float32)).shape == (0, N_MFCC)


def test_segment_embedding_is_fixed_length():
    sig = _tone([150, 300], dur=1.0)
    e = segment_embedding(sig, 0.0, 1.0)
    assert e.shape == (N_MFCC * 2,)
    # Different timbres give different embeddings.
    other = segment_embedding(_tone([400, 800], dur=1.0), 0.0, 1.0)
    assert np.linalg.norm(e - other) > 0


def test_cluster_single_embedding():
    assert cluster_speakers(np.zeros((1, N_MFCC * 2), dtype=np.float32)).tolist() == [0]


def test_cluster_separates_two_distinct_voices():
    # Two very different timbres, three turns each, interleaved.
    a = [segment_embedding(_tone([120, 240, 360]), 0, 1) for _ in range(3)]
    b = [segment_embedding(_tone([500, 1000, 1500]), 0, 1) for _ in range(3)]
    embs = np.stack([a[0], b[0], a[1], b[1], a[2], b[2]])
    labels = cluster_speakers(embs, max_speakers=4)
    assert len(set(labels)) == 2
    # Same voice -> same label; the two voices differ.
    assert labels[0] == labels[2] == labels[4]
    assert labels[1] == labels[3] == labels[5]
    assert labels[0] != labels[1]


def test_cluster_keeps_one_voice_together():
    # Six turns of the *same* timbre must not be over-split into many speakers.
    embs = np.stack([segment_embedding(_tone([200, 400, 600]), 0, 1) for _ in range(6)])
    labels = cluster_speakers(embs, max_speakers=4)
    assert len(set(labels)) == 1


def test_relabel_by_first_appearance():
    out = _relabel_by_first_appearance(np.array([2, 2, 0, 0, 1]))
    assert out.tolist() == [0, 0, 1, 1, 2]


def test_diarize_segments_no_audio_is_all_speaker_zero(tmp_path):
    # Nonexistent file -> extract fails -> everyone speaker 0 (never an error).
    segs = [{"start": 0.0, "end": 1.0}, {"start": 1.0, "end": 2.0}]
    assert diarize_segments(str(tmp_path / "nope.mp4"), segs) == [0, 0]


def test_diarize_segments_empty():
    assert diarize_segments("whatever.mp4", []) == []


def test_diarize_endpoint_labels_real_segments():
    # Real seeded short: run the endpoint end-to-end and confirm every segment
    # gets a non-negative speaker index persisted onto segments_json.
    import json
    from backend import db
    from backend.app import diarize_video, DiarizeBody

    with db.get_conn() as c:
        row = c.execute(
            "SELECT v.id FROM videos v JOIN transcripts t ON t.video_id=v.id "
            "WHERE v.original_filename LIKE 'sample_short%' "
            "ORDER BY v.created_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        import pytest
        pytest.skip("no seeded sample_short video")
    vid = row["id"]

    out = diarize_video(vid, DiarizeBody(max_speakers=3))
    assert out["ok"] is True
    assert out["num_speakers"] >= 1
    assert all("speaker" in s and s["speaker"] >= 0 for s in out["segments"])
    # persisted onto the transcript
    saved = json.loads(db.get_transcript(vid)["segments_json"])
    assert all("speaker" in s for s in saved)
