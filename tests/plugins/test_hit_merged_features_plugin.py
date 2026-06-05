import numpy as np
import pytest

from tests.utils import DummyContext, make_records
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import (
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
)
from waveform_analysis.core.plugins.builtin.cpu.hit_merged_features import (
    HIT_MERGED_FEATURES_DTYPE,
    HitMergedFeaturesPlugin,
    _polarity_sign_array,
)


def _make_hit(*, record_id, board=0, channel=0, edge_start=2, edge_end=5, dt=2, timestamp=0):
    arr = np.zeros(1, dtype=THRESHOLD_HIT_DTYPE)
    position = (edge_start + edge_end - 1) // 2
    arr[0]["position"] = position
    arr[0]["edge_start"] = edge_start
    arr[0]["edge_end"] = edge_end
    arr[0]["width"] = edge_end - edge_start
    arr[0]["dt"] = dt
    arr[0]["timestamp"] = timestamp + position * dt * 1000
    arr[0]["board"] = board
    arr[0]["channel"] = channel
    arr[0]["record_id"] = record_id
    return arr[0]


def _make_merged(
    *,
    record_id,
    board=0,
    channel=0,
    sample_start=2,
    sample_end=5,
    component_offset=0,
    component_count=1,
    dt=2,
    timestamp=0,
):
    arr = np.zeros(1, dtype=HIT_MERGED_DTYPE)
    position = max(sample_start, 0)
    if sample_end > sample_start:
        position = (sample_start + sample_end - 1) // 2
    arr[0]["position"] = position
    arr[0]["sample_start"] = sample_start
    arr[0]["sample_end"] = sample_end
    arr[0]["width"] = sample_end - sample_start if sample_end > sample_start else -1
    arr[0]["dt"] = dt
    arr[0]["timestamp"] = timestamp + position * dt * 1000
    arr[0]["board"] = board
    arr[0]["channel"] = channel
    arr[0]["record_id"] = record_id
    arr[0]["component_offset"] = component_offset
    arr[0]["component_count"] = component_count
    return arr[0]


def _components(pairs):
    out = np.zeros(len(pairs), dtype=HIT_MERGED_COMPONENTS_DTYPE)
    for i, (merged_index, hit_index) in enumerate(pairs):
        out[i]["merged_index"] = merged_index
        out[i]["hit_index"] = hit_index
    return out


def _context(merged, components, hits, wave_pool, *, filtered_pool=None):
    records = make_records(
        n_records=max(len(wave_pool) // 10, 1), event_length=10, baseline=100.0, dt=2
    )
    records["polarity"] = "negative"
    records["timestamp"] = 0
    data = {
        "hit_merged": merged,
        "hit_merged_components": components,
        "hit_threshold": hits,
        "records": records,
        "wave_pool": wave_pool,
    }
    if filtered_pool is not None:
        data["wave_pool_filtered"] = filtered_pool
    return DummyContext({"wave_source": "records", "use_filtered": filtered_pool is not None}, data)


def test_hit_merged_features_empty_input_returns_dtype():
    ctx = _context(
        np.zeros(0, dtype=HIT_MERGED_DTYPE),
        np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE),
        np.zeros(0, dtype=THRESHOLD_HIT_DTYPE),
        np.full(10, 100, dtype=np.uint16),
    )

    out = HitMergedFeaturesPlugin().compute(ctx, "run_001")

    assert out.dtype == HIT_MERGED_FEATURES_DTYPE
    assert len(out) == 0


def test_hit_merged_features_single_merged_hit_direct_window():
    hit = _make_hit(record_id=0, edge_start=2, edge_end=5)
    merged = np.array(
        [_make_merged(record_id=0, sample_start=2, sample_end=5)], dtype=HIT_MERGED_DTYPE
    )
    wave_pool = np.array([100, 100, 90, 70, 80, 100, 100, 100, 100, 100], dtype=np.uint16)
    ctx = _context(
        merged, _components([(0, 0)]), np.array([hit], dtype=THRESHOLD_HIT_DTYPE), wave_pool
    )

    out = HitMergedFeaturesPlugin().compute(ctx, "run_001")

    assert len(out) == 1
    row = out[0]
    assert int(row["merged_index"]) == 0
    assert int(row["time_start"]) == 4000
    assert int(row["time_end"]) == 10000
    assert int(row["max_time"]) == 6000
    assert float(row["area"]) == 60.0
    assert float(row["height"]) == 30.0
    assert float(row["width"]) == 6.0
    assert int(row["n_hits"]) == 1
    assert int(row["valid"]) == 1


