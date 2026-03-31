import numpy as np

from tests.utils import DummyContext, FakeContext
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import (
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
    HitMergedComponentsPlugin,
    HitMergePlugin,
)


def _make_hit(
    position,
    height,
    integral,
    edge_start,
    edge_end,
    timestamp,
    channel,
    record_id,
    dt=2,
    record_sample_start=None,
    record_sample_end=None,
    wave_pool_start=None,
    wave_pool_end=None,
):
    arr = np.zeros(1, dtype=THRESHOLD_HIT_DTYPE)
    arr[0]["position"] = position
    arr[0]["height"] = height
    arr[0]["integral"] = integral
    arr[0]["edge_start"] = edge_start
    arr[0]["edge_end"] = edge_end
    arr[0]["width"] = edge_end - edge_start
    arr[0]["dt"] = dt
    arr[0]["timestamp"] = timestamp
    arr[0]["channel"] = channel
    arr[0]["record_id"] = record_id
    arr[0]["record_sample_start"] = (
        int(edge_start) if record_sample_start is None else record_sample_start
    )
    arr[0]["record_sample_end"] = int(edge_end) if record_sample_end is None else record_sample_end
    arr[0]["wave_pool_start"] = int(edge_start) if wave_pool_start is None else wave_pool_start
    arr[0]["wave_pool_end"] = int(edge_end) if wave_pool_end is None else wave_pool_end
    return arr[0]


def test_hit_merge_dtype_and_empty():
    plugin = HitMergePlugin()
    ctx = DummyContext(
        {"merge_gap_ns": 50.0},
        {"hit_threshold": np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)},
    )

    out = plugin.compute(ctx, "run_001")

    assert out.dtype == HIT_MERGED_DTYPE
    assert len(out) == 0


def test_hit_merge_same_channel_across_records_marks_direct_window_invalid():
    plugin = HitMergePlugin()

    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0, wave_pool_start=8, wave_pool_end=12)
    h2 = _make_hit(
        14, 25.0, 40.0, 13.0, 16.0, 108_000, 0, 1, wave_pool_start=113, wave_pool_end=116
    )
    h1["rise_time"] = 2.0
    h1["fall_time"] = 3.0
    h2["rise_time"] = 6.0
    h2["fall_time"] = 8.0
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)

    ctx = DummyContext(
        {
            "merge_gap_ns": 3.0,
            "max_total_width_ns": 10000.0,
            "dt": 2,
        },
        {"hit_threshold": hits},
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 1
    assert int(out[0]["record_id"]) == 1
    assert int(out[0]["position"]) == 14
    assert float(out[0]["height"]) == 25.0
    assert abs(float(out[0]["integral"]) - 70.0) < 1e-6
    assert float(out[0]["width"]) == 8.0
    assert int(out[0]["dt"]) == 2
    assert float(out[0]["rise_time"]) == float(h2["rise_time"])
    assert float(out[0]["fall_time"]) == float(h2["fall_time"])
    assert int(out[0]["component_offset"]) == 0
    assert int(out[0]["component_count"]) == 2
    assert int(out[0]["record_sample_start"]) == -1
    assert int(out[0]["record_sample_end"]) == -1
    assert int(out[0]["wave_pool_start"]) == -1
    assert int(out[0]["wave_pool_end"]) == -1


def test_hit_merge_single_record_merges_direct_wave_pool_window():
    plugin = HitMergePlugin()
    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 7, wave_pool_start=108, wave_pool_end=112)
    h2 = _make_hit(
        14, 25.0, 40.0, 13.0, 16.0, 108_000, 0, 7, wave_pool_start=113, wave_pool_end=116
    )
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)

    ctx = DummyContext(
        {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2}, {"hit_threshold": hits}
    )
    out = plugin.compute(ctx, "run_001")

    assert len(out) == 1
    assert int(out[0]["component_count"]) == 2
    assert int(out[0]["record_id"]) == 7
    assert int(out[0]["record_sample_start"]) == 8
    assert int(out[0]["record_sample_end"]) == 16
    assert int(out[0]["wave_pool_start"]) == 108
    assert int(out[0]["wave_pool_end"]) == 116


