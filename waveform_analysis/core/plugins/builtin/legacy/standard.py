# -*- coding: utf-8 -*-
"""
Standard Plugins 模块 - 包含波形分析流程的标准插件实现。

定义了从原始文件扫描、波形提取、结构化到特征计算和事件配对的完整插件链。
这些插件是 WaveformDataset 内部调用的核心逻辑单元。
"""

from typing import Any, List

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.processor import (
    PEAK_DTYPE,
    RECORD_DTYPE,
    WaveformStruct,
    find_hits,
)


class RawFilesPlugin(Plugin):
    """Plugin to find raw CSV files."""

    provides = "raw_files"
    description = "Scan the data directory and group raw CSV files by channel number."
    options = {
        "n_channels": Option(default=2, type=int, help="Number of channels to load"),
        "start_channel_slice": Option(default=6, type=int, help="Starting channel index"),
        "data_root": Option(default="DAQ", type=str, help="Root directory for data"),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> List[List[str]]:
        """
        扫描数据目录并按通道分组原始 CSV 文件

        从配置的数据目录中查找指定运行的所有原始波形文件，并按通道号分组。
        支持 DAQ 集成，可以直接从 DAQ 元数据中获取文件列表。

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
        from waveform_analysis.utils.loader import get_raw_files

        n_channels = context.get_config(self, "n_channels")
        start_channel_slice = context.get_config(self, "start_channel_slice")
        data_root = context.get_config(self, "data_root")

        # Support DAQ integration if daq_run is present in context
        daq_run = getattr(context, "daq_run", None)

        return get_raw_files(
            n_channels=n_channels + start_channel_slice,
            run_name=run_id,
            data_root=data_root,
            daq_run=daq_run,
        )


class WaveformsPlugin(Plugin):
    """Plugin to extract waveforms from raw files."""

    provides = "waveforms"
    depends_on = ["raw_files"]
    description = "Read and parse waveform data from raw CSV files."
    options = {
        "start_channel_slice": Option(default=6, type=int),
        "n_channels": Option(default=2, type=int),
        "channel_workers": Option(default=None, help="Number of parallel workers for channel-level processing (None=auto, uses min(n_channels, cpu_count))"),
        "channel_executor": Option(default="thread", type=str, help="Executor type for channel-level parallelism: 'thread' or 'process'"),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        """
        从原始 CSV 文件中提取波形数据

        读取并解析原始 CSV 文件，提取每个通道的波形数据。
        支持并行处理加速，可配置使用线程池或进程池进行通道级并行。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 raw_files（由 RawFilesPlugin 提供）

        Returns:
            List[np.ndarray]: 每个通道的波形数据列表

        Examples:
            >>> waveforms = ctx.get_data('run_001', 'waveforms')
            >>> print(f"通道0波形形状: {waveforms[0].shape}")
        """
        import multiprocessing

        from waveform_analysis.utils.loader import get_waveforms

        start = context.get_config(self, "start_channel_slice")
        n_channels = context.config.get("n_channels", 2)
        end = start + n_channels
        raw_files = context.get_data(run_id, "raw_files")
        
        # Get parallel processing configuration
        channel_workers = context.get_config(self, "channel_workers")
        channel_executor = context.get_config(self, "channel_executor")
        
        # Enable multithreading acceleration by default: use number of channels or CPU count, whichever is smaller
        if channel_workers is None:
            channel_workers = min(n_channels, multiprocessing.cpu_count())
        
        show_progress = context.config.get("show_progress", True)
        
        return get_waveforms(
            raw_filess=raw_files[start:end],
            show_progress=show_progress,
            channel_workers=channel_workers,
            channel_executor=channel_executor,
        )


class StWaveformsPlugin(Plugin):
    """Plugin to structure waveforms into NumPy arrays."""

    provides = "st_waveforms"
    depends_on = ["waveforms"]
    save_when = "always"
    # output_dtype 使用默认的 RECORD_DTYPE，但实际会根据原始数据的波形长度动态调整
    output_dtype = np.dtype(RECORD_DTYPE)

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        """
        将波形数据结构化为 NumPy 结构化数组

        将原始波形列表转换为包含时间戳、基线、通道号和波形数据的结构化数组。
        这是数据流中的关键步骤，为后续特征提取提供统一的数据格式。
        
        注意：波形长度会根据原始数据的实际长度动态确定，不再固定使用 DEFAULT_WAVE_LENGTH。
        如果原始数据的波形长度与默认值不同，会自动创建相应长度的 dtype。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 waveforms（由 WaveformsPlugin 提供）

        Returns:
            List[np.ndarray]: 每个通道的结构化数组，dtype 根据实际波形长度动态创建

        Examples:
            >>> st_waveforms = ctx.get_data('run_001', 'st_waveforms')
            >>> print(st_waveforms[0].dtype.names)
            >>> print(st_waveforms[0]["wave"].shape)  # 波形长度根据实际数据确定
        """
        waveforms = context.get_data(run_id, "waveforms")
        waveform_struct = WaveformStruct(waveforms)
        # 通道号现在从CSV的BOARD/CHANNEL字段读取并映射，不再使用start_channel_slice
        # 保留start_channel_slice参数以向后兼容，但实际不再使用
        start_channel_slice = context.config.get("start_channel_slice", 0)
        st_waveforms = waveform_struct.structure_waveforms(
            show_progress=context.config.get("show_progress", True),
            start_channel_slice=start_channel_slice  # 保留参数以兼容，但不再使用
        )
        return st_waveforms


class HitFinderPlugin(Plugin):
    """Example implementation of the HitFinder as a plugin."""

    provides = "hits"
    depends_on = ["st_waveforms"]
    input_dtype = {"st_waveforms": np.dtype(RECORD_DTYPE)}
    output_dtype = np.dtype(PEAK_DTYPE)

    def compute(self, context: Any, run_id: str, threshold: float = 10.0, **kwargs) -> List[np.ndarray]:
        """
        从结构化波形中检测 Hit 事件

        使用阈值法从波形中识别和定位 Hit（超过阈值的信号峰值）。
        返回每个 Hit 的时间、面积、高度和宽度等特征。

        Args:
            context: Context 实例
            run_id: 运行标识符
            threshold: Hit 检测阈值（默认10.0）
            **kwargs: 依赖数据，包含 st_waveforms

        Returns:
            List[np.ndarray]: 每个通道的 Hit 列表，dtype 为 PEAK_DTYPE

        Examples:
            >>> hits = ctx.get_data('run_001', 'hits')
            >>> print(f"通道0的Hit数: {len(hits[0])}")
        """
        st_waveforms = context.get_data(run_id, "st_waveforms")

        hits_list = []
        for i in range(len(st_waveforms)):
            st_ch = st_waveforms[i]
            if len(st_ch) == 0:
                hits_list.append(np.zeros(0, dtype=kwargs.get("dtype", object)))
                continue

            # 使用每个通道的全部事件数
            waves_2d = np.stack(st_ch["wave"])
            hits = find_hits(waves_2d, st_ch["baseline"], threshold=threshold)
            hits_list.append(hits)
        return hits_list


class PeaksPlugin(Plugin):
    """Plugin to compute peak features from structured waveforms."""

    provides = "peaks"
    depends_on = ["st_waveforms"]
    save_when = "always"
    options = {
        "peaks_range": Option(default=None, type=tuple, help="峰值计算范围 (start, end)"),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        """
        从结构化波形中计算峰值特征

        在配置的时间窗口内查找波形的最大峰值（最大值 - 最小值）。
        使用向量化计算，高效处理大量波形数据。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据

        Returns:
            List[np.ndarray]: 每个通道的峰值数组

        Examples:
            >>> peaks = ctx.get_data('run_001', 'peaks')
            >>> print(f"峰值范围: {peaks[0].min():.2f} - {peaks[0].max():.2f}")
        """
        from waveform_analysis.core.processing.processor import WaveformProcessor

        st_waveforms = context.get_data(run_id, "st_waveforms")
        peaks_range = context.get_config(self, "peaks_range")

        processor = WaveformProcessor(n_channels=len(st_waveforms))
        peaks, _ = processor.compute_basic_features(st_waveforms, peaks_range=peaks_range)
        return peaks


class ChargesPlugin(Plugin):
    """Plugin to compute charge features from structured waveforms."""

    provides = "charges"
    depends_on = ["st_waveforms"]
    save_when = "always"
    options = {
        "charge_range": Option(
            default=(0, None),
            type=tuple,
            help="电荷计算范围 (start, end)，end=None 表示积分到波形末端",
        ),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        """
        从结构化波形中计算电荷积分

        在配置的时间窗口内对波形进行积分（baseline - wave），计算总电荷。
        使用向量化计算提高效率。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据

        Returns:
            List[np.ndarray]: 每个通道的电荷数组

        Examples:
            >>> charges = ctx.get_data('run_001', 'charges')
            >>> print(f"电荷范围: {charges[0].min():.2f} - {charges[0].max():.2f}")
        """
        from waveform_analysis.core.processing.processor import WaveformProcessor

        st_waveforms = context.get_data(run_id, "st_waveforms")
        charge_range = context.get_config(self, "charge_range")

        processor = WaveformProcessor(n_channels=len(st_waveforms))
        _, charges = processor.compute_basic_features(st_waveforms, charge_range=charge_range)
        return charges


class DataFramePlugin(Plugin):
    """Plugin to build the initial single-channel events DataFrame."""

    provides = "df"
    depends_on = ["st_waveforms", "peaks", "charges"]
    save_when = "always"

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        """
        构建单通道事件的 DataFrame

        整合结构化波形、峰值和电荷特征，构建包含所有事件信息的 pandas DataFrame。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 st_waveforms, peaks, charges

        Returns:
            pd.DataFrame: 包含所有通道事件的 DataFrame

        Examples:
            >>> df = ctx.get_data('run_001', 'df')
            >>> print(f"总事件数: {len(df)}")
        """
        from waveform_analysis.core.processing.processor import WaveformProcessor

        st_waveforms = context.get_data(run_id, "st_waveforms")
        peaks = context.get_data(run_id, "peaks")
        charges = context.get_data(run_id, "charges")

        # 通道号现在从st_waveforms中的channel字段读取（从BOARD/CHANNEL映射得到）
        # 保留start_channel_slice参数以向后兼容，但实际不再使用
        start_channel_slice = context.config.get("start_channel_slice", 0)

        processor = WaveformProcessor(n_channels=len(st_waveforms))
        df = processor.build_dataframe(
            st_waveforms,
            peaks,
            charges,
            start_channel_slice=start_channel_slice,  # 保留参数以兼容，但不再使用
        )
        return df


class GroupedEventsPlugin(Plugin):
    """Plugin to group events by time window."""

    provides = "df_events"
    depends_on = ["df"]
    save_when = "always"
    options = {
        "time_window_ns": Option(default=100.0, type=float),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        """
        按时间窗口分组多通道事件

        在指定的时间窗口内识别多通道同时触发的事件，并将它们分组。
        支持 Numba 加速和多进程并行处理。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 df

        Returns:
            pd.DataFrame: 分组后的事件

        Examples:
            >>> df_events = ctx.get_data('run_001', 'df_events')
            >>> print(f"事件组数: {df_events['event_id'].nunique()}")
        """
        from waveform_analysis.core.processing.analyzer import EventAnalyzer

        df = context.get_data(run_id, "df")
        tw = context.get_config(self, "time_window_ns")

        # We need n_channels and start_channel_slice from context config
        n_channels = context.config.get("n_channels", 2)
        start_channel_slice = context.config.get("start_channel_slice", 6)

        analyzer = EventAnalyzer(n_channels=n_channels, start_channel_slice=start_channel_slice)
        # 从context配置中获取优化参数（如果存在）
        use_numba = context.config.get("use_numba", True)
        n_processes = context.config.get("n_processes", None)
        return analyzer.group_events(df, tw, use_numba=use_numba, n_processes=n_processes)


class PairedEventsPlugin(Plugin):
    """Plugin to pair events across channels."""

    provides = "df_paired"
    depends_on = ["df_events"]
    save_when = "always"

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        """
        配对跨通道的符合事件

        识别满足时间符合条件的多通道事件对，用于符合测量分析。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 df_events

        Returns:
            pd.DataFrame: 配对事件

        Examples:
            >>> df_paired = ctx.get_data('run_001', 'df_paired')
            >>> print(f"配对数: {len(df_paired)}")
        """
        from waveform_analysis.core.processing.analyzer import EventAnalyzer

        df_events = context.get_data(run_id, "df_events")

        n_channels = context.config.get("n_channels", 2)
        start_channel_slice = context.config.get("start_channel_slice", 6)
        time_window_ns = context.config.get("time_window_ns", 100.0)  # 从配置获取时间窗口

        analyzer = EventAnalyzer(n_channels=n_channels, start_channel_slice=start_channel_slice)
        return analyzer.pair_events(df_events, time_window_ns=time_window_ns)