def test_hit_merged_features_direct_merged_window_covers_full_window_for_multiple_hits():
    hits = np.array(
        [
            _make_hit(record_id=0, edge_start=2, edge_end=4),
            _make_hit(record_id=0, edge_start=6, edge_end=8),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    merged = np.array(
        [_make_merged(record_id=0, sample_start=2, sample_end=8, component_count=2)],
        dtype=HIT_MERGED_DTYPE,
    )
    wave_pool = np.array([100, 100, 90, 90, 100, 100, 80, 80, 100, 100], dtype=np.uint16)
    ctx = _context(merged, _components([(0, 0), (0, 1)]), hits, wave_pool)

    out = HitMergedFeaturesPlugin().compute(ctx, "run_001")

    assert len(out) == 1
    assert float(out[0]["area"]) == 60.0
    assert float(out[0]["height"]) == 20.0
    assert int(out[0]["n_hits"]) == 2


def test_hit_merged_features_positive_polarity_direct_window():
    hit = _make_hit(record_id=0, edge_start=2, edge_end=5)
    merged = np.array(
        [_make_merged(record_id=0, sample_start=2, sample_end=5)], dtype=HIT_MERGED_DTYPE
    )
    wave_pool = np.array([100, 100, 110, 130, 120, 100, 100, 100, 100, 100], dtype=np.uint16)
    ctx = _context(
        merged, _components([(0, 0)]), np.array([hit], dtype=THRESHOLD_HIT_DTYPE), wave_pool
    )
    ctx._data["records"]["polarity"] = "positive"

    out = HitMergedFeaturesPlugin().compute(ctx, "run_001")

    assert float(out[0]["area"]) == 60.0
    assert float(out[0]["height"]) == 30.0
    assert int(out[0]["max_time"]) == 6000


def test_hit_merged_features_polarity_sign_array_vectorized_string_dtypes():
    unicode_records = make_records(n_records=3)
    unicode_records["polarity"] = ["negative", "positive", "unknown"]

    byte_records = unicode_records.astype(
        [
            (name, "S8" if name == "polarity" else unicode_records.dtype[name])
            for name in unicode_records.dtype.names
        ]
    )

    np.testing.assert_array_equal(
        _polarity_sign_array(unicode_records),
        np.array([-1.0, 1.0, -1.0], dtype=np.float32),
    )
    np.testing.assert_array_equal(
        _polarity_sign_array(byte_records),
        np.array([-1.0, 1.0, -1.0], dtype=np.float32),
    )


def test_hit_merged_features_fallback_for_invalid_cross_record_window():
    hits = np.array(
        [
            _make_hit(record_id=0, edge_start=2, edge_end=4),
            _make_hit(record_id=1, edge_start=3, edge_end=5),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    merged = np.array(
        [_make_merged(record_id=0, sample_start=-1, sample_end=-1, component_count=2)],
        dtype=HIT_MERGED_DTYPE,
    )
    wave_pool = np.array(
        [
            100,
            100,
            80,
            80,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            70,
            70,
            100,
            100,
            100,
            100,
            100,
        ],
        dtype=np.uint16,
    )
    ctx = _context(merged, _components([(0, 0), (0, 1)]), hits, wave_pool)

    out = HitMergedFeaturesPlugin().compute(ctx, "run_001")

    assert len(out) == 1
    assert float(out[0]["area"]) == 100.0
    assert float(out[0]["height"]) == 30.0
    assert int(out[0]["n_hits"]) == 2
    assert int(out[0]["valid"]) == 1


def test_hit_merged_features_use_filtered_reads_filtered_wave_pool():
    hit = _make_hit(record_id=0, edge_start=2, edge_end=4)
    merged = np.array(
        [_make_merged(record_id=0, sample_start=2, sample_end=4)], dtype=HIT_MERGED_DTYPE
    )
    raw_pool = np.array([100, 100, 90, 90, 100, 100, 100, 100, 100, 100], dtype=np.uint16)
    filtered_pool = np.array([100, 100, 80, 80, 100, 100, 100, 100, 100, 100], dtype=np.uint16)
    ctx = _context(
        merged,
        _components([(0, 0)]),
        np.array([hit], dtype=THRESHOLD_HIT_DTYPE),
        raw_pool,
        filtered_pool=filtered_pool,
    )

    out = HitMergedFeaturesPlugin().compute(ctx, "run_001")

    assert float(out[0]["area"]) == 40.0


def test_hit_merged_features_raises_when_record_missing():
    hit = _make_hit(record_id=2, edge_start=2, edge_end=4)
    merged = np.array(
        [_make_merged(record_id=2, sample_start=2, sample_end=4)], dtype=HIT_MERGED_DTYPE
    )
    ctx = _context(
        merged,
        _components([(0, 0)]),
        np.array([hit], dtype=THRESHOLD_HIT_DTYPE),
        np.full(10, 100, dtype=np.uint16),
    )

    with pytest.raises(ValueError, match="record_id=2"):
        HitMergedFeaturesPlugin().compute(ctx, "run_001")
