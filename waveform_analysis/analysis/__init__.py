"""Canonical analysis accessors, queries, filters, and sampling helpers."""

from importlib import import_module

__all__ = [
    "PeakChannelAccessor",
    "S1S2PairAccessor",
    "adaptive_sample_count",
    "adaptive_stratified_sample_2d",
]

_LAZY_ATTRS = {
    "PeakChannelAccessor": (".peak_channel_accessor", "PeakChannelAccessor"),
    "S1S2PairAccessor": (".s1_s2_pair_accessor", "S1S2PairAccessor"),
    "adaptive_sample_count": (".sampling", "adaptive_sample_count"),
    "adaptive_stratified_sample_2d": (
        ".sampling",
        "adaptive_stratified_sample_2d",
    ),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _LAZY_ATTRS[name]
    except KeyError as exc:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'") from exc
    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__) | set(_LAZY_ATTRS))
