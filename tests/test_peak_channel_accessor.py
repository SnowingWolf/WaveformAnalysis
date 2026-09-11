import numpy as np
import pandas as pd

from tests.utils import DummyContext, make_records
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
)
from waveform_analysis.core.plugins.builtin.hit.hit_merged_features import (
    HIT_MERGED_FEATURES_DTYPE,
)
from waveform_analysis.core.plugins.builtin.peaks.peaklet_channels import (
    PEAKLET_CHANNELS_DTYPE,
)
from waveform_analysis.core.plugins.builtin.peaks.peaklets import (
    PEAKLET_COMPONENTS_DTYPE,
    PEAKLET_WAVEFORMS_DTYPE,
)
from waveform_analysis.utils.peak_channel_accessor import (
    PeakChannelAccessor,
    PeakChannelDataUnavailableError,
    WaveformOverlapConflictError,
)
from waveform_analysis.utils.query_helpers import get_hits_for_merged, get_hits_for_peak


def test_hit_queries_reuse_helper_contract_without_loading_features_or_waveforms():
    class CountingContext(DummyContext):
        def __init__(self, data):
            super().__init__(data=data)
            self.calls = []

        def get_data(self, run_id, name, **kwargs):
            self.calls.append(name)
            return super().get_data(run_id, name, **kwargs)

    peaklet_components = np.zeros(2, dtype=PEAKLET_COMPONENTS_DTYPE)
    peaklet_components["peak_id"] = [919, 919]
    peaklet_components["merged_index"] = [7, 8]

    merged_components = np.zeros(3, dtype=HIT_MERGED_COMPONENTS_DTYPE)
    merged_components["merged_index"] = [7, 7, 8]
    merged_components["hit_index"] = [0, 1, 2]

    hit_threshold = np.zeros(3, dtype=THRESHOLD_HIT_DTYPE)
    hit_threshold["position"] = [5, 2, 1]
    hit_threshold["edge_start"] = [4, 1, 0]
    hit_threshold["edge_end"] = [7, 4, 3]
    hit_threshold["width"] = [3, 3, 3]
    hit_threshold["dt"] = [2, 2, 2]
    hit_threshold["timestamp"] = [20_000, 10_000, 30_000]
    hit_threshold["board"] = [0, 0, 1]
    hit_threshold["channel"] = [5, 6, 2]
    hit_threshold["record_id"] = [100, 101, 102]

    ctx = CountingContext(
        data={
            "peaklet_components": peaklet_components,
            "hit_merged_components": merged_components,
            "hit_threshold": hit_threshold,
        }
    )
    accessor = PeakChannelAccessor(ctx, "run", lazy_load=True)

    actual_peak = accessor.get_hits(peak_id=919)
    expected_peak = get_hits_for_peak(
        peak_id=919,
        peaklet_components=peaklet_components,
        hit_merged_components=merged_components,
        hit_threshold=hit_threshold,
    )
    pd.testing.assert_frame_equal(actual_peak, expected_peak)

    actual_merged = accessor.get_merged_hits(merged_index=7)
    expected_merged = get_hits_for_merged(7, merged_components, hit_threshold)
    pd.testing.assert_frame_equal(actual_merged, expected_merged)
    assert accessor.get_hits(peak_id=999).empty
    assert accessor.get_merged_hits(merged_index=999).empty

    assert ctx.calls == ["peaklet_components", "hit_merged_components", "hit_threshold"]
    assert not {
        "peaklet_channels",
        "hit_merged",
        "hit_merged_features",
        "records",
        "wave_pool",
        "wave_pool_filtered",
    }.intersection(ctx.calls)


