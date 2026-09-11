"""Canonical DAQ discovery, format adapters, and input parsing APIs."""

from importlib import import_module

__all__ = ["DAQAnalyzer", "DAQRun", "DAQAdapter", "get_adapter"]

_LAZY_ATTRS = {
    "DAQAnalyzer": (".daq", "DAQAnalyzer"),
    "DAQRun": (".daq", "DAQRun"),
    "DAQAdapter": (".formats", "DAQAdapter"),
    "get_adapter": (".formats", "get_adapter"),
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
