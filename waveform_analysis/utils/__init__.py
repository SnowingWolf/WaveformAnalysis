"""
Utils module - 工具函数
"""

from importlib import import_module

__all__ = [
    "DAQRun",
    "DAQAnalyzer",
    "get_raw_files",
    "get_waveforms",
    "get_waveforms_generator",
    "filter_events_by_function",
    "filter_coincidence_events",
    "extract_channel_attributes",
    "plot_records_waveforms",
]

_LAZY_ATTRS: dict[str, tuple[str, str | None]] = {
    "DAQRun": (".daq", "DAQRun"),
    "DAQAnalyzer": (".daq", "DAQAnalyzer"),
    "get_raw_files": ("waveform_analysis.core.processing.loader", "get_raw_files"),
    "get_waveforms": ("waveform_analysis.core.processing.loader", "get_waveforms"),
    "get_waveforms_generator": (
        "waveform_analysis.core.processing.loader",
        "get_waveforms_generator",
    ),
    "filter_events_by_function": (".event_filters", "filter_events_by_function"),
    "filter_coincidence_events": (".event_filters", "filter_coincidence_events"),
    "extract_channel_attributes": (".event_filters", "extract_channel_attributes"),
    "parse_files_generator": (".io", "parse_files_generator"),
    "plot_records_waveforms": (".preview", "plot_records_waveforms"),
}


def __getattr__(name: str):
    if name in _LAZY_ATTRS:
        module_name, attr_name = _LAZY_ATTRS[name]
        module = import_module(module_name, __name__)
        value = getattr(module, attr_name) if attr_name else module
        globals()[name] = value
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(set(globals()) | set(__all__) | set(_LAZY_ATTRS))
