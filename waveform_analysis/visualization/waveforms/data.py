"""Waveform input normalization shared by renderers."""

import numpy as np

from waveform_analysis.core.hardware.channel import HardwareChannel

from .selectors import parse_channel_selector


def prepare_waveform_channels(waveforms, channels):
    """Return normalized channel order and a channel-to-waveform lookup."""
    if isinstance(waveforms, np.ndarray) and waveforms.dtype.names is not None:
        if "channel" not in waveforms.dtype.names or "board" not in waveforms.dtype.names:
            raise ValueError("waveforms missing 'board'/'channel' fields")
        if channels is None:
            channels = sorted(
                {
                    HardwareChannel(int(board), int(ch))
                    for board, ch in zip(waveforms["board"], waveforms["channel"], strict=False)
                }
            )
        else:
            channels = [parse_channel_selector(channel) for channel in channels]
        waveform_lookup = {
            hw_channel: waveforms[
                (waveforms["board"] == hw_channel.board)
                & (waveforms["channel"] == hw_channel.channel)
            ]
            for hw_channel in channels
        }
        return channels, waveform_lookup
    if isinstance(waveforms, np.ndarray) and waveforms.ndim == 2:
        waveforms = [waveforms]
    if channels is None:
        channels = list(range(len(waveforms)))
    return channels, {channel: waveforms[channel] for channel in channels}
