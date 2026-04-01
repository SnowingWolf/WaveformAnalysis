"""
Composable plugin sets for building execution profiles.
"""

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()

from .basic_features import plugins_basic_features
from .events import plugins_events
from .io import plugins_io
from .peaks import plugins_peaks
from .tabular import plugins_tabular
from .waveform import plugins_waveform

PLUGIN_SETS = export(
    {
        "io": plugins_io,
        "waveform": plugins_waveform,
        "basic_features": plugins_basic_features,
        "tabular": plugins_tabular,
        "events": plugins_events,
        "peaks": plugins_peaks,
    },
    name="PLUGIN_SETS",
)


@export
def get_plugin_set(name: str):
    """Return a plugin set factory by name."""
    if name not in PLUGIN_SETS:
        raise KeyError(f"Unknown plugin set: {name}")
    return PLUGIN_SETS[name]
