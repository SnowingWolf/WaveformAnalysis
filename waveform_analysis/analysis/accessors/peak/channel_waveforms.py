"""Peak-channel waveform access methods."""

from ...peak_channel_accessor import PeakChannelAccessor

get_merged_waveform = PeakChannelAccessor._get_merged_waveform
get_channel_waveform_data = PeakChannelAccessor._get_channel_waveform_data

__all__ = ["get_merged_waveform", "get_channel_waveform_data"]
