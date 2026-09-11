"""Backward-compatible shim. Implementation moved to :mod:`waveform_analysis.core.plugins.builtin.peaklet_channels`."""

from waveform_analysis.core.plugins.builtin.peaklet_channels import (  # noqa: F401
    PEAKLET_CHANNELS_DTYPE,
    PeakletChannelsPlugin,
)

__all__ = ["PEAKLET_CHANNELS_DTYPE", "PeakletChannelsPlugin"]
