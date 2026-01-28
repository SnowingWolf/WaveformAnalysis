# -*- coding: utf-8 -*-
"""
StWaveforms Plugin - 波形结构化插件

**加速器**: CPU (NumPy)
**功能**: 将原始波形数据结构化为 NumPy 结构化数组

本插件将波形列表转换为包含时间戳、基线、通道号和波形数据的结构化数组，
为后续特征提取提供统一的数据格式。
"""

from pathlib import Path
from typing import Any, List, Optional

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.dtypes import RECORD_DTYPE
from waveform_analysis.core.processing.waveform_struct import WaveformStruct, WaveformStructConfig


class StWaveformsPlugin(Plugin):
    """Plugin to structure waveforms into NumPy arrays."""

    provides = "st_waveforms"
    depends_on = []
    save_when = "always"
    output_dtype = np.dtype(RECORD_DTYPE)
    options = {
        "daq_adapter": Option(
            default="vx2730",
            type=str,
            help="DAQ adapter name (default: 'vx2730').",
        ),
        "use_upstream_baseline": Option(
            default=False,
            type=bool,
            help="Whether to use baseline from upstream plugin (requires 'baseline' data).",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: Optional[str] = None) -> List[str]:
        """动态解析依赖关系"""
        deps = ["waveforms"]
        if context.get_config(self, "use_upstream_baseline"):
            deps.append("baseline")  # 如果启用，添加 baseline 依赖
        return deps

    def _get_record_dtype(self, daq_adapter: Optional[str]) -> np.dtype:
        if daq_adapter:
            config = WaveformStructConfig.from_adapter(daq_adapter)
        else:
            config = WaveformStructConfig.default_vx2730()
        return config.get_record_dtype()

    def get_lineage(self, context: Any) -> dict:
        config = {}
        for key in self.config_keys:
            option = self.options.get(key)
            if option and getattr(option, "track", True):
                config[key] = context.get_config(self, key)

        daq_adapter = config.get("daq_adapter")
        lineage = {
            "plugin_class": self.__class__.__name__,
            "plugin_version": getattr(self, "version", "0.0.0"),
            "description": getattr(self, "description", ""),
            "config": config,
            "depends_on": self._build_depends_lineage(context),
        }
        try:
            dtype = self._get_record_dtype(daq_adapter)
            lineage["dtype"] = np.dtype(dtype).descr
        except Exception:
            lineage["dtype"] = str(self.output_dtype)
        return lineage

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        """
        将波形数据结构化为 NumPy 结构化数组

        将原始波形列表转换为包含时间戳、基线、通道号和波形数据的结构化数组。
        这是数据流中的关键步骤，为后续特征提取提供统一的数据格式。

        支持通过 daq_adapter 配置选项指定 DAQ 适配器，以支持不同的 DAQ 格式。
        如果启用 use_upstream_baseline，则从上游插件获取 baseline 并保存到 baseline_upstream 字段。
        """
        waveforms = context.get_data(run_id, "waveforms")

        # 获取配置
        daq_adapter = context.get_config(self, "daq_adapter")
        use_upstream_baseline = context.get_config(self, "use_upstream_baseline")

        # 获取上游 baseline（如果启用）
        upstream_baselines = None
        if use_upstream_baseline:
            try:
                upstream_baselines = context.get_data(run_id, "baseline")
                context.logger.info(f"使用上游 baseline，共 {len(upstream_baselines)} 个通道")
            except Exception as e:
                context.logger.warning(f"无法获取上游 baseline: {e}，将使用 NaN 填充")
                upstream_baselines = None

        # 获取 epoch（从 DAQ 适配器或文件创建时间）
        epoch_ns = None
        if daq_adapter:
            from pathlib import Path

            from waveform_analysis.utils.formats import get_adapter

            adapter = get_adapter(daq_adapter)
            raw_files = context.get_data(run_id, "raw_files")

            # 从第一个通道的第一个文件获取 epoch
            if raw_files and raw_files[0]:
                first_file = Path(raw_files[0][0])
                epoch_ns = adapter.get_file_epoch(first_file)

        # 根据配置创建 WaveformStruct
        if daq_adapter:
            config = WaveformStructConfig.from_adapter(daq_adapter)
        else:
            config = WaveformStructConfig.default_vx2730()
        config.epoch_ns = epoch_ns
        self.output_dtype = config.get_record_dtype()

        # 创建 WaveformStruct，传入上游 baseline
        waveform_struct = WaveformStruct(waveforms, config=config, upstream_baselines=upstream_baselines)

        # 结构化波形
        start_channel_slice = context.config.get("start_channel_slice", 0)
        st_waveforms = waveform_struct.structure_waveforms(
            show_progress=context.config.get("show_progress", True),
            start_channel_slice=start_channel_slice,
        )
        return st_waveforms
