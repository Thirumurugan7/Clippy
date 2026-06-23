import pytest

from backend.edl import validate_edl, ordered_intervals


def test_validate_ok():
    segs = [
        {"id": "a", "sourceStart": 0, "sourceEnd": 2},
        {"id": "b", "sourceStart": 5, "sourceEnd": 7},
    ]
    assert validate_edl(segs, 10) == segs


def test_validate_rejects_out_of_bounds():
    with pytest.raises(ValueError):
        validate_edl([{"id": "a", "sourceStart": 0, "sourceEnd": 11}], 10)


def test_validate_rejects_inverted():
    with pytest.raises(ValueError):
        validate_edl([{"id": "a", "sourceStart": 5, "sourceEnd": 4}], 10)


def test_ordered_intervals_preserves_order():
    segs = [
        {"id": "b", "sourceStart": 5, "sourceEnd": 7},
        {"id": "a", "sourceStart": 0, "sourceEnd": 2},
    ]
    assert ordered_intervals(segs) == [(5.0, 7.0), (0.0, 2.0)]
