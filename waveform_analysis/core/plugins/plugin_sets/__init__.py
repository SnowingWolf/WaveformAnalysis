"""
Composable plugin sets for building execution profiles.
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)
from waveform_analysis.core.foundation.utils import exporter

export, _exported = exporter()

__all__ = ["PLUGIN_SETS", "get_plugin_set"]

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    "plugins_basic_features": (".basic_features", "plugins_basic_features"),
    "plugins_events": (".event", "plugins_events"),
    "plugins_hit": (".hit", "plugins_hit"),
    "plugins_io": (".io", "plugins_io"),
    "plugins_peaks": (".peaks", "plugins_peaks"),
    "plugins_tabular": (".tabular", "plugins_tabular"),
    "plugins_waveform": (".waveform", "plugins_waveform"),
}


def _plugin_set_factory(name: str):
    export_name = f"plugins_{name}"
    factory = globals().get(export_name)
    if factory is None:
        factory = _resolve_lazy_attribute(export_name, _LAZY_EXPORTS, globals())
    return factory


def _build_plugin_sets() -> dict[str, object]:
    return {
        "io": _plugin_set_factory("io"),
        "waveform": _plugin_set_factory("waveform"),
        "hit": _plugin_set_factory("hit"),
        "peaks": _plugin_set_factory("peaks"),
        "basic_features": _plugin_set_factory("basic_features"),
        "tabular": _plugin_set_factory("tabular"),
        "events": _plugin_set_factory("events"),
    }


@export
def get_plugin_set(name: str):
    """Return a plugin set factory by name."""
    registry = globals().get("PLUGIN_SETS")
    if registry is None:
        registry = __getattr__("PLUGIN_SETS")
    if name not in registry:
        raise KeyError(f"Unknown plugin set: {name}")
    return registry[name]


def __getattr__(name: str):
    if name == "PLUGIN_SETS":
        value = export(_build_plugin_sets(), name="PLUGIN_SETS")
        globals()[name] = value
        return value
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__():
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
