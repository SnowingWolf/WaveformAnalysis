import numpy as np
import pytest

from tests.utils import DummyContext, FakeContext, make_hit
from waveform_analysis.core.foundation.utils import Profiler
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
    HIT_MERGE_CLUSTERS_DTYPE,
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
    HitMergeClustersPlugin,
    HitMergedComponentsPlugin,
    HitMergePlugin,
)
from waveform_analysis.core.plugins.builtin.hit_merged import _compute as hit_merge_compute
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


def test_hit_merge_empty_does_not_build_enriched_arrays(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("empty hit input should not build enriched arrays")

    monkeypatch.setattr(hit_merge_compute, "_build_enriched_arrays", fail_if_called)
    ctx = DummyContext(
        {"merge_gap_ns": 50.0},
        {"hit_threshold": np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)},
    )

    out = HitMergePlugin().compute(ctx, "run_001")

    assert out.shape == (0,)
    assert out.dtype == HIT_MERGED_DTYPE


def test_hit_merge_reuses_one_global_enriched_array_for_interleaved_channels(monkeypatch):
    hits = np.array(
        [
            make_hit(
                position=10,
                edge_start=8,
                edge_end=12,
                timestamp=100_000,
                board=0,
                channel=1,
                record_id=0,
            ),
            make_hit(
                position=10,
                edge_start=8,
                edge_end=12,
                timestamp=200_000,
                board=0,
                channel=0,
                record_id=1,
            ),
            make_hit(
                position=14,
                edge_start=13,
                edge_end=16,
                timestamp=108_000,
                board=0,
                channel=1,
                record_id=0,
            ),
            make_hit(
                position=14,
                edge_start=13,
                edge_end=16,
                timestamp=208_000,
                board=0,
                channel=0,
                record_id=1,
            ),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    config = {"merge_gap_ns": 3.0, "max_total_width_ns": 10_000.0, "dt": 2}
    calls = []
    original = hit_merge_compute._build_enriched_arrays

    def counted(*args, **kwargs):
        calls.append(len(args[0]))
        return original(*args, **kwargs)

    monkeypatch.setattr(hit_merge_compute, "_build_enriched_arrays", counted)
    merge_plugin = HitMergePlugin()
    ctx = FakeContext(
        {"hit_merged": config},
        {"hit_threshold": hits},
        plugins={"hit_merged": merge_plugin},
    )

    out = merge_plugin.compute(ctx, "run_001")

    expected = np.zeros(2, dtype=HIT_MERGED_DTYPE)
    expected["merged_id"] = [0, 1]
    expected["position"] = [10, 10]
    expected["time_start"] = [196_000, 96_000]
    expected["time_end"] = [212_000, 112_000]
    expected["sample_start"] = [8, 8]
    expected["sample_end"] = [16, 16]
    expected["width"] = [8.0, 8.0]
    expected["dt"] = [2, 2]
    expected["timestamp"] = [200_000, 100_000]
    expected["board"] = [0, 0]
    expected["channel"] = [0, 1]
    expected["record_id"] = [1, 0]
    expected["component_offset"] = [0, 2]
    expected["component_count"] = [2, 2]
    expected["is_single_record"] = [True, True]

    np.testing.assert_array_equal(out, expected)
    assert calls == [len(hits)]

    clusters = HitMergeClustersPlugin().compute(ctx, "run_001")
    expected_clusters = np.array([(0, 1), (0, 3), (1, 0), (1, 2)], dtype=HIT_MERGE_CLUSTERS_DTYPE)
    np.testing.assert_array_equal(clusters, expected_clusters)


def test_hit_merge_profiler_segments_preserve_output_and_order():
    hits = np.array(
        [
            make_hit(
                position=10,
                edge_start=8.0,
                edge_end=12.0,
                timestamp=100_000,
                board=0,
                channel=0,
                record_id=0,
            ),
            make_hit(
                position=14,
                edge_start=13.0,
                edge_end=16.0,
                timestamp=108_000,
                board=0,
                channel=0,
                record_id=1,
            ),
            make_hit(
                position=20,
                edge_start=18.0,
                edge_end=22.0,
                timestamp=200_000,
                board=1,
                channel=0,
                record_id=2,
            ),
            make_hit(
                position=24,
                edge_start=23.0,
                edge_end=26.0,
                timestamp=208_000,
                board=1,
                channel=0,
                record_id=3,
            ),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    config = {"merge_gap_ns": 3.0, "max_total_width_ns": 10_000.0, "dt": 2}
    expected = HitMergePlugin().compute(DummyContext(config, {"hit_threshold": hits}), "run_001")
    profiled_context = DummyContext(config, {"hit_threshold": hits})
    profiled_context.profiler = Profiler()

    actual = HitMergePlugin().compute(profiled_context, "run_001")

    np.testing.assert_array_equal(actual, expected)
    assert actual.dtype == expected.dtype == HIT_MERGED_DTYPE
    assert profiled_context.profiler.counts == {
        "hit_merged.group_hardware_channels": 1,
        "hit_merged.per_channel_mergesort": 2,
        "hit_merged.cluster_scan": 2,
        "hit_merged.cluster_rows_concat": 1,
        "hit_merged.merged_materialize": 1,
    }
    assert all(
        profiled_context.profiler.durations[key] >= 0.0 for key in profiled_context.profiler.counts
    )


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


def test_hit_merge_family_shares_canonical_rows_within_context(monkeypatch):
    merge_plugin = HitMergePlugin()
    components_plugin = HitMergedComponentsPlugin()
    cluster_plugin = HitMergeClustersPlugin()
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
                position=14,
                edge_start=13.0,
                edge_end=16.0,
                timestamp=108_000,
                channel=0,
                record_id=1,
            ),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    config = {
        "hit_merged": {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2},
    }
    ctx = FakeContext(config, {"hit_threshold": hits}, plugins={"hit_merged": merge_plugin})

    calls = []
    original = hit_merge_compute._compute_canonical_cluster_rows

    def counted(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(hit_merge_compute, "_compute_canonical_cluster_rows", counted)

    merged = merge_plugin.compute(ctx, "run_001")
    ctx._set_data("run_001", "hit_merged", merged)
    components = components_plugin.compute(ctx, "run_001")
    clusters = cluster_plugin.compute(ctx, "run_001")

    assert len(calls) == 1
    np.testing.assert_array_equal(components["merged_index"], clusters["cluster_index"])
    np.testing.assert_array_equal(components["hit_index"], clusters["hit_index"])


def test_hit_merge_cluster_rows_guard_invalidates_config_and_run(monkeypatch):
    merge_plugin = HitMergePlugin()
    cluster_plugin = HitMergeClustersPlugin()
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
                position=14,
                edge_start=13.0,
                edge_end=16.0,
                timestamp=108_000,
                channel=0,
                record_id=1,
            ),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = FakeContext(
        {"hit_merged": {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2}},
        {"hit_threshold": hits},
        plugins={"hit_merged": merge_plugin},
    )

    calls = []
    original = hit_merge_compute._compute_canonical_cluster_rows

    def counted(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(hit_merge_compute, "_compute_canonical_cluster_rows", counted)

    cluster_plugin.compute(ctx, "run_001")
    assert len(calls) == 1
    assert (
        sum(
            isinstance(name, str) and name.startswith("_hit_merge_cluster_rows-")
            for run_id, name in ctx._results
            if run_id == "run_001"
        )
        == 1
    )

    ctx.config["hit_merged"]["merge_gap_ns"] = 0.0
    cluster_plugin.compute(ctx, "run_001")
    assert len(calls) == 2
    assert (
        sum(
            isinstance(name, str) and name.startswith("_hit_merge_cluster_rows-")
            for run_id, name in ctx._results
            if run_id == "run_001"
        )
        == 1
    )

    cluster_plugin.compute(ctx, "run_002")
    assert len(calls) == 3
    assert (
        sum(
            isinstance(name, str) and name.startswith("_hit_merge_cluster_rows-")
            for run_id, name in ctx._results
        )
        == 2
    )


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


def test_hit_merge_multi_hit_numba_matches_python_oracle(monkeypatch):
    """The CSR kernel preserves every field of the historical Python loop."""

    hits = np.zeros(7, dtype=THRESHOLD_HIT_DTYPE)
    hits["position"] = np.array([100, 203, 300, 401, 502, 603, 704], dtype=np.int64)
    hits["edge_start"] = np.array([90, 193, 295, 396, 497, 598, 699], dtype=np.int32)
    hits["edge_end"] = np.array([110, 213, 305, 406, 507, 608, 709], dtype=np.int32)
    hits["width"] = hits["edge_end"] - hits["edge_start"]
    hits["dt"] = np.array([1, 1, 2, 2, 2, 4, 4], dtype=np.int32)
    hits["timestamp"] = np.array([1000, 1010, 2000, 2030, 2040, 3000, 3010], dtype=np.int64)
    hits["board"] = np.array([0, 0, 0, 0, 1, 1, 1], dtype=np.int16)
    hits["channel"] = np.array([0, 0, 1, 1, 1, 2, 2], dtype=np.int16)
    hits["record_id"] = np.array([7, 7, 8, 9, 9, 10, 10], dtype=np.int64)

    cluster_rows = np.array(
        [
            (0, 0),
            (0, 1),  # same-record, midpoint tie: hit 0 remains the anchor
            (1, 2),  # single cluster
            (2, 3),
            (2, 4),  # same-record, different board in this direct oracle fixture
            (3, 5),
            (3, 6),
        ],
        dtype=HIT_MERGE_CLUSTERS_DTYPE,
    )
    enriched = hit_merge_compute._build_enriched_for_hits(
        hits,
        explicit_dt=None,
        plugin_name="test_hit_merge",
    )

    accelerated = hit_merge_compute._build_merged_from_cluster_rows(hits, cluster_rows, enriched)
    monkeypatch.setattr(hit_merge_compute, "_fill_multi_hit_clusters_numba", None)
    oracle = hit_merge_compute._build_merged_from_cluster_rows(hits, cluster_rows, enriched)

    assert accelerated.tobytes() == oracle.tobytes()
    assert int(accelerated[0]["position"]) == int(hits[0]["position"])
    assert bool(accelerated[2]["is_single_record"])
    assert int(accelerated[2]["component_count"]) == 2


def test_hit_merge_multi_hit_invalid_membership_is_rejected_before_kernel():
    hits = np.array(
        [
            make_hit(
                position=10,
                edge_start=8,
                edge_end=12,
                timestamp=100_000,
                channel=0,
                record_id=0,
            )
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    cluster_rows = np.array([(0, 0), (0, 99)], dtype=HIT_MERGE_CLUSTERS_DTYPE)
    enriched = hit_merge_compute._build_enriched_for_hits(
        hits,
        explicit_dt=2,
        plugin_name="test_hit_merge",
    )

    with pytest.raises(ValueError, match="invalid hit index"):
        hit_merge_compute._build_merged_from_cluster_rows(hits, cluster_rows, enriched)
