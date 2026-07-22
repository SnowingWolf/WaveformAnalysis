import numpy as np
import pytest

from tests.utils import DummyContext, make_records
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
    HIT_MERGED_DTYPE,
    HitMergedComponentsPlugin,
    HitMergePlugin,
)
from waveform_analysis.core.plugins.builtin.hit.hit_merged_features import HitMergedFeaturesPlugin
from waveform_analysis.core.plugins.builtin.peaks.peaklets import (
    PEAKLET_COMPONENTS_DTYPE,
    PEAKLET_DTYPE,
    PeakletComponentsPlugin,
    PeakletPlugin,
)


def _make_hit(*, record_id, board, channel, edge_start, edge_end, dt=2, timestamp=0):
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


def make_peaklet_context(hits, wave_pool, *, time_window_ns=4.0, use_filtered=False):
    merge_plugin = HitMergePlugin()
    components_plugin = HitMergedComponentsPlugin()
    merge_ctx = DummyContext(
        {"merge_gap_ns": 0.0, "max_total_width_ns": 10000.0, "dt": 2},
        {"hit_threshold": hits},
    )
    merged = merge_plugin.compute(merge_ctx, "run_001")
    component_ctx = DummyContext(
        {"merge_gap_ns": 0.0, "max_total_width_ns": 10000.0, "dt": 2},
        {"hit_threshold": hits, "hit_merged": merged},
    )
    component_ctx._plugins = {"hit_merged": merge_plugin}
    component_ctx.get_plugin = lambda name: component_ctx._plugins[name]
    components = components_plugin.compute(component_ctx, "run_001")

    records = make_records(n_records=len(hits), event_length=10, baseline=100.0, dt=2)
    records["board"] = hits["board"]
    records["channel"] = hits["channel"]
    records["timestamp"] = 0
    records["polarity"] = "negative"

    data = {
        "hit_threshold": hits,
        "hit_merged": merged,
        "hit_merged_components": components,
        "records": records,
        "wave_pool": wave_pool,
    }
    if use_filtered:
        data["wave_pool_filtered"] = wave_pool + 1

    feature_ctx = DummyContext(
        {
            "wave_source": "records",
            "use_filtered": False,
            "dt": 2,
        },
        data,
    )
    features = HitMergedFeaturesPlugin().compute(feature_ctx, "run_001")
    data["hit_merged_features"] = features

    peaklet_ctx = DummyContext(
        {
            "time_window_ns": time_window_ns,
            "max_total_width_ns": 10000.0,
            "dt": 2,
            "use_filtered": use_filtered,
        },
        data,
    )
    data["peaklet_components"] = PeakletComponentsPlugin().compute_array(peaklet_ctx, "run_001")
    return peaklet_ctx


def test_peaklets_cluster_cross_channel_hits_without_waveform_features():
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=3, edge_end=5),
            _make_hit(record_id=1, board=0, channel=1, edge_start=4, edge_end=6),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(20, 100, dtype=np.uint16))

    out = PeakletPlugin().compute_array(ctx, "run_001")

    assert out.dtype == PEAKLET_DTYPE
    assert out.dtype.names == (
        "time_start",
        "time_end",
        "center_time",
        "n_hits",
        "n_channels",
        "component_offset",
        "component_count",
    )
    assert len(out) == 1
    assert int(out[0]["time_start"]) == 6000
    assert int(out[0]["time_end"]) == 12000
    assert int(out[0]["center_time"]) == 9000
    assert int(out[0]["n_hits"]) == 2
    assert int(out[0]["n_channels"]) == 2
    assert int(out[0]["component_offset"]) == 0
    assert int(out[0]["component_count"]) == 2
    for removed in ("area", "height", "max_time", "width", "rise_time", "fall_time"):
        assert removed not in out.dtype.names


def test_peaklets_empty_input_returns_empty_lightweight_dtype():
    ctx = DummyContext({}, {"hit_merged": np.zeros(0, dtype=HIT_MERGED_DTYPE)})

    out = PeakletPlugin().compute_array(ctx, "run_001")

    assert out.dtype == PEAKLET_DTYPE
    assert len(out) == 0


def test_peaklets_split_when_cross_channel_gap_exceeds_window():
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=2),
            _make_hit(record_id=1, board=0, channel=1, edge_start=8, edge_end=9),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(20, 100, dtype=np.uint16), time_window_ns=1.0)

    out = PeakletPlugin().compute_array(ctx, "run_001")
    ctx._data["peaklets"] = out
    components = PeakletComponentsPlugin().compute_array(ctx, "run_001")

    assert len(out) == 2
    assert components.dtype == PEAKLET_COMPONENTS_DTYPE
    np.testing.assert_array_equal(components["peak_id"], np.array([0, 1], dtype=np.int64))
    np.testing.assert_array_equal(components["merged_index"], np.array([0, 1], dtype=np.int64))


