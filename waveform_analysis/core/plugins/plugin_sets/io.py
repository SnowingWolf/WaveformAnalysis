# -*- coding: utf-8 -*-
# DOC: docs/features/plugin/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: IO.

Contains plugins responsible for discovering raw input files.
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_io():
    """Return IO plugin instances in dependency order."""
    from waveform_analysis.core.plugins.builtin.cpu.raw_files import RawFileNamesPlugin

    return [
        RawFileNamesPlugin(),
    ]
