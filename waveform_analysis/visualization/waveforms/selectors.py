"""Hardware-channel selector parsing and labels."""

from waveform_analysis.core.hardware.channel import HardwareChannel


def parse_channel_selector(
    channel: HardwareChannel | tuple[int, int] | str,
) -> HardwareChannel:
    if isinstance(channel, HardwareChannel):
        return channel
    if isinstance(channel, tuple) and len(channel) == 2:
        return HardwareChannel(int(channel[0]), int(channel[1]))
    if isinstance(channel, str) and ":" in channel:
        board, ch = channel.split(":", 1)
        return HardwareChannel(int(board.strip()), int(ch.strip()))
    raise ValueError(
        f"Invalid channel selector {channel!r}; expected HardwareChannel, (board, channel), "
        'or "board:channel".'
    )


def channel_label(channel: HardwareChannel) -> str:
    return f"B{channel.board}:Ch{channel.channel}"
