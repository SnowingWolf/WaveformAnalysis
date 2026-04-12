"""
Shared helper for selecting waveform source paths in CPU plugins.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import numpy as np

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


@dataclass(frozen=True)
class WaveInputSpec:
    source: str
    use_filtered: bool
    data_name: str
    expected_name: str
    depends_on: tuple[str, ...]
    is_records: bool
    wave_pool_name: str | None = None


@dataclass
class LoadedWaveInput:
    spec: WaveInputSpec
    records: np.ndarray | None = None
    waveform_data: np.ndarray | None = None
    records_view: Any | None = None


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
    if source not in (WAVE_SOURCE_AUTO, WAVE_SOURCE_RECORDS) and use_filtered_option in getattr(
        plugin, "options", {}
    ):
        use_filtered = bool(context.get_config(plugin, use_filtered_option))
        if use_filtered:
            logger.warning(
                "Ignoring %s=%s because wave_source=%s explicitly selects data source.",
                plugin.provides,
                use_filtered_option,
                source,
            )
    return source


def resolve_depends_on(
    source: str,
    use_filtered: bool,
    *,
    needs_wave_samples: bool = True,
) -> list[str]:
    # Dynamic dependency mapping for waveform-consuming plugins:
    # - explicit wave_source wins
    # - otherwise auto mode falls back to filtered_waveforms when use_filtered
    #   is true, or st_waveforms when it is false
    if source == WAVE_SOURCE_RECORDS:
        if not needs_wave_samples:
            return [WAVE_SOURCE_RECORDS]
        return [WAVE_SOURCE_RECORDS, "wave_pool_filtered" if use_filtered else "wave_pool"]
    if source == WAVE_SOURCE_ST:
        return [WAVE_SOURCE_ST]
    if source == WAVE_SOURCE_FILTERED:
        return [WAVE_SOURCE_FILTERED]
    return [WAVE_SOURCE_FILTERED] if use_filtered else [WAVE_SOURCE_ST]


def resolve_wave_input_spec(
    context: Any,
    plugin: Any,
    *,
    use_filtered_option: str = "use_filtered",
    needs_wave_samples: bool = True,
) -> WaveInputSpec:
    source = resolve_wave_source(context, plugin, use_filtered_option=use_filtered_option)
    use_filtered = False
    if use_filtered_option in getattr(plugin, "options", {}):
        use_filtered = bool(context.get_config(plugin, use_filtered_option))

    depends_on = tuple(
        resolve_depends_on(source, use_filtered, needs_wave_samples=needs_wave_samples)
    )
    if source == WAVE_SOURCE_RECORDS:
        return WaveInputSpec(
            source=source,
            use_filtered=use_filtered,
            data_name=WAVE_SOURCE_RECORDS,
            expected_name=WAVE_SOURCE_RECORDS,
            depends_on=depends_on,
            is_records=True,
            wave_pool_name="wave_pool_filtered" if use_filtered else "wave_pool",
        )
    if source == WAVE_SOURCE_ST:
        return WaveInputSpec(
            source=source,
            use_filtered=use_filtered,
            data_name=WAVE_SOURCE_ST,
            expected_name=WAVE_SOURCE_ST,
            depends_on=depends_on,
            is_records=False,
        )
    if source == WAVE_SOURCE_FILTERED:
        return WaveInputSpec(
            source=source,
            use_filtered=use_filtered,
            data_name=WAVE_SOURCE_FILTERED,
            expected_name=WAVE_SOURCE_FILTERED,
            depends_on=depends_on,
            is_records=False,
        )
    auto_data_name = WAVE_SOURCE_FILTERED if use_filtered else WAVE_SOURCE_ST
    return WaveInputSpec(
        source=source,
        use_filtered=use_filtered,
        data_name=auto_data_name,
        expected_name=auto_data_name,
        depends_on=depends_on,
        is_records=False,
    )


def load_wave_input(
    context: Any,
    plugin: Any,
    run_id: str,
    *,
    use_filtered_option: str = "use_filtered",
    needs_wave_samples: bool = True,
) -> LoadedWaveInput:
    spec = resolve_wave_input_spec(
        context,
        plugin,
        use_filtered_option=use_filtered_option,
        needs_wave_samples=needs_wave_samples,
    )
    if spec.is_records:
        if needs_wave_samples:
            from waveform_analysis.core import records_view

            rv = records_view(context, run_id, wave_pool_name=spec.wave_pool_name or "wave_pool")
            return LoadedWaveInput(spec=spec, records=rv.records, records_view=rv)

        records = context.get_data(run_id, WAVE_SOURCE_RECORDS)
        if not isinstance(records, np.ndarray):
            raise ValueError(
                f"{plugin.provides} expects {WAVE_SOURCE_RECORDS} as a single structured array"
            )
        return LoadedWaveInput(spec=spec, records=records)

    waveform_data = context.get_data(run_id, spec.data_name)
    if not isinstance(waveform_data, np.ndarray):
        raise ValueError(
            f"{plugin.provides} expects {spec.expected_name} as a single structured array"
        )
    return LoadedWaveInput(spec=spec, waveform_data=waveform_data)
