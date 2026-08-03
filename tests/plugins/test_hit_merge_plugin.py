import numpy as np

from tests.utils import DummyContext, FakeContext, make_hit
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
    HIT_MERGE_CLUSTERS_DTYPE,
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
    HitMergeClustersPlugin,
    HitMergedComponentsPlugin,
    HitMergePlugin,
)
from waveform_analysis.core.processing.chunk import Chunk


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

    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=108_000, channel=0, record_id=1
    )
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
    # 新增：验证新字段
    assert not out[0]["is_single_record"]
    assert int(out[0]["time_start"]) == 96000  # min(96000, 106000)
    assert int(out[0]["time_end"]) == 112000  # max(104000, 112000)


def test_hit_merge_single_record_merges_direct_record_window():
    plugin = HitMergePlugin()
    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=7
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=108_000, channel=0, record_id=7
    )
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
    # 新增：验证新字段
    assert out[0]["is_single_record"]
    assert int(out[0]["time_start"]) == 96000
    assert int(out[0]["time_end"]) == 112000


def test_hit_merge_not_across_channels():
    plugin = HitMergePlugin()

    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=11, edge_start=9.0, edge_end=13.0, timestamp=101_000, channel=1, record_id=1
    )
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

    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=200_000, channel=0, record_id=1
    )
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

    h1 = make_hit(
        position=10, edge_start=9.0, edge_end=11.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=15.0, timestamp=106_000, channel=0, record_id=1
    )
    h3 = make_hit(
        position=18, edge_start=17.0, edge_end=19.0, timestamp=112_000, channel=0, record_id=2
    )
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

    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=110_000, channel=0, record_id=1
    )
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
    np.testing.assert_array_equal(out["component_offset"], np.arange(2, dtype=np.int64))
    np.testing.assert_array_equal(out["component_count"], np.ones(2, dtype=np.int32))


def test_hit_merge_disabled_does_not_read_cluster_rows():
    class NoClusterContext(DummyContext):
        def get_data(self, run_id, name, **kwargs):
            if name == "hit_merge_clusters":
                raise AssertionError(
                    "hit_merge_clusters should not be read when merging is disabled"
                )
            return super().get_data(run_id, name, **kwargs)

    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=110_000, channel=0, record_id=1
    )
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)
    ctx = NoClusterContext(
        {"merge_gap_ns": 0.0, "max_total_width_ns": 10000.0, "dt": 2},
        {"hit_threshold": hits},
    )

    out = HitMergePlugin().compute(ctx, "run_001")

    assert len(out) == 2
    np.testing.assert_array_equal(out["component_count"], np.ones(2, dtype=np.int32))


def test_hit_merge_ignores_stale_cluster_rows_and_uses_own_config():
    class StaleClusterContext(DummyContext):
        def get_data(self, run_id, name, **kwargs):
            if name == "hit_merge_clusters":
                raise AssertionError("hit_merged should not read hit_merge_clusters")
            return super().get_data(run_id, name, **kwargs)

    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=108_000, channel=0, record_id=1
    )
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)
    stale_cluster_rows = np.array([(0, 0), (1, 1)], dtype=HIT_MERGE_CLUSTERS_DTYPE)
    ctx = StaleClusterContext(
        {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2},
        {"hit_threshold": hits, "hit_merge_clusters": stale_cluster_rows},
    )

    out = HitMergePlugin().compute(ctx, "run_001")

    assert len(out) == 1
    assert int(out[0]["component_count"]) == 2


def test_hit_merge_clusters_disabled_when_gap_non_positive_maps_hits_one_to_one():
    plugin = HitMergeClustersPlugin()
    merge_plugin = HitMergePlugin()

    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=110_000, channel=0, record_id=1
    )
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)

    ctx = FakeContext(
        {"hit_merged": {"merge_gap_ns": 0.0, "max_total_width_ns": 10000.0, "dt": 2}},
        {"hit_threshold": hits},
        plugins={"hit_merged": merge_plugin},
    )

    out = plugin.compute(ctx, "run_001")

    assert out.dtype == HIT_MERGE_CLUSTERS_DTYPE
    np.testing.assert_array_equal(out["cluster_index"], np.array([0, 1], dtype=np.int64))
    np.testing.assert_array_equal(out["hit_index"], np.array([0, 1], dtype=np.int64))


