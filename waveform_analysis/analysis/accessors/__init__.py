"""Canonical Accessor facades."""

from importlib import import_module

__all__ = ["PeakChannelAccessor", "S1S2PairAccessor"]


def __getattr__(name: str):
    if name in __all__:
        leaf = "peak_channel_accessor" if name == "PeakChannelAccessor" else "s1_s2_pair_accessor"
        return getattr(import_module(f"waveform_analysis.analysis.{leaf}"), name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
