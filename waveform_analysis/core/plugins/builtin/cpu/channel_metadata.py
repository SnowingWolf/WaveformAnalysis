"""Backward-compatible wrapper around hardware channel metadata helpers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from waveform_analysis.core.hardware.channel import (
    HardwareChannel,
    get_channel_metadata_config,
    resolve_channel_metadata_map,
)


def resolve_channel_metadata(
    channel_metadata: Any,
    run_id: str,
    channels: Iterable[tuple[int, int] | HardwareChannel],
    plugin_name: str,
) -> dict[Any, dict[str, Any]]:
    """Resolve metadata and expose the historical dict-of-dict shape."""
    normalized_channels = []
    for item in channels:
        if isinstance(item, HardwareChannel):
            normalized_channels.append(item)
        elif isinstance(item, tuple) and len(item) == 2:
            normalized_channels.append(HardwareChannel(int(item[0]), int(item[1])))
        else:
            raise ValueError(
                f"Invalid hardware channel selector {item!r}; expected HardwareChannel or "
                "(board, channel)."
            )

    configs = resolve_channel_metadata_map(
        channel_metadata=channel_metadata,
        channels=normalized_channels,
    )

    result: dict[Any, dict[str, Any]] = {}
    for hw_channel, config in configs.items():
        key: Any = hw_channel
        result[key] = {
            "polarity": config.polarity,
            "geometry": config.geometry,
            "adc_bits": config.adc_bits,
        }
    return result


def resolve_context_channel_metadata(
    context: Any,
    run_id: str,
    channels: Iterable[tuple[int, int] | HardwareChannel],
) -> dict[Any, dict[str, Any]]:
    """Resolve merged top-level channel_metadata for a run."""
    return resolve_channel_metadata(
        channel_metadata=get_channel_metadata_config(context, run_id),
        run_id=run_id,
        channels=channels,
        plugin_name="channel_metadata",
    )