def test_hit_merge_clusters_uses_hit_merged_config_namespace():
    plugin = HitMergeClustersPlugin()
    merge_plugin = HitMergePlugin()

    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=108_000, channel=0, record_id=1
    )
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)
    ctx = FakeContext(
        {
            "hit_merged": {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2},
            "hit_merge_clusters": {
                "merge_gap_ns": 0.0,
                "max_total_width_ns": 10000.0,
                "dt": 2,
            },
        },
        {"hit_threshold": hits},
        plugins={"hit_merged": merge_plugin},
    )

    out = plugin.compute(ctx, "run_001")

    np.testing.assert_array_equal(out["cluster_index"], np.array([0, 0], dtype=np.int64))
    np.testing.assert_array_equal(out["hit_index"], np.array([0, 1], dtype=np.int64))


def test_hit_merge_uses_int64_ps_for_large_timestamps_and_small_gaps():
    plugin = HitMergePlugin()

    base_timestamp = 10_000_000_000_000_000
    h1 = make_hit(
        position=10,
        edge_start=8.0,
        edge_end=12.0,
        timestamp=base_timestamp,
        channel=0,
        record_id=0,
        dt=1,
    )
    h2 = make_hit(
        position=10,
        edge_start=8.0,
        edge_end=12.0,
        timestamp=base_timestamp + 20_000,
        channel=0,
        record_id=1,
        dt=1,
    )
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)

    ctx = DummyContext(
        {"merge_gap_ns": 5.0, "max_total_width_ns": 10000.0},
        {"hit_threshold": hits},
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 2
    np.testing.assert_array_equal(out["timestamp"], hits["timestamp"])


def test_hit_merge_clusters_numba_path_returns_contiguous_cluster_rows():
    plugin = HitMergeClustersPlugin()
    merge_plugin = HitMergePlugin()
    hits = np.array(
        [
            make_hit(
                position=10,
                edge_start=8.0,
                edge_end=12.0,
                timestamp=100_000 + idx * 20_000,
                channel=0,
                record_id=idx,
                dt=1,
            )
            for idx in range(205)
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )

    out = plugin.compute(
        FakeContext(
            {"hit_merged": {"merge_gap_ns": 5.0, "max_total_width_ns": 10000.0}},
            {"hit_threshold": hits},
            plugins={"hit_merged": merge_plugin},
        ),
        "run_001",
    )

    assert len(out) == len(hits)
    np.testing.assert_array_equal(out["cluster_index"], np.arange(len(hits), dtype=np.int64))
    np.testing.assert_array_equal(out["hit_index"], np.arange(len(hits), dtype=np.int64))


def test_hit_merge_clusters_keeps_contiguous_cluster_offsets_across_channels():
    plugin = HitMergeClustersPlugin()
    merge_plugin = HitMergePlugin()
    hits = np.array(
        [
            make_hit(
                position=10,
                edge_start=8.0,
                edge_end=12.0,
                timestamp=100_000,
                channel=0,
                record_id=0,
            ),
            make_hit(
                position=10,
                edge_start=8.0,
                edge_end=12.0,
                timestamp=200_000,
                channel=1,
                record_id=1,
            ),
            make_hit(
                position=14,
                edge_start=13.0,
                edge_end=16.0,
                timestamp=108_000,
                channel=0,
                record_id=2,
            ),
            make_hit(
                position=14,
                edge_start=13.0,
                edge_end=16.0,
                timestamp=208_000,
                channel=1,
                record_id=3,
            ),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )

    out = plugin.compute(
        FakeContext(
            {"hit_merged": {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2}},
            {"hit_threshold": hits},
            plugins={"hit_merged": merge_plugin},
        ),
        "run_001",
    )

    np.testing.assert_array_equal(out["cluster_index"], np.array([0, 0, 1, 1], dtype=np.int64))
    np.testing.assert_array_equal(out["hit_index"], np.array([0, 2, 1, 3], dtype=np.int64))


def test_hit_merge_single_hit_cluster_uses_sample_fields_without_temp_array():
    dtype = np.dtype(
        [
            ("position", "i8"),
            ("sample_start", "i4"),
            ("sample_end", "i4"),
            ("width", "f4"),
            ("dt", "i4"),
            ("timestamp", "i8"),
            ("board", "i2"),
            ("channel", "i2"),
            ("record_id", "i8"),
        ]
    )
    hits = np.zeros(1, dtype=dtype)
    hits[0]["position"] = 10
    hits[0]["sample_start"] = 7
    hits[0]["sample_end"] = 13
    hits[0]["width"] = 6
    hits[0]["dt"] = 2
    hits[0]["timestamp"] = 100_000
    hits[0]["channel"] = 0
    hits[0]["record_id"] = 3

    out = HitMergePlugin().compute(
        DummyContext(
            {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0},
            {"hit_threshold": hits},
        ),
        "run_001",
    )

    assert len(out) == 1
    assert int(out[0]["sample_start"]) == 7
    assert int(out[0]["sample_end"]) == 13


def test_hit_merge_does_not_merge_different_dt_values():
    plugin = HitMergePlugin()

    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0, dt=2
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=108_000, channel=0, record_id=1, dt=4
    )
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)

    ctx = DummyContext(
        {"merge_gap_ns": 10.0, "max_total_width_ns": 10000.0}, {"hit_threshold": hits}
    )
    out = plugin.compute(ctx, "run_001")

    assert len(out) == 2


def test_hit_merged_components_returns_flat_component_rows():
    merge_plugin = HitMergePlugin()
    components_plugin = HitMergedComponentsPlugin()
    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=108_000, channel=0, record_id=1
    )
    h3 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=200_000, channel=0, record_id=2
    )
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


