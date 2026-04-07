import numpy as np
import pandas as pd

from tests.utils import DummyContext, FakeContext
from waveform_analysis.core.plugins.builtin.cpu.event_analysis import HitGroupedPlugin
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import (
    HitMergedComponentsPlugin,
    HitMergePlugin,
)


def _make_hit(
    *,
    position,
    height,
    integral,
    edge_start,
    edge_end,
    timestamp,
    board,
    channel,
    record_id,
    dt=2,
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
    arr[0]["board"] = board
    arr[0]["channel"] = channel
    arr[0]["record_id"] = record_id
    return arr[0]


def test_hit_grouped_empty():
    plugin = HitGroupedPlugin()
    ctx = DummyContext(
        {"time_window_ns": 0.0, "dt": 2},
        {
            "hit_merged": np.zeros(0, dtype=THRESHOLD_HIT_DTYPE),
            "hit_merged_components": np.zeros(
                0, dtype=[("merged_index", "i8"), ("hit_index", "i8")]
            ),
            "hit_threshold": np.zeros(0, dtype=THRESHOLD_HIT_DTYPE),
        },
    )

    out = plugin.compute(ctx, "run_001")

    assert isinstance(out, pd.DataFrame)
    assert out.empty
    assert list(out.columns) == [
        "event_id",
        "t_min",
        "t_max",
        "dt/ns",
        "n_hits",
        "dt",
        "boards",
        "channels",
        "heights",
        "integrals",
        "timestamps",
        "record_ids",
        "sample_starts",
        "sample_ends",
    ]


def test_hit_grouped_merges_overlapping_windows_across_channels():
    plugin = HitGroupedPlugin()
    h1 = _make_hit(
        position=10,
        height=20.0,
        integral=30.0,
        edge_start=8.0,
        edge_end=12.0,
        timestamp=100_000,
        board=0,
        channel=0,
        record_id=0,
    )
    h2 = _make_hit(
        position=14,
        height=25.0,
        integral=40.0,
        edge_start=13.0,
        edge_end=16.0,
        timestamp=106_000,
        board=0,
        channel=1,
        record_id=1,
    )
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)
    ctx = DummyContext(
        {"time_window_ns": 0.0, "dt": 2},
        {
            "hit_merged": hits,
            "hit_merged_components": np.array(
                [(0, 0), (1, 1)], dtype=[("merged_index", "i8"), ("hit_index", "i8")]
            ),
            "hit_threshold": hits,
        },
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 1
    row = out.iloc[0]
    assert row["n_hits"] == 2
    np.testing.assert_array_equal(row["boards"], np.array([0, 0], dtype=np.int16))
    np.testing.assert_array_equal(row["channels"], np.array([0, 1], dtype=np.int16))
    np.testing.assert_array_equal(row["record_ids"], np.array([0, 1], dtype=np.int64))
    np.testing.assert_array_equal(row["sample_starts"], np.array([8, 13], dtype=np.int32))
    np.testing.assert_array_equal(row["sample_ends"], np.array([12, 16], dtype=np.int32))
    np.testing.assert_array_equal(row["dt"], np.array([2, 2], dtype=np.int32))
    assert row["t_min"] == 96_000
    assert row["t_max"] == 110_000
    assert row["dt/ns"] == 14.0


def test_hit_grouped_merges_non_overlapping_windows_with_gap_threshold():
    plugin = HitGroupedPlugin()
    h1 = _make_hit(
        position=10,
        height=10.0,
        integral=5.0,
        edge_start=8.0,
        edge_end=12.0,
        timestamp=100_000,
        board=0,
        channel=0,
        record_id=0,
    )
    h2 = _make_hit(
        position=18,
        height=12.0,
        integral=6.0,
        edge_start=17.0,
        edge_end=19.0,
        timestamp=112_000,
        board=0,
        channel=1,
        record_id=1,
    )
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)
    ctx = DummyContext(
        {"time_window_ns": 7.0, "dt": 2},
        {
            "hit_merged": hits,
            "hit_merged_components": np.array(
                [(0, 0), (1, 1)], dtype=[("merged_index", "i8"), ("hit_index", "i8")]
            ),
            "hit_threshold": hits,
        },
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 1
    assert out.iloc[0]["t_min"] == 96_000
    assert out.iloc[0]["t_max"] == 114_000


def test_hit_grouped_splits_clusters_when_gap_is_too_large():
    plugin = HitGroupedPlugin()
    h1 = _make_hit(
        position=10,
        height=10.0,
        integral=5.0,
        edge_start=8.0,
        edge_end=12.0,
        timestamp=100_000,
        board=0,
        channel=0,
        record_id=0,
    )
    h2 = _make_hit(
        position=18,
        height=12.0,
        integral=6.0,
        edge_start=17.0,
        edge_end=19.0,
        timestamp=112_000,
        board=0,
        channel=1,
        record_id=1,
    )
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)
    ctx = DummyContext(
        {"time_window_ns": 1.0, "dt": 2},
        {
            "hit_merged": hits,
            "hit_merged_components": np.array(
                [(0, 0), (1, 1)], dtype=[("merged_index", "i8"), ("hit_index", "i8")]
            ),
            "hit_threshold": hits,
        },
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 2
    assert list(out["event_id"]) == [0, 1]


def test_hit_grouped_keeps_all_hits_and_sorts_by_board_then_channel():
    plugin = HitGroupedPlugin()
    h1 = _make_hit(
        position=10,
        height=11.0,
        integral=5.0,
        edge_start=8.0,
        edge_end=12.0,
        timestamp=100_000,
        board=1,
        channel=0,
        record_id=10,
    )
    h2 = _make_hit(
        position=11,
        height=12.0,
        integral=6.0,
        edge_start=9.0,
        edge_end=13.0,
        timestamp=100_500,
        board=0,
        channel=1,
        record_id=11,
    )
    h3 = _make_hit(
        position=12,
        height=13.0,
        integral=7.0,
        edge_start=10.0,
        edge_end=14.0,
        timestamp=101_000,
        board=0,
        channel=1,
        record_id=12,
    )
    hits = np.array([h1, h2, h3], dtype=THRESHOLD_HIT_DTYPE)
    ctx = DummyContext(
        {"time_window_ns": 5.0, "dt": 2},
        {
            "hit_merged": hits,
            "hit_merged_components": np.array(
                [(0, 0), (1, 1), (2, 2)], dtype=[("merged_index", "i8"), ("hit_index", "i8")]
            ),
            "hit_threshold": hits,
        },
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 1
    row = out.iloc[0]
    assert row["n_hits"] == 3
    np.testing.assert_array_equal(row["boards"], np.array([0, 0, 1], dtype=np.int16))
    np.testing.assert_array_equal(row["channels"], np.array([1, 1, 0], dtype=np.int16))
    np.testing.assert_array_equal(row["record_ids"], np.array([11, 12, 10], dtype=np.int64))


def test_hit_grouped_supports_chain_expansion():
    plugin = HitGroupedPlugin()
    h1 = _make_hit(
        position=10,
        height=10.0,
        integral=5.0,
        edge_start=9.0,
        edge_end=11.0,
        timestamp=100_000,
        board=0,
        channel=0,
        record_id=0,
    )
    h2 = _make_hit(
        position=14,
        height=12.0,
        integral=6.0,
        edge_start=13.0,
        edge_end=15.0,
        timestamp=108_000,
        board=0,
        channel=1,
        record_id=1,
    )
    h3 = _make_hit(
        position=18,
        height=14.0,
        integral=7.0,
        edge_start=17.0,
        edge_end=19.0,
        timestamp=116_000,
        board=0,
        channel=2,
        record_id=2,
    )
    hits = np.array([h1, h2, h3], dtype=THRESHOLD_HIT_DTYPE)
    ctx = DummyContext(
        {"time_window_ns": 4.0, "dt": 2},
        {
            "hit_merged": hits,
            "hit_merged_components": np.array(
                [(0, 0), (1, 1), (2, 2)], dtype=[("merged_index", "i8"), ("hit_index", "i8")]
            ),
            "hit_threshold": hits,
        },
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 1
    assert out.iloc[0]["n_hits"] == 3


def test_hit_grouped_merges_different_dt_values_when_absolute_windows_overlap():
    plugin = HitGroupedPlugin()
    h1 = _make_hit(
        position=10,
        height=20.0,
        integral=30.0,
        edge_start=8.0,
        edge_end=12.0,
        timestamp=100_000,
        board=0,
        channel=0,
        record_id=0,
        dt=2,
    )
    h2 = _make_hit(
        position=10,
        height=22.0,
        integral=31.0,
        edge_start=8.0,
        edge_end=12.0,
        timestamp=100_000,
        board=0,
        channel=1,
        record_id=1,
        dt=4,
    )
    hits = np.array([h1, h2], dtype=THRESHOLD_HIT_DTYPE)

    ctx = DummyContext(
        {"time_window_ns": 10.0},
        {
            "hit_merged": hits,
            "hit_merged_components": np.array(
                [(0, 0), (1, 1)], dtype=[("merged_index", "i8"), ("hit_index", "i8")]
            ),
            "hit_threshold": hits,
        },
    )
    out = plugin.compute(ctx, "run_001")

    assert len(out) == 1
    row = out.iloc[0]
    assert row["t_min"] == 92_000
    assert row["t_max"] == 108_000
    np.testing.assert_array_equal(row["dt"], np.array([2, 4], dtype=np.int32))


def test_hit_grouped_uses_components_for_cross_record_merged_windows():
    merge_plugin = HitMergePlugin()
    components_plugin = HitMergedComponentsPlugin()
    grouped_plugin = HitGroupedPlugin()

    h1 = _make_hit(
        position=10,
        height=20.0,
        integral=30.0,
        edge_start=8,
        edge_end=12,
        timestamp=100_000,
        board=0,
        channel=0,
        record_id=0,
        dt=2,
    )
    h2 = _make_hit(
        position=14,
        height=25.0,
        integral=40.0,
        edge_start=13,
        edge_end=16,
        timestamp=108_000,
        board=0,
        channel=0,
        record_id=1,
        dt=2,
    )
    h3 = _make_hit(
        position=10,
        height=18.0,
        integral=22.0,
        edge_start=8,
        edge_end=12,
        timestamp=107_000,
        board=0,
        channel=1,
        record_id=2,
        dt=2,
    )
    threshold_hits = np.array([h1, h2, h3], dtype=THRESHOLD_HIT_DTYPE)

    base_ctx = DummyContext(
        {"merge_gap_ns": 3.0, "max_total_width_ns": 10000.0, "dt": 2},
        {"hit_threshold": threshold_hits},
    )
    merged = merge_plugin.compute(base_ctx, "run_001")

    ctx = FakeContext(
        {
            "merge_gap_ns": 3.0,
            "max_total_width_ns": 10000.0,
            "time_window_ns": 0.0,
            "dt": 2,
        },
        {
            "hit_threshold": threshold_hits,
            "hit_merged": merged,
        },
        plugins={"hit_merged": merge_plugin},
    )
    components = components_plugin.compute(ctx, "run_001")
    ctx._data["hit_merged_components"] = components

    out = grouped_plugin.compute(ctx, "run_001")

    assert len(out) == 1
    row = out.iloc[0]
    assert row["n_hits"] == 2
    assert row["t_min"] == 96_000
    assert row["t_max"] == 112_000
    np.testing.assert_array_equal(row["sample_starts"], np.array([-1, 8], dtype=np.int32))
    np.testing.assert_array_equal(row["sample_ends"], np.array([-1, 12], dtype=np.int32))
