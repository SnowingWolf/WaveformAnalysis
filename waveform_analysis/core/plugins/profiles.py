# -*- coding: utf-8 -*-
# DOC: docs/features/plugin/PLUGIN_SET_PROFILE_GUIDE.md#profiles
"""
Execution profiles composed from plugin sets.
"""

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.plugin_sets import (
    plugins_basic_features,
    plugins_events,
    plugins_io,
    plugins_tabular,
    plugins_waveform,
)

export, __all__ = exporter()


@export
def cpu_default():
    """Default CPU profile (core pipeline)."""
    return (
        plugins_io()
        + plugins_waveform()
        + plugins_basic_features()
        + plugins_tabular()
        + plugins_events()
    )


@export
def streaming_default():
    """Placeholder for a streaming profile."""
    raise NotImplementedError(
        "Streaming profile is not available yet. Use cpu_default() for now."
    )


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
