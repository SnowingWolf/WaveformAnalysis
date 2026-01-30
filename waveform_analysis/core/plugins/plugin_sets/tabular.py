# -*- coding: utf-8 -*-
# DOC: docs/features/plugin/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Tabular outputs (DataFrame, tables).
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_tabular():
    """Return tabular output plugin instances in dependency order."""
    from waveform_analysis.core.plugins.builtin.cpu.dataframe import DataFramePlugin

    return [
        DataFramePlugin(),
    ]
