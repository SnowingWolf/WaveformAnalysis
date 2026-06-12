import numpy as np

from tests.utils import DummyContext, make_records
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import (
    HIT_MERGED_DTYPE,
    HitMergedComponentsPlugin,
    HitMergePlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.hit_merged_features import HitMergedFeaturesPlugin
from waveform_analysis.core.plugins.builtin.cpu.peaklets import (
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

    return DummyContext(
        {
            "time_window_ns": time_window_ns,
            "max_total_width_ns": 10000.0,
            "dt": 2,
            "use_filtered": use_filtered,
        },
        data,
    )


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
    components = PeakletComponentsPlugin().compute_array(ctx, "run_001")

    assert len(out) == 2
    assert components.dtype == PEAKLET_COMPONENTS_DTYPE
    np.testing.assert_array_equal(components["peak_id"], np.array([0, 1], dtype=np.int64))
    np.testing.assert_array_equal(components["merged_index"], np.array([0, 1], dtype=np.int64))


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

    out = PeakletPlugin().compute_array(ctx, "run_001")

    assert len(out) == 2
