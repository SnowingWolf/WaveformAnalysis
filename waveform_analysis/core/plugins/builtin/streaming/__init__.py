"""
流式插件模块 - 支持流式处理的插件

本模块包含流式处理插件，分为 CPU 和 JAX 两个子模块：
- streaming/cpu/: CPU 流式插件
- streaming/jax/: [JAX] JAX 流式插件（GPU 加速）

**特性**:
- 内存高效的 chunk 级处理
- 支持动态负载均衡
- 自动并行批处理
"""

from waveform_analysis._lazy_exports import LazyExport as _LazyExport
from waveform_analysis._lazy_exports import lazy_dir as _lazy_dir
from waveform_analysis._lazy_exports import (
    resolve_lazy_attribute as _resolve_lazy_attribute,
)
from waveform_analysis.core.foundation.utils import exporter

# Preserve the historical helper names without importing the CPU plugin.
export, _exported = exporter()

__all__ = ["SignalPeaksStreamPlugin"]

_LAZY_EXPORTS: dict[str, _LazyExport] = {
    "SignalPeaksStreamPlugin": (
        "waveform_analysis.core.plugins.builtin.signal_peaks_stream",
        "SignalPeaksStreamPlugin",
    ),
    "cpu": (".cpu", None),
}

_LAZY_ATTRS = _LAZY_EXPORTS


def __getattr__(name: str):
    return _resolve_lazy_attribute(name, _LAZY_EXPORTS, globals())


def __dir__():
    return _lazy_dir(globals(), _LAZY_EXPORTS, __all__)
