# DOC: docs/plugins/PLUGIN_SYSTEM_OVERVIEW.md#profiles
"""
Execution profiles composed from plugin sets.
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)
from waveform_analysis.core.foundation.utils import exporter

export, _exported = exporter()

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    "plugins_basic_features": (".plugin_sets.basic_features", "plugins_basic_features"),
    "plugins_events": (".plugin_sets.event", "plugins_events"),
    "plugins_hit": (".plugin_sets.hit", "plugins_hit"),
    "plugins_io": (".plugin_sets.io", "plugins_io"),
    "plugins_peaks": (".plugin_sets.peaks", "plugins_peaks"),
    "plugins_tabular": (".plugin_sets.tabular", "plugins_tabular"),
    "plugins_waveform": (".plugin_sets.waveform", "plugins_waveform"),
}


def _plugin_set_factory(name: str):
    export_name = f"plugins_{name}"
    factory = globals().get(export_name)
    if factory is None:
        factory = _resolve_lazy_attribute(export_name, _LAZY_EXPORTS, globals())
    return factory


@export
def cpu_default():
    """Default CPU profile (core pipeline)."""
    return (
        _plugin_set_factory("io")()
        + _plugin_set_factory("waveform")()
        + _plugin_set_factory("hit")()
        + _plugin_set_factory("peaks")()
        + _plugin_set_factory("basic_features")()
        + _plugin_set_factory("tabular")()
        + _plugin_set_factory("events")()
    )


@export
def streaming_default():
    """Placeholder for a streaming profile."""
    raise NotImplementedError("Streaming profile is not available yet. Use cpu_default() for now.")


@export
def jax_accel():
    """Placeholder for a JAX-accelerated profile."""
    raise NotImplementedError("JAX profile is not available yet. Use cpu_default() for now.")


PROFILES = export(
    {
        "cpu": cpu_default,
        "cpu_default": cpu_default,
        "streaming": streaming_default,
        "streaming_default": streaming_default,
        "jax": jax_accel,
        "jax_accel": jax_accel,
    },
    name="PROFILES",
)


@export
def get_profile(name: str):
    """Return a profile factory by name."""
    if name not in PROFILES:
        raise KeyError(f"Unknown profile: {name}")
    return PROFILES[name]


__all__ = ["cpu_default", "streaming_default", "jax_accel", "PROFILES", "get_profile"]


def __getattr__(name: str):
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__():
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
