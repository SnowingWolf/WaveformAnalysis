# -*- coding: utf-8 -*-
"""DAQ 工具：包含 DAQRun 和 DAQAnalyzer

This module exposes DAQRun and DAQAnalyzer from their dedicated modules so
external imports can continue to use ``waveform_analysis.utils.daq`` as the
public entrypoint.
"""

from __future__ import annotations

import logging
from typing import Any

from .daq_analyzer import DAQAnalyzer
from .daq_run import DAQRun
from waveform_analysis.core.foundation.utils import exporter

logger = logging.getLogger(__name__)


export, __all__ = exporter()

# 导出已有的类
export(DAQAnalyzer)
export(DAQRun)

class _DAQRunAdapter:
    """Lightweight adapter exposing a stable minimal DAQRun protocol:

    - get_channel_paths(n_channels) -> List[List[str]]
    - channel_files -> dict mapping ch -> list(entries)z

    This adapter wraps objects that either already implement the method,
    or provide a `channel_files` attribute, or are plain dict mappings.
    """

    def __init__(self, src: Any):
        """
        初始化 DAQ 运行适配器

        包装不同来源的 DAQ 运行对象，提供统一的接口。

        Args:
            src: DAQ 运行对象（可以是 DAQRun, dict, 或任何提供 channel_files 的对象）

        Note:
            适配器会尝试调用 get_channel_paths 方法，如果不存在则从 channel_files 属性构建。
        """
        self._src = src

    def get_channel_paths(self, n_channels: int):
        # If source already provides the method, prefer it
        if hasattr(self._src, "get_channel_paths"):
            try:
                return self._src.get_channel_paths(n_channels)
            except Exception:
                logger.debug("get_channel_paths existed but raised; falling back", exc_info=True)

        # If source exposes channel_files mapping, construct ordered paths
        cf = getattr(self._src, "channel_files", None)
        if cf is not None and isinstance(cf, dict):
            out = [[] for _ in range(n_channels)]
            for ch in range(n_channels):
                entries = cf.get(ch, [])
                # entries may be dicts with 'path' and optional 'index', or plain paths
                # Preserve provided order; entries is expected to be in acquisition order
                paths = [str(e.get("path")) if isinstance(e, dict) else str(e) for e in entries]
                out[ch] = paths
            return out

        # If source is itself a dict mapping
        if isinstance(self._src, dict):
            out = [[] for _ in range(n_channels)]
            for ch in range(n_channels):
                entries = self._src.get(ch, [])
                paths = [str(e.get("path")) if isinstance(e, dict) else str(e) for e in entries]
                out[ch] = paths
            return out

        # Unknown shape: return empty lists
        return [[] for _ in range(n_channels)]


@export
def adapt_daq_run(obj: Any):
    """Return an adapter providing `get_channel_paths(n_channels)` for obj. 

    Use this in loader/dataset to normalize inputs from different DAQ tooling.
    """
    return _DAQRunAdapter(obj)


__all__ = ["DAQRun", "DAQAnalyzer"]