def test_hit_merge_not_across_channels():
    plugin = HitMergePlugin()

    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0)
    h2 = _make_hit(11, 22.0, 31.0, 9.0, 13.0, 101_000, 1, 1)
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)

    ctx = DummyContext(
        {
            "merge_gap_ns": 100.0,
            "max_total_width_ns": 10000.0,
            "dt": 2,
        },
        {"hit_threshold": hits},
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 2


def test_hit_merge_gap_exceeds_threshold():
    plugin = HitMergePlugin()

    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0)
    h2 = _make_hit(10, 22.0, 31.0, 8.0, 12.0, 200_000, 0, 1)
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)

    ctx = DummyContext(
        {
            "merge_gap_ns": 5.0,
            "max_total_width_ns": 10000.0,
            "dt": 2,
        },
        {"hit_threshold": hits},
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 2


def test_hit_merge_respects_max_total_width():
    plugin = HitMergePlugin()

    h1 = _make_hit(10, 10.0, 5.0, 9.0, 11.0, 100_000, 0, 0)
    h2 = _make_hit(14, 12.0, 6.0, 13.0, 15.0, 106_000, 0, 1)
    h3 = _make_hit(18, 14.0, 7.0, 17.0, 19.0, 112_000, 0, 2)
    hits = np.array([h1, h2, h3], dtype=THRESHOLD_HIT_DTYPE)

    ctx = DummyContext(
        {
            "merge_gap_ns": 10.0,
            "max_total_width_ns": 12.0,
            "dt": 2,
        },
        {"hit_threshold": hits},
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 2


def test_hit_merge_disabled_when_gap_non_positive():
    plugin = HitMergePlugin()

    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0)
    h2 = _make_hit(14, 25.0, 40.0, 13.0, 16.0, 110_000, 0, 1)
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)

    ctx = DummyContext(
        {
            "merge_gap_ns": 0.0,
            "max_total_width_ns": 10000.0,
            "dt": 2,
        },
        {"hit_threshold": hits},
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 2
    np.testing.assert_array_equal(out["position"], hits["position"])
    np.testing.assert_array_equal(out["wave_pool_start"], hits["wave_pool_start"])
    np.testing.assert_array_equal(out["wave_pool_end"], hits["wave_pool_end"])
    np.testing.assert_array_equal(out["component_count"], np.ones(2, dtype=np.int32))


def test_hit_merge_does_not_merge_different_dt_values():
    plugin = HitMergePlugin()

    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0, dt=2)
    h2 = _make_hit(14, 25.0, 40.0, 13.0, 16.0, 108_000, 0, 1, dt=4)
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)

    ctx = DummyContext(
        {"merge_gap_ns": 10.0, "max_total_width_ns": 10000.0}, {"hit_threshold": hits}
    )
    out = plugin.compute(ctx, "run_001")

    assert len(out) == 2


def test_hit_merged_components_returns_flat_component_rows():
    merge_plugin = HitMergePlugin()
    components_plugin = HitMergedComponentsPlugin()
    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0)
    h2 = _make_hit(14, 25.0, 40.0, 13.0, 16.0, 108_000, 0, 1)
    h3 = _make_hit(10, 22.0, 31.0, 8.0, 12.0, 200_000, 0, 2)
    hits = np.array([h1, h2, h3], dtype=THRESHOLD_HIT_DTYPE)

    base_ctx = DummyContext(
        {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2}, {"hit_threshold": hits}
    )
    merged = merge_plugin.compute(base_ctx, "run_001")

    ctx = FakeContext(
        {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2},
        {"hit_threshold": hits, "hit_merged": merged},
        plugins={"hit_merged": merge_plugin},
    )
    out = components_plugin.compute(ctx, "run_001")

    assert out.dtype == HIT_MERGED_COMPONENTS_DTYPE
    np.testing.assert_array_equal(out["merged_index"], np.array([0, 0, 1], dtype=np.int64))
    np.testing.assert_array_equal(out["hit_index"], np.array([0, 1, 2], dtype=np.int64))
