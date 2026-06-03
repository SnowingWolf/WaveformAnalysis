import numpy as np

from tests.utils import DummyContext, make_records
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import (
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


def _make_peaklet_context(hits, wave_pool, *, time_window_ns=4.0):
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

    feature_ctx = DummyContext(
        {
            "wave_source": "records",
            "use_filtered": False,
            "dt": 2,
        },
        {
            "hit_threshold": hits,
            "hit_merged": merged,
            "hit_merged_components": components,
            "records": records,
            "wave_pool": wave_pool,
        },
    )
    features = HitMergedFeaturesPlugin().compute(feature_ctx, "run_001")

    return DummyContext(
        {
            "time_window_ns": time_window_ns,
            "max_total_width_ns": 10000.0,
            "dt": 2,
        },
        {
            "hit_threshold": hits,
            "hit_merged": merged,
            "hit_merged_components": components,
            "hit_merged_features": features,
            "records": records,
            "wave_pool": wave_pool,
        },
    )


def test_peaklets_merge_cross_channel_hits_and_compute_features():
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=3, edge_end=5),
            _make_hit(record_id=1, board=0, channel=1, edge_start=4, edge_end=6),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    wave_pool = np.array(
        [
            100,
            100,
            100,
            80,
            70,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            90,
            80,
            100,
            100,
            100,
            100,
        ],
        dtype=np.uint16,
    )
    ctx = _make_peaklet_context(hits, wave_pool)

    out = PeakletPlugin().compute_array(ctx, "run_001")

    assert out.dtype == PEAKLET_DTYPE
    assert len(out) == 1
    row = out[0]
    assert int(row["time_start"]) == 6000
    assert int(row["time_end"]) == 12000
    assert int(row["max_time"]) == 8000
    assert float(row["area"]) == 80.0
    assert float(row["height"]) == 40.0
    assert float(row["width"]) == 6.0
    assert float(row["rise_time"]) == 2.0
    assert float(row["fall_time"]) == 4.0
    assert int(row["n_hits"]) == 2
    assert int(row["n_channels"]) == 2


def test_peaklets_aggregate_area_hits_and_channels_from_hit_merged_features():
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=3, edge_end=5),
            _make_hit(record_id=1, board=0, channel=1, edge_start=4, edge_end=6),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    wave_pool = np.full(20, 100, dtype=np.uint16)
    ctx = _make_peaklet_context(hits, wave_pool)
    features = ctx._data["hit_merged_features"].copy()
    features["area"] = np.array([123.0, 7.0], dtype=np.float32)
    features["n_hits"] = np.array([3, 4], dtype=np.int32)
    ctx._data["hit_merged_features"] = features

    out = PeakletPlugin().compute_array(ctx, "run_001")

    assert len(out) == 1
    assert float(out[0]["area"]) == 130.0
    assert int(out[0]["n_hits"]) == 7
    assert int(out[0]["n_channels"]) == 2


def test_peaklets_split_when_cross_channel_gap_exceeds_window():
    hits = np.array(
        [
            _make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=2),
            _make_hit(record_id=1, board=0, channel=1, edge_start=8, edge_end=9),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    wave_pool = np.full(20, 100, dtype=np.uint16)
    wave_pool[1] = 80
    wave_pool[18] = 80
    ctx = _make_peaklet_context(hits, wave_pool, time_window_ns=1.0)

    out = PeakletPlugin().compute_array(ctx, "run_001")
    components = PeakletComponentsPlugin().compute_array(ctx, "run_001")

    assert len(out) == 2
    assert components.dtype == PEAKLET_COMPONENTS_DTYPE
    np.testing.assert_array_equal(components["peaklet_index"], np.array([0, 1], dtype=np.int64))
    np.testing.assert_array_equal(components["merged_index"], np.array([0, 1], dtype=np.int64))