def test_hit_query_layer_reuses_eagerly_loaded_peaklet_components():
    class CountingContext(DummyContext):
        def __init__(self, data):
            super().__init__(data=data)
            self.calls = []

        def get_data(self, run_id, name, **kwargs):
            self.calls.append(name)
            return super().get_data(run_id, name, **kwargs)

    ctx = CountingContext(
        data={
            "peaklet_components": np.zeros(0, dtype=PEAKLET_COMPONENTS_DTYPE),
            "peaklet_channels": np.zeros(0, dtype=PEAKLET_CHANNELS_DTYPE),
            "hit_merged": np.zeros(0, dtype=HIT_MERGED_DTYPE),
            "hit_merged_features": np.zeros(0, dtype=HIT_MERGED_FEATURES_DTYPE),
            "hit_merged_components": np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE),
            "hit_threshold": np.zeros(0, dtype=THRESHOLD_HIT_DTYPE),
        }
    )

    accessor = PeakChannelAccessor(ctx, "run")
    result = accessor.get_hits(peak_id=919)

    assert result.empty
    assert ctx.calls.count("peaklet_components") == 1
    assert ctx.calls.count("hit_merged_components") == 1
    assert ctx.calls.count("hit_threshold") == 1


def test_feature_layer_reuses_hit_query_peaklet_components():
    class CountingContext(DummyContext):
        def __init__(self, data):
            super().__init__(data=data)
            self.calls = []

        def get_data(self, run_id, name, **kwargs):
            self.calls.append(name)
            return super().get_data(run_id, name, **kwargs)

    ctx = CountingContext(
        data={
            "peaklet_components": np.zeros(0, dtype=PEAKLET_COMPONENTS_DTYPE),
            "peaklet_channels": np.zeros(0, dtype=PEAKLET_CHANNELS_DTYPE),
            "hit_merged": np.zeros(0, dtype=HIT_MERGED_DTYPE),
            "hit_merged_features": np.zeros(0, dtype=HIT_MERGED_FEATURES_DTYPE),
            "hit_merged_components": np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE),
            "hit_threshold": np.zeros(0, dtype=THRESHOLD_HIT_DTYPE),
        }
    )

    accessor = PeakChannelAccessor(ctx, "run", lazy_load=True)
    accessor.get_hits(peak_id=919)
    assert accessor.get_channels(peak_id=919) == []

    assert ctx.calls.count("peaklet_components") == 1


def test_get_channels_uses_peaklet_channels_aggregates():
    peaklet_components = np.zeros(3, dtype=PEAKLET_COMPONENTS_DTYPE)
    peaklet_components["peak_id"] = [919, 919, 919]
    peaklet_components["merged_index"] = [0, 1, 2]

    hit_merged = np.zeros(3, dtype=HIT_MERGED_DTYPE)
    hit_merged["board"] = [0, 0, 0]
    hit_merged["channel"] = [5, 5, 7]
    hit_merged["sample_start"] = [10, 20, 30]
    hit_merged["sample_end"] = [15, 25, 35]
    hit_merged["record_id"] = [100, 101, 102]
    hit_merged["is_single_record"] = True

    hit_merged_features = np.zeros(3, dtype=HIT_MERGED_FEATURES_DTYPE)
    hit_merged_features["merged_index"] = [0, 1, 2]
    hit_merged_features["board"] = [0, 0, 0]
    hit_merged_features["channel"] = [5, 5, 7]
    hit_merged_features["area"] = [10.0, 20.0, 40.0]
    hit_merged_features["height"] = [4.0, 8.0, 12.0]
    hit_merged_features["width"] = [5.0, 6.0, 7.0]
    hit_merged_features["rise_time"] = [1.0, 2.0, 3.0]
    hit_merged_features["fall_time"] = [1.5, 2.5, 3.5]
    hit_merged_features["center_time"] = [1000, 2000, 3000]

    peaklet_channels = np.zeros(2, dtype=PEAKLET_CHANNELS_DTYPE)
    peaklet_channels["peaklet_id"] = [919, 919]
    peaklet_channels["board"] = [0, 0]
    peaklet_channels["channel"] = [5, 7]
    peaklet_channels["area"] = [30.0, 40.0]
    peaklet_channels["height"] = [8.0, 12.0]
    peaklet_channels["n_hits"] = [3, 1]
    peaklet_channels["area_fraction"] = [0.42857143, 0.57142857]

    ctx = DummyContext(
        data={
            "peaklet_components": peaklet_components,
            "peaklet_channels": peaklet_channels,
            "hit_merged": hit_merged,
            "hit_merged_features": hit_merged_features,
        }
    )

    channels = PeakChannelAccessor(ctx, "run").get_channels(peak_id=919)

    assert len(channels) == 2
    by_channel = {row["channel"]: row for row in channels}
    assert by_channel[5]["area"] == 30.0
    assert by_channel[5]["height"] == 8.0
    assert by_channel[5]["n_hits"] == 3
    assert by_channel[5]["merged_indices"] == [0, 1]
    assert by_channel[7]["area"] == 40.0


