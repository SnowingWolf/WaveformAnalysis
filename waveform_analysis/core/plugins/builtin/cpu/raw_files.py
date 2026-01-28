# -*- coding: utf-8 -*-
"""
Raw Files Plugin - 原始文件扫描插件

**加速器**: CPU (NumPy)
**功能**: 扫描数据目录并按通道分组原始 CSV 文件

本模块包含原始文件扫描插件，是数据处理流程的起点。
支持 DAQ 集成，可以直接从 DAQ 元数据中获取文件列表。
"""

from typing import Any, List

from waveform_analysis.core.plugins.core.base import Option, Plugin


class RawFileNamesPlugin(Plugin):
    """Plugin to find raw CSV files."""

    provides = "raw_files"
    description = "Scan the data directory and group raw CSV files by channel number."
    version = "0.0.2"
    options = {
        "data_root": Option(default="DAQ", type=str, help="Root directory for data"),
        "daq_adapter": Option(default="vx2730", type=str, help="DAQ adapter name (e.g., 'vx2730')"),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> List[List[str]]:
        """
        扫描数据目录并按通道分组原始 CSV 文件

        从配置的数据目录中查找指定运行的所有原始波形文件，并按通道号分组。
        支持 DAQ 集成，可以直接从 DAQ 元数据中获取文件列表。
        支持通过 daq_adapter 参数指定 DAQ 适配器来处理不同格式。
        通道选择由 DAQ 适配器或 DAQ 元数据决定，不再通过插件配置裁剪。

        Args:
            context: Context 实例，用于访问配置和缓存
            run_id: 运行标识符（运行名称）
            **kwargs: 依赖数据（此插件无依赖）

        Returns:
            List[List[str]]: 按通道分组的文件路径列表

        Examples:
            >>> raw_files = ctx.get_data('run_001', 'raw_files')
            >>> print(f"通道数: {len(raw_files)}")
        """
        from waveform_analysis.core.processing.loader import get_raw_files

        data_root = context.get_config(self, "data_root")
        daq_adapter = context.get_config(self, "daq_adapter")

        # Support DAQ integration if daq_run is present in context
        daq_run = getattr(context, "daq_run", None)

        return get_raw_files(
            run_name=run_id,
            data_root=data_root,
            daq_run=daq_run,
            daq_adapter=daq_adapter,
        )
