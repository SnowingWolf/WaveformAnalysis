"""Peak-channel index methods."""

from ...peak_channel_accessor import PeakChannelAccessor

build_feature_indices = PeakChannelAccessor._build_feature_indices
build_waveform_indices = PeakChannelAccessor._build_waveform_indices

__all__ = ["build_feature_indices", "build_waveform_indices"]