def test_hit_merged_components_ignores_stale_cluster_rows_and_matches_hit_merged():
    class StaleClusterContext(FakeContext):
        def get_data(self, run_id, name, **kwargs):
            if name == "hit_merge_clusters":
                raise AssertionError("hit_merged_components should not read hit_merge_clusters")
            return super().get_data(run_id, name, **kwargs)

    merge_plugin = HitMergePlugin()
    components_plugin = HitMergedComponentsPlugin()
    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=108_000, channel=0, record_id=1
    )
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)
    config = {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2}
    merged = merge_plugin.compute(DummyContext(config, {"hit_threshold": hits}), "run_001")
    stale_cluster_rows = np.array([(0, 0), (1, 1)], dtype=HIT_MERGE_CLUSTERS_DTYPE)
    ctx = StaleClusterContext(
        config,
        {
            "hit_threshold": hits,
            "hit_merged": merged,
            "hit_merge_clusters": stale_cluster_rows,
        },
        plugins={"hit_merged": merge_plugin},
    )

    out = components_plugin.compute(ctx, "run_001")

    np.testing.assert_array_equal(out["merged_index"], np.array([0, 0], dtype=np.int64))
    np.testing.assert_array_equal(out["hit_index"], np.array([0, 1], dtype=np.int64))


def test_hit_merged_components_validate_components_checks_consistency():
    components_plugin = HitMergedComponentsPlugin()
    merge_plugin = HitMergePlugin()
    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    hits = np.array([h1], dtype=THRESHOLD_HIT_DTYPE)
    merged = np.zeros(1, dtype=HIT_MERGED_DTYPE)
    merged[0]["component_offset"] = 99
    merged[0]["component_count"] = 1

    default_ctx = FakeContext(
        {},
        {"hit_threshold": hits, "hit_merged": merged},
        plugins={"hit_merged": merge_plugin},
    )
    out = components_plugin.compute(default_ctx, "run_001")
    np.testing.assert_array_equal(out["merged_index"], np.array([0], dtype=np.int64))
    np.testing.assert_array_equal(out["hit_index"], np.array([0], dtype=np.int64))

    validate_ctx = FakeContext(
        {"validate_components": True},
        {"hit_threshold": hits, "hit_merged": merged},
        plugins={"hit_merged": merge_plugin},
    )
    try:
        components_plugin.compute(validate_ctx, "run_001")
    except ValueError as exc:
        assert "component_offset mismatch" in str(exc)
    else:
        raise AssertionError("validate_components=True should check merged component metadata")