def test_get_channels_combines_all_channel_merged_waveforms():
    peaklet_components = np.zeros(2, dtype=PEAKLET_COMPONENTS_DTYPE)
    peaklet_components["peak_id"] = [919, 919]
    peaklet_components["merged_index"] = [0, 1]

    hit_merged = np.zeros(2, dtype=HIT_MERGED_DTYPE)
    hit_merged["board"] = [0, 0]
    hit_merged["channel"] = [5, 5]
    hit_merged["sample_start"] = [1, 1]
    hit_merged["sample_end"] = [3, 3]
    hit_merged["record_id"] = [0, 1]
    hit_merged["is_single_record"] = True

    hit_merged_features = np.zeros(2, dtype=HIT_MERGED_FEATURES_DTYPE)
    hit_merged_features["merged_index"] = [0, 1]
    hit_merged_features["board"] = [0, 0]
    hit_merged_features["channel"] = [5, 5]
    hit_merged_features["height"] = [20.0, 40.0]

    peaklet_channels = np.zeros(1, dtype=PEAKLET_CHANNELS_DTYPE)
    peaklet_channels["peaklet_id"] = [919]
    peaklet_channels["board"] = [0]
    peaklet_channels["channel"] = [5]
    peaklet_channels["area"] = [60.0]
    peaklet_channels["height"] = [40.0]
    peaklet_channels["n_hits"] = [2]
    peaklet_channels["area_fraction"] = [1.0]

    records = make_records(2, event_length=4, baseline=100.0, dt=1)
    records["timestamp"] = [100_000, 0]
    records["channel"] = [5, 5]
    wave_pool = np.array([100, 90, 80, 100, 100, 70, 60, 100], dtype=np.uint16)

    ctx = DummyContext(
        data={
            "peaklet_components": peaklet_components,
            "peaklet_channels": peaklet_channels,
            "hit_merged": hit_merged,
            "hit_merged_features": hit_merged_features,
            "records": records,
            "hit_threshold": np.zeros(0, dtype=THRESHOLD_HIT_DTYPE),
            "hit_merged_components": np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE),
            "wave_pool": wave_pool,
        }
    )

    accessor = PeakChannelAccessor(ctx, "run")
    channels = accessor.get_channels(peak_id=919, include_waveforms=True, pad=0)

    assert len(channels) == 1
    channel = channels[0]
    assert channel["merged_indices"] == [0, 1]
    assert [seg["merged_index"] for seg in channel["segments"]] == [1, 0]
    np.testing.assert_array_equal(channel["waveform"], np.array([30, 40, 10, 20]))

    repeated = accessor.get_channels(peak_id=919, include_waveforms=True, pad=0)
    assert repeated[0]["waveform"] is channel["waveform"]
    assert len(accessor._channel_waveform_cache) == 1

    accessor.clear_waveform_cache()
    assert accessor._channel_waveform_cache == {}


