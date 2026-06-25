import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import HIT_MERGED_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.hit_merged_features import (
    HIT_MERGED_FEATURES_DTYPE,
)
from waveform_analysis.core.plugins.builtin.cpu.peaklet_channels import (
    PEAKLET_CHANNELS_DTYPE,
)
from waveform_analysis.core.plugins.builtin.cpu.peaklets import PEAKLET_COMPONENTS_DTYPE
from waveform_analysis.utils.peak_channel_accessor import PeakChannelAccessor


def test_get_peak_channels_uses_peaklet_channels_aggregates():
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

    channels = PeakChannelAccessor(ctx, "run").get_peak_channels(peak_id=919)

    assert len(channels) == 2
    by_channel = {row["channel"]: row for row in channels}
    assert by_channel[5]["area"] == 30.0
    assert by_channel[5]["height"] == 8.0
    assert by_channel[5]["n_hits"] == 3
    assert by_channel[5]["merged_indices"] == [0, 1]
    assert by_channel[7]["area"] == 40.0