def test_peaklet_components_use_peaklets_clustering_config():
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=2),
            _make_hit(record_id=1, board=0, channel=1, edge_start=8, edge_end=9),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(20, 100, dtype=np.uint16), time_window_ns=1.0)
    ctx.config = {
        **ctx.config,
        "peaklets": {"time_window_ns": 20.0, "max_total_width_ns": 10000.0},
    }
    peaklet_plugin = PeakletPlugin()
    ctx.get_plugin = lambda name: peaklet_plugin if name == "peaklets" else None

    components = PeakletComponentsPlugin().compute_array(ctx, "run_001")
    ctx._data["peaklet_components"] = components
    out = peaklet_plugin.compute_array(ctx, "run_001")
    ctx._data["peaklets"] = out

    assert len(out) == 1
    assert int(out[0]["component_count"]) == 2
    np.testing.assert_array_equal(components["peak_id"], np.array([0, 0], dtype=np.int64))
    np.testing.assert_array_equal(components["merged_index"], np.array([0, 1], dtype=np.int64))


def test_peaklet_components_compute_without_peaklets_dependency():
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=2),
            _make_hit(record_id=1, board=0, channel=1, edge_start=8, edge_end=9),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(20, 100, dtype=np.uint16), time_window_ns=1.0)
    ctx._data.pop("peaklets", None)

    components = PeakletComponentsPlugin().compute_array(ctx, "run_001")

    assert components.dtype == PEAKLET_COMPONENTS_DTYPE
    np.testing.assert_array_equal(components["peak_id"], np.array([0, 1], dtype=np.int64))
    np.testing.assert_array_equal(components["merged_index"], np.array([0, 1], dtype=np.int64))


def test_peaklets_consume_peaklet_components_without_reclustering(monkeypatch):
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=2),
            _make_hit(record_id=1, board=0, channel=1, edge_start=8, edge_end=9),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(20, 100, dtype=np.uint16), time_window_ns=1.0)
    components = PeakletComponentsPlugin().compute_array(ctx, "run_001")
    ctx._data["peaklet_components"] = components

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("peaklets should consume peaklet_components")

    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.peaks.peaklets._cluster_merged_hits",
        fail_if_called,
    )

    out = PeakletPlugin().compute_array(ctx, "run_001")

    assert len(out) == 2
    np.testing.assert_array_equal(out["component_offset"], np.array([0, 1], dtype=np.int64))
    np.testing.assert_array_equal(out["component_count"], np.array([1, 1], dtype=np.int32))


def test_peaklets_respect_max_total_width_window():
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=4),
            _make_hit(record_id=1, board=0, channel=1, edge_start=3, edge_end=8),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(20, 100, dtype=np.uint16), time_window_ns=10.0)
    ctx.config["max_total_width_ns"] = 8.0
    ctx._data["peaklet_components"] = PeakletComponentsPlugin().compute_array(ctx, "run_001")

    out = PeakletPlugin().compute_array(ctx, "run_001")

    assert len(out) == 2


def test_peaklet_components_flat_output_preserves_stable_time_order():
    merged = np.zeros(3, dtype=HIT_MERGED_DTYPE)
    merged["time_start"] = [1000, 1000, 5000]
    merged["time_end"] = [2000, 1500, 6000]
    ctx = DummyContext(
        {"time_window_ns": 0.0, "max_total_width_ns": 10000.0, "dt": 2},
        {"hit_merged": merged},
    )

    components = PeakletComponentsPlugin().compute_array(ctx, "run_001")

    assert components.dtype == PEAKLET_COMPONENTS_DTYPE
    np.testing.assert_array_equal(components["peak_id"], [0, 0, 1])
    np.testing.assert_array_equal(components["merged_index"], [0, 1, 2])


def test_peaklets_group_unordered_membership_and_deduplicate_board_channel():
    merged = np.zeros(4, dtype=HIT_MERGED_DTYPE)
    merged["time_start"] = [1000, 10000, 2000, 9000]
    merged["time_end"] = [3000, 12000, 4000, 13000]
    merged["board"] = [2, 3, 2, 3]
    merged["channel"] = [7, 9, 7, 10]
    merged["component_count"] = [2, 1, 3, 4]
    components = np.array([(1, 3), (0, 2), (0, 0), (1, 1)], dtype=PEAKLET_COMPONENTS_DTYPE)
    ctx = DummyContext({"dt": 2}, {"hit_merged": merged, "peaklet_components": components})

    peaklets = PeakletPlugin().compute_array(ctx, "run_001")

    assert peaklets.dtype == PEAKLET_DTYPE
    np.testing.assert_array_equal(peaklets["time_start"], [1000, 9000])
    np.testing.assert_array_equal(peaklets["time_end"], [4000, 13000])
    np.testing.assert_array_equal(peaklets["n_hits"], [5, 5])
    np.testing.assert_array_equal(peaklets["n_channels"], [1, 2])
    np.testing.assert_array_equal(peaklets["component_offset"], [0, 2])
    np.testing.assert_array_equal(peaklets["component_count"], [2, 2])


def test_peaklets_reject_out_of_range_flat_membership_index():
    merged = np.zeros(1, dtype=HIT_MERGED_DTYPE)
    merged["time_start"] = [1000]
    merged["time_end"] = [2000]
    components = np.array([(0, 1)], dtype=PEAKLET_COMPONENTS_DTYPE)
    ctx = DummyContext({"dt": 2}, {"hit_merged": merged, "peaklet_components": components})

    with pytest.raises(ValueError, match="out-of-range merged_index"):
        PeakletPlugin().compute_array(ctx, "run_001")
