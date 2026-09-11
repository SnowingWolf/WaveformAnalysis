"""Backward-compatible shim. Implementation moved to builtin.shared.wave_source."""

from waveform_analysis.core.plugins.builtin.shared.wave_source import (
    WAVE_SOURCE_AUTO,
    WAVE_SOURCE_FILTERED,
    WAVE_SOURCE_RECORDS,
    WAVE_SOURCE_ST,
    WAVE_SOURCES,
    LoadedWaveInput,
    WaveInputSpec,
    load_wave_input,
    normalize_wave_source,
    resolve_depends_on,
    resolve_wave_input_spec,
    resolve_wave_source,
)

__all__ = [
    "WAVE_SOURCE_AUTO",
    "WAVE_SOURCE_RECORDS",
    "WAVE_SOURCE_ST",
    "WAVE_SOURCE_FILTERED",
    "WAVE_SOURCES",
    "WaveInputSpec",
    "LoadedWaveInput",
    "normalize_wave_source",
    "resolve_wave_source",
    "resolve_depends_on",
    "resolve_wave_input_spec",
    "load_wave_input",
]
