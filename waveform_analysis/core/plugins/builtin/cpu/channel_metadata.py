"""Legacy compatibility helpers for channel_metadata lookup."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict

from waveform_analysis.core.hardware.channel import (
    HardwareChannel,
    get_channel_metadata_config,
    resolve_channel_metadata_map,
)


def _normalize_channels(
    channels: Iterable[HardwareChannel | tuple[int, int]],
) -> list[HardwareChannel]:
    normalized: list[HardwareChannel] = []
    for item in channels:
        if isinstance(item, HardwareChannel):
            normalized.append(item)
            continue
        board, channel = item
        normalized.append(HardwareChannel(int(board), int(channel)))
    return normalized


def resolve_channel_metadata(
    channel_metadata,
    run_id: str,
    channels: Iterable[HardwareChannel | tuple[int, int]],
    plugin_name: str | None = None,
) -> dict[HardwareChannel, dict[str, object]]:
    """Return legacy dict-shaped channel metadata for the given channels."""
    del run_id, plugin_name
    resolved = resolve_channel_metadata_map(
        channel_metadata=channel_metadata,
        channels=_normalize_channels(channels),
    )
    return {hw_channel: asdict(metadata) for hw_channel, metadata in resolved.items()}


def resolve_context_channel_metadata(
    context,
    run_id: str,
    channels: Iterable[HardwareChannel | tuple[int, int]],
) -> dict[HardwareChannel, dict[str, object]]:
    """Resolve top-level context/run channel_metadata using the legacy dict shape."""
    return resolve_channel_metadata(
        get_channel_metadata_config(context, run_id),
        run_id,
        channels,
        plugin_name=None,
    )
