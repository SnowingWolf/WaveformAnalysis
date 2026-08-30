"""Peak summed-waveform access methods."""

from ...peak_channel_accessor import PeakChannelAccessor

load_sum_waveform_layer = PeakChannelAccessor._load_sum_waveform_layer
get_sum_waveform = PeakChannelAccessor.get_sum_waveform

__all__ = ["load_sum_waveform_layer", "get_sum_waveform"]
