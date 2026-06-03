import numpy as np

from tests.utils import DummyContext, FakeContext
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import (
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
    HitMergeClustersPlugin,
    HitMergedComponentsPlugin,
    HitMergePlugin,
)
from waveform_analysis.core.processing.chunk import Chunk


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
):
    arr = np.zeros(1, dtype=THRESHOLD_HIT_DTYPE)
    arr[0]["position"] = position
    arr[0]["edge_start"] = edge_start
    arr[0]["edge_end"] = edge_end
    arr[0]["width"] = edge_end - edge_start
    arr[0]["dt"] = dt
    arr[0]["timestamp"] = timestamp
    arr[0]["channel"] = channel
    arr[0]["record_id"] = record_id
    return arr[0]


def _chunk_stream(data, *more_data):
    for chunk_data in (data, *more_data):
        if len(chunk_data) == 0:
            continue
        if "timestamp" not in (chunk_data.dtype.names or ()):
            yield chunk_data
            continue
        yield Chunk(
            data=chunk_data,
            start=int(np.min(chunk_data["timestamp"])),
            end=int(np.max(chunk_data["timestamp"])),
            run_id="run_001",
            data_type="hit_threshold",
            time_field="timestamp",
        )


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

    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0)
    h2 = _make_hit(14, 25.0, 40.0, 13.0, 16.0, 108_000, 0, 1)
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
    assert float(out[0]["width"]) == -1.0
    assert int(out[0]["dt"]) == 2
    assert int(out[0]["component_offset"]) == 0
    assert int(out[0]["component_count"]) == 2
    assert int(out[0]["sample_start"]) == -1
    assert int(out[0]["sample_end"]) == -1
    assert float(out[0]["width"]) == -1.0


def test_hit_merge_single_record_merges_direct_record_window():
    plugin = HitMergePlugin()
    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 7)
    h2 = _make_hit(14, 25.0, 40.0, 13.0, 16.0, 108_000, 0, 7)
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)

    ctx = DummyContext(
        {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2}, {"hit_threshold": hits}
    )
    out = plugin.compute(ctx, "run_001")

    assert len(out) == 1
    assert int(out[0]["component_count"]) == 2
    assert int(out[0]["record_id"]) == 7
    assert int(out[0]["sample_start"]) == 8
    assert int(out[0]["sample_end"]) == 16
    assert float(out[0]["width"]) == 8.0


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
    np.testing.assert_array_equal(out["sample_start"], hits["edge_start"])
    np.testing.assert_array_equal(out["sample_end"], hits["edge_end"])
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


def test_hit_merge_clusters_materializes_hit_threshold_chunk_stream():
    plugin = HitMergeClustersPlugin()
    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0)
    h2 = _make_hit(14, 25.0, 40.0, 13.0, 16.0, 108_000, 0, 1)
    h3 = _make_hit(10, 22.0, 31.0, 8.0, 12.0, 200_000, 0, 2)
    hits = np.array([h1, h2, h3], dtype=THRESHOLD_HIT_DTYPE)
    ctx = DummyContext(
        {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2},
        {"hit_threshold": _chunk_stream(hits[:2], hits[2:])},
    )

    out = plugin.compute(ctx, "run_001")

    np.testing.assert_array_equal(out["cluster_index"], np.array([0, 0, 1], dtype=np.int64))
    np.testing.assert_array_equal(out["hit_index"], np.array([0, 1, 2], dtype=np.int64))


def test_hit_merge_materializes_upstream_array_outputs():
    cluster_plugin = HitMergeClustersPlugin()
    merge_plugin = HitMergePlugin()
    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0)
    h2 = _make_hit(14, 25.0, 40.0, 13.0, 16.0, 108_000, 0, 1)
    h3 = _make_hit(10, 22.0, 31.0, 8.0, 12.0, 200_000, 0, 2)
    hits = np.array([h1, h2, h3], dtype=THRESHOLD_HIT_DTYPE)
    config = {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2}
    cluster_rows = cluster_plugin.compute(DummyContext(config, {"hit_threshold": hits}), "run_001")
    ctx = DummyContext(
        config,
        {
            "hit_threshold": _chunk_stream(hits[:1], hits[1:]),
            "hit_merge_clusters": _chunk_stream(cluster_rows[:2], cluster_rows[2:]),
        },
    )

    out = merge_plugin.compute(ctx, "run_001")

    assert out.dtype == HIT_MERGED_DTYPE
    assert len(out) == 2
    np.testing.assert_array_equal(out["component_count"], np.array([2, 1], dtype=np.int32))


def test_hit_merged_components_materializes_upstream_array_outputs():
    cluster_plugin = HitMergeClustersPlugin()
    merge_plugin = HitMergePlugin()
    components_plugin = HitMergedComponentsPlugin()
    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0)
    h2 = _make_hit(14, 25.0, 40.0, 13.0, 16.0, 108_000, 0, 1)
    h3 = _make_hit(10, 22.0, 31.0, 8.0, 12.0, 200_000, 0, 2)
    hits = np.array([h1, h2, h3], dtype=THRESHOLD_HIT_DTYPE)
    config = {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2}
    cluster_rows = cluster_plugin.compute(DummyContext(config, {"hit_threshold": hits}), "run_001")
    merged = merge_plugin.compute(
        DummyContext(config, {"hit_threshold": hits, "hit_merge_clusters": cluster_rows}),
        "run_001",
    )
    ctx = DummyContext(
        config,
        {
            "hit_merged": _chunk_stream(merged[:1], merged[1:]),
            "hit_merge_clusters": _chunk_stream(cluster_rows[:2], cluster_rows[2:]),
        },
    )

    out = components_plugin.compute(ctx, "run_001")

    assert out.dtype == HIT_MERGED_COMPONENTS_DTYPE
    np.testing.assert_array_equal(out["merged_index"], np.array([0, 0, 1], dtype=np.int64))
    np.testing.assert_array_equal(out["hit_index"], np.array([0, 1, 2], dtype=np.int64))