def test_get_channels_deduplicates_equal_absolute_samples_and_rejects_conflicts():
    peaklet_components = np.zeros(2, dtype=PEAKLET_COMPONENTS_DTYPE)
    peaklet_components["peak_id"] = [919, 919]
    peaklet_components["merged_index"] = [0, 1]

    hit_merged = np.zeros(2, dtype=HIT_MERGED_DTYPE)
    hit_merged["board"] = 0
    hit_merged["channel"] = 5
    hit_merged["sample_start"] = 1
    hit_merged["sample_end"] = 3
    hit_merged["record_id"] = [0, 1]
    hit_merged["is_single_record"] = True

    features = np.zeros(2, dtype=HIT_MERGED_FEATURES_DTYPE)
    features["merged_index"] = [0, 1]
    features["board"] = 0
    features["channel"] = 5
    features["height"] = 20.0

    channel_rows = np.zeros(1, dtype=PEAKLET_CHANNELS_DTYPE)
    channel_rows["peaklet_id"] = 919
    channel_rows["board"] = 0
    channel_rows["channel"] = 5
    channel_rows["area"] = 30.0
    channel_rows["height"] = 20.0
    channel_rows["n_hits"] = 2
    channel_rows["area_fraction"] = 1.0

    records = make_records(2, event_length=4, baseline=100.0, dt=1)
    records["timestamp"] = [0, 0]
    records["channel"] = [5, 5]
    wave_pool = np.array([100, 90, 80, 100, 100, 90, 80, 100], dtype=np.uint16)
    ctx = DummyContext(
        data={
            "peaklet_components": peaklet_components,
            "peaklet_channels": channel_rows,
            "hit_merged": hit_merged,
            "hit_merged_features": features,
            "records": records,
            "hit_threshold": np.zeros(0, dtype=THRESHOLD_HIT_DTYPE),
            "hit_merged_components": np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE),
            "wave_pool": wave_pool,
        }
    )

    channel = PeakChannelAccessor(ctx, "run").get_channels(
        peak_id=919, include_waveforms=True, pad=0
    )[0]
    np.testing.assert_array_equal(channel["waveform"], np.array([10, 20], dtype=np.float32))
    np.testing.assert_array_equal(channel["abs_time_ps"], np.array([1000, 2000]))
    assert channel["waveform_area"] == 30.0

    wave_pool[5] = 89
    conflict_accessor = PeakChannelAccessor(ctx, "run")
    with np.testing.assert_raises_regex(WaveformOverlapConflictError, "conflicting overlap"):
        conflict_accessor.get_channels(peak_id=919, include_waveforms=True, pad=0)


def test_get_sum_waveform_loads_and_indexes_layer_once():
    class CountingContext(DummyContext):
        def __init__(self, data):
            super().__init__(data=data)
            self.calls = {}

        def get_data(self, run_id, name, **kwargs):
            self.calls[name] = self.calls.get(name, 0) + 1
            return super().get_data(run_id, name, **kwargs)

    peaklet_waveforms = np.zeros(2, dtype=PEAKLET_WAVEFORMS_DTYPE)
    peaklet_waveforms["peak_id"] = [20, 10]
    peaklet_waveforms["time_start"] = [1_000, 2_000]
    peaklet_waveforms["time_end"] = [5_000, 8_000]
    peaklet_waveforms["dt"] = [2, 2]
    peaklet_waveforms["wave_offset"] = [0, 2]
    peaklet_waveforms["wave_length"] = [2, 3]
    peaklet_waveform_pool = np.array([1, 2, 3, 4, 5], dtype=np.float32)

    ctx = CountingContext(
        data={
            "peaklet_components": np.zeros(0, dtype=PEAKLET_COMPONENTS_DTYPE),
            "peaklet_channels": np.zeros(0, dtype=PEAKLET_CHANNELS_DTYPE),
            "hit_merged": np.zeros(0, dtype=HIT_MERGED_DTYPE),
            "hit_merged_features": np.zeros(0, dtype=HIT_MERGED_FEATURES_DTYPE),
            "peaklet_waveforms": peaklet_waveforms,
            "peaklet_waveform_pool": peaklet_waveform_pool,
        }
    )
    accessor = PeakChannelAccessor(ctx, "run")

    first = accessor.get_sum_waveform(peak_id=10)
    repeated = accessor.get_sum_waveform(peak_id=10)

    np.testing.assert_array_equal(first["waveform"], np.array([3, 4, 5], dtype=np.float32))
    np.testing.assert_array_equal(first["time_ns"], np.array([0, 2, 4]))
    assert np.shares_memory(repeated["waveform"], first["waveform"])
    assert ctx.calls["peaklet_waveforms"] == 1
    assert ctx.calls["peaklet_waveform_pool"] == 1
    assert accessor.get_sum_waveform(peak_id=999) is None

    accessor.clear_waveform_cache(release_wave_pool=True)
    accessor.get_sum_waveform(peak_id=10)
    assert ctx.calls["peaklet_waveforms"] == 2
    assert ctx.calls["peaklet_waveform_pool"] == 2


