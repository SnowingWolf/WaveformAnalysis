# -*- coding: utf-8 -*-
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

from waveform_analysis.core.foundation.utils import exporter

from .cpu import SignalPeaksStreamPlugin

export, __all__ = exporter()

__all__.extend([
    "SignalPeaksStreamPlugin",
])
