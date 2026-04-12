# DOC: docs/plugins/guides/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Waveform processing.

Contains waveform extraction, optional filtering, and records/wave_pool plugins.

WaveformsPlugin, RecordsPlugin, and WavePoolPlugin must be registered together in the same
plugin set. Their effective relationship is adapter-dependent:

- Non-V1725 adapters, including VX2730: st_waveforms -> records/wave_pool
- V1725 adapter: records/wave_pool keep a dedicated raw_files path and do not
  reuse st_waveforms

Keeping them in one plugin set avoids registration-time confusion when users
switch adapters and helps make the adapter-specific dependency resolution
explicit in one place.
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_waveform():
    """Return waveform+records plugin instances in dependency order.

    Notes:
    - Non-V1725 path, including VX2730: WaveformsPlugin produces
      ``st_waveforms`` and records bundle plugins reuse it to build
      ``records`` + ``wave_pool`` + ``wave_pool_filtered``.
    - V1725 path: records bundle plugins keep their dedicated raw-file path, while
      WaveformsPlugin can still build ``st_waveforms`` independently.
    """
    from waveform_analysis.core.plugins.builtin.cpu.filtering import FilteredWaveformsPlugin
    from waveform_analysis.core.plugins.builtin.cpu.records import (
        RecordsPlugin,
        WavePoolFilteredPlugin,
        WavePoolPlugin,
    )
    from waveform_analysis.core.plugins.builtin.cpu.waveforms import WaveformsPlugin

    return [
        WaveformsPlugin(),
        FilteredWaveformsPlugin(),
        RecordsPlugin(),
        WavePoolPlugin(),
        WavePoolFilteredPlugin(),
    ]
