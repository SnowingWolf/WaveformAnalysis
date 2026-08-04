import numpy as np
import pytest

from tests.utils import DummyContext, make_hit, make_records
from waveform_analysis.core.plugins.builtin.hit_merged._compute import (
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
)
from waveform_analysis.core.plugins.builtin.hit_merged_features import (
    HIT_MERGED_FEATURES_DTYPE,
    HitMergedFeaturesPlugin,
)
from waveform_analysis.core.plugins.builtin.hit_merged_features.plugin import (
    _polarity_sign_array,
)
from waveform_analysis.core.plugins.builtin.hit_threshold import THRESHOLD_HIT_DTYPE


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


def _legacy_fallback_values(hits, records, wave_pool):
    """Reference the pre-0.5.0 fallback semantics for exact parity checks."""
    records_by_id = {int(record["record_id"]): record for record in records}
    time_start = None
    time_end = None
    area = 0.0
    height = 0.0
    max_time = None

    for hit in hits:
        start = int(hit["edge_start"])
        end = int(hit["edge_end"])
        if end <= start:
            raise ValueError("component hit has empty sample window")

        record = records_by_id[int(hit["record_id"])]
        clipped_start = max(0, start)
        clipped_end = min(int(record["event_length"]), end)
        if clipped_end <= clipped_start:
            raise ValueError("component hit has empty sample window after clipping")

        raw = wave_pool[
            int(record["wave_offset"]) + clipped_start : int(record["wave_offset"]) + clipped_end
        ].astype(np.float32, copy=False)
        signal = np.maximum(np.float32(record["baseline"]) - raw, 0.0)
        dt_ps = int(hit["dt"]) * 1000
        hit_start = int(hit["timestamp"]) + (start - int(hit["position"])) * dt_ps
        hit_end = int(hit["timestamp"]) + (end - int(hit["position"])) * dt_ps
        hit_max_time = hit_start + int(np.argmax(signal)) * dt_ps

        time_start = hit_start if time_start is None else min(time_start, hit_start)
        time_end = hit_end if time_end is None else max(time_end, hit_end)
        area += float(np.sum(signal))
        hit_height = float(signal[int(np.argmax(signal))])
        if hit_height > height or max_time is None:
            height = hit_height
            max_time = hit_max_time

    return time_start, time_end, area, height, max_time


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
    hit = make_hit(record_id=0, edge_start=2, edge_end=5)
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
            make_hit(record_id=0, edge_start=2, edge_end=4),
            make_hit(record_id=0, edge_start=6, edge_end=8),
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
    hit = make_hit(record_id=0, edge_start=2, edge_end=5)
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
            make_hit(record_id=0, edge_start=2, edge_end=4),
            make_hit(record_id=1, edge_start=3, edge_end=5),
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


def test_hit_merged_features_fallback_keeps_unclipped_time_edges():
    hit = make_hit(record_id=0, edge_start=-2, edge_end=2)
    merged = np.array(
        [_make_merged(record_id=0, sample_start=-1, sample_end=-1)], dtype=HIT_MERGED_DTYPE
    )
    wave_pool = np.array([80, 80, 100, 100, 100, 100, 100, 100, 100, 100], dtype=np.uint16)
    ctx = _context(
        merged, _components([(0, 0)]), np.array([hit], dtype=THRESHOLD_HIT_DTYPE), wave_pool
    )

    out = HitMergedFeaturesPlugin().compute(ctx, "run_001")

    assert int(out[0]["time_start"]) == -4000
    assert int(out[0]["time_end"]) == 4000
    assert int(out[0]["max_time"]) == -4000


def test_hit_merged_features_fallback_rejects_empty_component_window():
    hit = make_hit(record_id=0, edge_start=12, edge_end=13)
    merged = np.array(
        [_make_merged(record_id=0, sample_start=-1, sample_end=-1)], dtype=HIT_MERGED_DTYPE
    )
    ctx = _context(
        merged,
        _components([(0, 0)]),
        np.array([hit], dtype=THRESHOLD_HIT_DTYPE),
        np.full(10, 100, dtype=np.uint16),
    )

    with pytest.raises(ValueError, match="empty sample window"):
        HitMergedFeaturesPlugin().compute(ctx, "run_001")


def test_hit_merged_features_fallback_rejects_misaligned_component_rows():
    hit = make_hit(record_id=0, edge_start=2, edge_end=4)
    merged = np.array(
        [_make_merged(record_id=0, sample_start=-1, sample_end=-1)], dtype=HIT_MERGED_DTYPE
    )
    ctx = _context(
        merged,
        _components([(1, 0)]),
        np.array([hit], dtype=THRESHOLD_HIT_DTYPE),
        np.full(10, 100, dtype=np.uint16),
    )

    with pytest.raises(ValueError, match="not aligned"):
        HitMergedFeaturesPlugin().compute(ctx, "run_001")


def test_hit_merged_features_use_filtered_reads_filtered_wave_pool():
    hit = make_hit(record_id=0, edge_start=2, edge_end=4)
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
    hit = make_hit(record_id=2, edge_start=2, edge_end=4)
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


