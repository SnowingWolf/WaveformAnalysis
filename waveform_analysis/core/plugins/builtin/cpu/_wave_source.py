"""
Shared helper for selecting waveform source paths in CPU plugins.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

WAVE_SOURCE_AUTO = "auto"
WAVE_SOURCE_RECORDS = "records"
WAVE_SOURCE_ST = "st_waveforms"
WAVE_SOURCE_FILTERED = "filtered_waveforms"

WAVE_SOURCES = {
    WAVE_SOURCE_AUTO,
    WAVE_SOURCE_RECORDS,
    WAVE_SOURCE_ST,
    WAVE_SOURCE_FILTERED,
}


def normalize_wave_source(value: Any) -> str:
    if value is None:
        return WAVE_SOURCE_AUTO
    source = str(value).strip().lower()
    if source not in WAVE_SOURCES:
        raise ValueError(f"Invalid wave_source: {value!r}. Expected one of {sorted(WAVE_SOURCES)}.")
    return source


def resolve_wave_source(
    context: Any, plugin: Any, use_filtered_option: str = "use_filtered"
) -> str:
    source = normalize_wave_source(context.get_config(plugin, "wave_source"))
    if source != WAVE_SOURCE_AUTO and use_filtered_option in getattr(plugin, "options", {}):
        use_filtered = bool(context.get_config(plugin, use_filtered_option))
        if use_filtered:
            logger.warning(
                "Ignoring %s=%s because wave_source=%s explicitly selects data source.",
                plugin.provides,
                use_filtered_option,
                source,
            )
    return source


def resolve_depends_on(source: str, use_filtered: bool) -> list[str]:
    # Dynamic dependency mapping for waveform-consuming plugins:
    # - explicit wave_source wins
    # - otherwise auto mode falls back to filtered_waveforms when use_filtered
    #   is true, or st_waveforms when it is false
    if source == WAVE_SOURCE_RECORDS:
        return [WAVE_SOURCE_RECORDS]
    if source == WAVE_SOURCE_ST:
        return [WAVE_SOURCE_ST]
    if source == WAVE_SOURCE_FILTERED:
        return [WAVE_SOURCE_FILTERED]
    return [WAVE_SOURCE_FILTERED] if use_filtered else [WAVE_SOURCE_ST]