def test_hit_merge_clusters_materializes_hit_threshold_chunk_stream():
    plugin = HitMergeClustersPlugin()
    merge_plugin = HitMergePlugin()
    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=108_000, channel=0, record_id=1
    )
    h3 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=200_000, channel=0, record_id=2
    )
    hits = np.array([h1, h2, h3], dtype=THRESHOLD_HIT_DTYPE)
    ctx = FakeContext(
        {"hit_merged": {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2}},
        {"hit_threshold": _chunk_stream(hits[:2], hits[2:])},
        plugins={"hit_merged": merge_plugin},
    )

    out = plugin.compute(ctx, "run_001")

    np.testing.assert_array_equal(out["cluster_index"], np.array([0, 0, 1], dtype=np.int64))
    np.testing.assert_array_equal(out["hit_index"], np.array([0, 1, 2], dtype=np.int64))


def test_hit_merge_clusters_materializes_many_hit_threshold_chunks():
    plugin = HitMergeClustersPlugin()
    merge_plugin = HitMergePlugin()
    hits = np.array(
        [
            make_hit(
                position=10,
                edge_start=8.0,
                edge_end=12.0,
                timestamp=100_000 + idx * 20_000,
                channel=0,
                record_id=idx,
            )
            for idx in range(105)
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = FakeContext(
        {"hit_merged": {"merge_gap_ns": 0.0, "max_total_width_ns": 10000.0, "dt": 2}},
        {"hit_threshold": _chunk_stream(*[hits[idx : idx + 1] for idx in range(len(hits))])},
        plugins={"hit_merged": merge_plugin},
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == len(hits)
    np.testing.assert_array_equal(out["hit_index"], np.arange(len(hits), dtype=np.int64))


def test_hit_merge_materializes_upstream_array_outputs():
    cluster_plugin = HitMergeClustersPlugin()
    merge_plugin = HitMergePlugin()
    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=108_000, channel=0, record_id=1
    )
    h3 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=200_000, channel=0, record_id=2
    )
    hits = np.array([h1, h2, h3], dtype=THRESHOLD_HIT_DTYPE)
    config = {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2}
    cluster_rows = cluster_plugin.compute(
        FakeContext(
            {"hit_merged": config},
            {"hit_threshold": hits},
            plugins={"hit_merged": merge_plugin},
        ),
        "run_001",
    )
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
    h1 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=100_000, channel=0, record_id=0
    )
    h2 = make_hit(
        position=14, edge_start=13.0, edge_end=16.0, timestamp=108_000, channel=0, record_id=1
    )
    h3 = make_hit(
        position=10, edge_start=8.0, edge_end=12.0, timestamp=200_000, channel=0, record_id=2
    )
    hits = np.array([h1, h2, h3], dtype=THRESHOLD_HIT_DTYPE)
    config = {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2}
    cluster_rows = cluster_plugin.compute(
        FakeContext(
            {"hit_merged": config},
            {"hit_threshold": hits},
            plugins={"hit_merged": merge_plugin},
        ),
        "run_001",
    )
    merged = merge_plugin.compute(
        DummyContext(config, {"hit_threshold": hits, "hit_merge_clusters": cluster_rows}),
        "run_001",
    )
    ctx = FakeContext(
        config,
        {
            "hit_threshold": _chunk_stream(hits[:1], hits[1:]),
            "hit_merged": _chunk_stream(merged[:1], merged[1:]),
            "hit_merge_clusters": _chunk_stream(cluster_rows[:2], cluster_rows[2:]),
        },
        plugins={"hit_merged": merge_plugin},
    )

    out = components_plugin.compute(ctx, "run_001")

    assert out.dtype == HIT_MERGED_COMPONENTS_DTYPE
    np.testing.assert_array_equal(out["merged_index"], np.array([0, 0, 1], dtype=np.int64))
    np.testing.assert_array_equal(out["hit_index"], np.array([0, 1, 2], dtype=np.int64))
