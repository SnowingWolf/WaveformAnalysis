import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import HitMergePlugin
from waveform_analysis.core.plugins.builtin.cpu.peak_finding import HIT_DTYPE


def _make_hit(
    position,
    height,
    integral,
    edge_start,
    edge_end,
    timestamp,
    channel,
    event_index,
):
    arr = np.zeros(1, dtype=HIT_DTYPE)
    arr[0]["position"] = position
    arr[0]["height"] = height
    arr[0]["integral"] = integral
    arr[0]["edge_start"] = edge_start
    arr[0]["edge_end"] = edge_end
    arr[0]["timestamp"] = timestamp
    arr[0]["channel"] = channel
    arr[0]["event_index"] = event_index
    return arr[0]


def test_hit_merge_dtype_and_empty():
    plugin = HitMergePlugin()
    ctx = DummyContext({"merge_gap_ns": 50.0}, {"hit_threshold": np.zeros(0, dtype=HIT_DTYPE)})

    out = plugin.compute(ctx, "run_001")

    assert out.dtype == HIT_DTYPE
    assert len(out) == 0


def test_hit_merge_same_channel_across_records():
    plugin = HitMergePlugin()

    # dt = 2ns -> 2000ps; 构造边界间距 2ns (<= merge_gap_ns=3)
    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0)
    # abs_start = 108000 + (13-14)*2000 = 106000ps; previous abs_end = 104000ps => gap=2ns
    h2 = _make_hit(14, 25.0, 40.0, 13.0, 16.0, 108_000, 0, 1)
    hits = np.array([h1, h2], dtype=HIT_DTYPE)

    ctx = DummyContext(
        {
            "merge_gap_ns": 3.0,
            "max_total_width_ns": 10000.0,
            "sampling_interval_ns": 2.0,
        },
        {"hit_threshold": hits},
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 1
    assert out[0]["board"] == 0
    assert out[0]["channel"] == 0
    # highest peak semantic: should anchor to h2
    assert int(out[0]["event_index"]) == 1
    assert int(out[0]["position"]) == 14
    assert float(out[0]["height"]) == 25.0
    assert abs(float(out[0]["integral"]) - 70.0) < 1e-6


def test_hit_merge_not_across_channels():
    plugin = HitMergePlugin()

    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0)
    h2 = _make_hit(11, 22.0, 31.0, 9.0, 13.0, 101_000, 1, 1)
    hits = np.array([h1, h2], dtype=HIT_DTYPE)

    ctx = DummyContext(
        {
            "merge_gap_ns": 100.0,
            "max_total_width_ns": 10000.0,
            "sampling_interval_ns": 2.0,
        },
        {"hit_threshold": hits},
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 2


def test_hit_merge_gap_exceeds_threshold():
    plugin = HitMergePlugin()

    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0)
    # very far in time
    h2 = _make_hit(10, 22.0, 31.0, 8.0, 12.0, 200_000, 0, 1)
    hits = np.array([h1, h2], dtype=HIT_DTYPE)

    ctx = DummyContext(
        {
            "merge_gap_ns": 5.0,
            "max_total_width_ns": 10000.0,
            "sampling_interval_ns": 2.0,
        },
        {"hit_threshold": hits},
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 2


def test_hit_merge_respects_max_total_width():
    plugin = HitMergePlugin()

    # three close hits, but chain width will exceed max_total_width_ns=8
    h1 = _make_hit(10, 10.0, 5.0, 9.0, 11.0, 100_000, 0, 0)
    h2 = _make_hit(14, 12.0, 6.0, 13.0, 15.0, 106_000, 0, 1)
    h3 = _make_hit(18, 14.0, 7.0, 17.0, 19.0, 112_000, 0, 2)
    hits = np.array([h1, h2, h3], dtype=HIT_DTYPE)

    ctx = DummyContext(
        {
            "merge_gap_ns": 10.0,
            "max_total_width_ns": 12.0,
            "sampling_interval_ns": 2.0,
        },
        {"hit_threshold": hits},
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 2


def test_hit_merge_disabled_when_gap_non_positive():
    plugin = HitMergePlugin()

    h1 = _make_hit(10, 20.0, 30.0, 8.0, 12.0, 100_000, 0, 0)
    h2 = _make_hit(14, 25.0, 40.0, 13.0, 16.0, 110_000, 0, 1)
    hits = np.array([h1, h2], dtype=HIT_DTYPE)

    ctx = DummyContext(
        {
            "merge_gap_ns": 0.0,
            "max_total_width_ns": 10000.0,
            "sampling_interval_ns": 2.0,
        },
        {"hit_threshold": hits},
    )

    out = plugin.compute(ctx, "run_001")

    assert len(out) == 2
    np.testing.assert_array_equal(out, hits)