def test_hit_merged_features_plugin_version_is_051():
    """Fallback validation and cache semantics require a PATCH lineage bump."""
    assert HitMergedFeaturesPlugin.version == "0.5.1"


def test_hit_merged_features_new_option_feature_num_threads():
    """线程数是运行时调优参数，不应改变缓存 lineage。"""
    plugin = HitMergedFeaturesPlugin()
    assert "feature_num_threads" in plugin.options
    opt = plugin.options["feature_num_threads"]
    assert opt.default is None
    assert opt.type is int
    assert opt.track is False


def test_hit_merged_features_thread_option_covers_fallback(monkeypatch):
    from waveform_analysis.core.plugins.builtin.hit_merged_features import plugin as module

    seen = {}

    def fake_fast(*_args):
        seen["fast"] = module.nb.get_num_threads()

    def fake_validate(*_args):
        return 0, -1, -1, 0, 0

    def fake_fallback(*_args):
        seen["fallback"] = module.nb.get_num_threads()

    monkeypatch.setattr(module, "_features_fast_kernel", fake_fast)
    monkeypatch.setattr(module, "_validate_fallback_components_kernel", fake_validate)
    monkeypatch.setattr(module, "_features_fallback_kernel", fake_fallback)

    hit = make_hit(record_id=0)
    merged = np.array(
        [_make_merged(record_id=0, sample_start=-1, sample_end=-1)], dtype=HIT_MERGED_DTYPE
    )
    ctx = _context(
        merged, _components([(0, 0)]), np.array([hit], dtype=THRESHOLD_HIT_DTYPE), np.full(10, 100)
    )

    HitMergedFeaturesPlugin()._compute_features(
        merged=merged,
        component_rows=ctx._data["hit_merged_components"],
        hits=ctx._data["hit_threshold"],
        records=ctx._data["records"],
        wave_pool=ctx._data["wave_pool"],
        num_threads=1,
    )

    assert seen == {"fast": 1, "fallback": 1}


def test_hit_merged_features_no_build_component_slices_function():
    """验证 _build_component_slices 已被移除"""
    from waveform_analysis.core.plugins.builtin.hit_merged_features import plugin as mod

    assert not hasattr(mod, "_build_component_slices"), "_build_component_slices should be removed"
    assert not hasattr(mod, "_record_lookup"), "_record_lookup should be removed"


def test_hit_merged_features_output_dtype_integrity():
    """Golden: 验证输出 dtype 完整且所有字段存在"""
    hit = make_hit(record_id=0, edge_start=2, edge_end=5)
    merged = np.array(
        [_make_merged(record_id=0, sample_start=2, sample_end=5)], dtype=HIT_MERGED_DTYPE
    )
    wave_pool = np.array([100, 100, 90, 70, 80, 100, 100, 100, 100, 100], dtype=np.uint16)
    ctx = _context(
        merged, _components([(0, 0)]), np.array([hit], dtype=THRESHOLD_HIT_DTYPE), wave_pool
    )

    out = HitMergedFeaturesPlugin().compute(ctx, "run_001")

    assert out.dtype == HIT_MERGED_FEATURES_DTYPE
    expected_fields = {
        "merged_index",
        "board",
        "channel",
        "record_id",
        "time_start",
        "time_end",
        "center_time",
        "max_time",
        "area",
        "height",
        "width",
        "rise_time",
        "fall_time",
        "n_hits",
        "valid",
        "area_pe",
        "height_pe",
    }
    actual_fields = set(out.dtype.names)
    assert expected_fields == actual_fields, f"Missing fields: {expected_fields - actual_fields}"


def test_hit_merged_features_fallback_matches_legacy_reference_exactly():
    rng = np.random.default_rng(7)
    hits = np.array(
        [make_hit(record_id=index, edge_start=0, edge_end=10) for index in range(100)],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    merged = np.array(
        [_make_merged(record_id=0, sample_start=-1, sample_end=-1, component_count=len(hits))],
        dtype=HIT_MERGED_DTYPE,
    )
    wave_pool = rng.integers(60, 121, size=1000, dtype=np.uint16)
    ctx = _context(merged, _components([(0, index) for index in range(len(hits))]), hits, wave_pool)
    ctx._data["records"]["baseline"] = 100.3

    out = HitMergedFeaturesPlugin().compute(ctx, "run_001")
    expected = _legacy_fallback_values(hits, ctx._data["records"], wave_pool)

    row = out[0]
    assert int(row["valid"]) == 1
    assert int(row["time_start"]) == expected[0]
    assert int(row["time_end"]) == expected[1]
    assert int(row["max_time"]) == expected[4]
    assert row["area"].tobytes() == np.float32(expected[2]).tobytes()
    assert row["height"].tobytes() == np.float32(expected[3]).tobytes()
    assert row["width"].tobytes() == np.float32((expected[1] - expected[0]) / 1000.0).tobytes()
    assert np.isnan(float(row["area_pe"]))
    assert np.isnan(float(row["height_pe"]))
