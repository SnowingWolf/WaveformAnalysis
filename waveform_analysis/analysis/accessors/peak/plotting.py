"""Peak-channel plotting methods."""

from ...peak_channel_accessor import PeakChannelAccessor

plot = PeakChannelAccessor.plot
plot_stacked = PeakChannelAccessor._plot_stacked
plot_overlay = PeakChannelAccessor._plot_overlay
plot_sum_comparison = PeakChannelAccessor._plot_sum_comparison

__all__ = ["plot", "plot_stacked", "plot_overlay", "plot_sum_comparison"]