def test_get_channels_requires_complete_peaklet_channels():
    ctx = DummyContext(
        data={
            "peaklet_components": np.zeros(0, dtype=PEAKLET_COMPONENTS_DTYPE),
            "hit_merged": np.zeros(0, dtype=HIT_MERGED_DTYPE),
            "hit_merged_features": np.zeros(0, dtype=HIT_MERGED_FEATURES_DTYPE),
        }
    )

    with np.testing.assert_raises_regex(
        PeakChannelDataUnavailableError, "requires 'peaklet_channels' as a structured array"
    ):
        PeakChannelAccessor(ctx, "run")


def test_plot_dispatches_views_and_normalizes_overlay_axes():
    accessor = PeakChannelAccessor.__new__(PeakChannelAccessor)
    stacked_axes = np.asarray([object()])
    comparison_axes = np.asarray([object(), object()])
    overlay_ax = object()
    accessor._plot_stacked = lambda *args, **kwargs: ("stacked", stacked_axes)
    accessor._plot_overlay = lambda *args, **kwargs: ("overlay", overlay_ax)
    accessor._plot_sum_comparison = lambda *args, **kwargs: ("comparison", comparison_axes)

    fig, axes = accessor.plot(919, view="stacked")
    assert fig == "stacked"
    assert axes is stacked_axes
    fig, axes = accessor.plot(919, view="overlay", channel_filter=lambda _channel: True)
    assert fig == "overlay"
    assert axes.shape == (1,)
    assert axes[0] is overlay_ax
    fig, axes = accessor.plot(919, view="sum-comparison")
    assert fig == "comparison"
    assert axes is comparison_axes
    with np.testing.assert_raises_regex(ValueError, "view must be one of"):
        accessor.plot(919, view="unknown")


def test_legacy_public_methods_are_removed():
    for name in (
        "get_peak_channels",
        "get_channel_waveform",
        "get_peak_channel_data",
        "batch_plot",
        "plot_channel_comparison",
        "plot_sum_vs_channels",
    ):
        assert not hasattr(PeakChannelAccessor, name)


def test_plot_waveform_segments_plots_each_segment_separately():
    class DummyAxes:
        def __init__(self):
            self.calls = []

        def plot(self, time_ns, waveform, **kwargs):
            self.calls.append((np.asarray(time_ns), np.asarray(waveform), kwargs))

    ax = DummyAxes()
    segments = [
        {
            "abs_time_ps": np.array([0, 1000], dtype=np.int64),
            "waveform": np.array([1.0, 2.0], dtype=np.float32),
        },
        {
            "abs_time_ps": np.array([10_000, 11_000], dtype=np.int64),
            "waveform": np.array([3.0, 4.0], dtype=np.float32),
        },
    ]

    PeakChannelAccessor._plot_waveform_segments(
        ax, segments, event_t0=0, color="C0", lw=1.2, label="ch"
    )

    assert len(ax.calls) == 2
    assert ax.calls[0][2]["label"] == "ch"
    assert ax.calls[1][2]["label"] is None
    np.testing.assert_array_equal(ax.calls[0][0], np.array([0.0, 1.0]))
    np.testing.assert_array_equal(ax.calls[1][0], np.array([10.0, 11.0]))
