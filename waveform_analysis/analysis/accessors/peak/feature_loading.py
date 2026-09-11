"""Peak-channel feature loading and validation."""

from typing import Any

import numpy as np

REQUIRED_PEAKLET_CHANNEL_FIELDS = frozenset(
    {
        "peaklet_id",
        "board",
        "channel",
        "area",
        "height",
        "n_hits",
        "area_fraction",
    }
)


def load_peaklet_channels(
    context: Any,
    run_id: str,
    unavailable_error: type[Exception],
) -> np.ndarray:
    """Load and validate the canonical per-channel aggregation product."""
    try:
        peaklet_channels = context.get_data(run_id, "peaklet_channels")
    except Exception as error:
        raise unavailable_error(
            "PeakChannelAccessor requires the 'peaklet_channels' product. "
            "Register PeakletChannelsPlugin and regenerate this run."
        ) from error
    names = (
        set(peaklet_channels.dtype.names or ())
        if isinstance(peaklet_channels, np.ndarray)
        else set()
    )
    if not isinstance(peaklet_channels, np.ndarray) or not REQUIRED_PEAKLET_CHANNEL_FIELDS.issubset(
        names
    ):
        missing_fields = sorted(REQUIRED_PEAKLET_CHANNEL_FIELDS - names)
        detail = f" Missing fields: {', '.join(missing_fields)}." if missing_fields else ""
        raise unavailable_error(
            "PeakChannelAccessor requires 'peaklet_channels' as a structured array with the "
            f"canonical per-channel fields.{detail} Regenerate the product with PeakletChannelsPlugin."
        )
    return peaklet_channels
