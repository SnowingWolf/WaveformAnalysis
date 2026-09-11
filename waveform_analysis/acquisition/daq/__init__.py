"""DAQ（数据采集）模块 - 数据采集接口、运行管理、分析工具。"""

from importlib import import_module

__all__ = [
    "DAQAnalyzer",
    "DAQRun",
    "adapt_daq_run",
]

_LAZY_ATTRS: dict[str, tuple[str, str | None]] = {
    "DAQAnalyzer": (".daq_analyzer", "DAQAnalyzer"),
    "DAQRun": (".daq_run", "DAQRun"),
    "adapt_daq_run": (".daq", "adapt_daq_run"),
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
