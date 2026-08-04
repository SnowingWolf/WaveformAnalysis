# DOC: docs/plugins/guides/PLUGIN_SET_PROFILE_GUIDE.md#plugin-sets
"""
Plugin set: Tabular outputs (DataFrame, tables).
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
def plugins_tabular():
    """Return tabular output plugin instances in dependency order."""
    from waveform_analysis.core.plugins.builtin.cpu.dataframe import DataFramePlugin
    from waveform_analysis.core.plugins.builtin.df_events import GroupedEventsPlugin
    from waveform_analysis.core.plugins.builtin.df_paired import PairedEventsPlugin

    return [
        DataFramePlugin(),
        GroupedEventsPlugin(),
        PairedEventsPlugin(),
    ]
