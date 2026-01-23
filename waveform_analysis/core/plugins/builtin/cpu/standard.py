# -*- coding: utf-8 -*-
"""
CPU Standard Plugins - 标准波形分析插件（NumPy/SciPy 实现）

**加速器**: CPU (NumPy/SciPy/Numba)
**功能**: 从原始文件扫描到特征计算和事件配对的完整插件链

本模块包含波形分析流程的标准插件实现，是标准处理流程的核心逻辑单元。
这些插件使用 CPU 计算，支持 Numba JIT 加速和多进程并行处理。
"""

from typing import Any, List, Optional

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
    version = "0.0.1"
    options = {
        "n_channels": Option(default=2, type=int, help="Number of channels to load"),
        "start_channel_slice": Option(default=6, type=int, help="Starting channel index"),
        "data_root": Option(default="DAQ", type=str, help="Root directory for data"),
        "daq_adapter": Option(default=None, type=str, help="DAQ adapter name (e.g., 'vx2730')"),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> List[List[str]]:
        """
        扫描数据目录并按通道分组原始 CSV 文件

        从配置的数据目录中查找指定运行的所有原始波形文件，并按通道号分组。
        支持 DAQ 集成，可以直接从 DAQ 元数据中获取文件列表。
        支持通过 daq_adapter 参数指定 DAQ 适配器来处理不同格式。

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

        n_channels = context.get_config(self, "n_channels")
        start_channel_slice = context.get_config(self, "start_channel_slice")
        data_root = context.get_config(self, "data_root")
        daq_adapter = context.get_config(self, "daq_adapter")

        # Support DAQ integration if daq_run is present in context
        daq_run = getattr(context, "daq_run", None)

        return get_raw_files(
            n_channels=n_channels + start_channel_slice,
            run_name=run_id,
            data_root=data_root,
            daq_run=daq_run,
            daq_adapter=daq_adapter,
        )

class WaveformsPlugin(Plugin):
    """Plugin to extract waveforms from raw files."""

    version = "0.0.1"
    provides = "waveforms"
    depends_on = ["raw_files"]
    description = "Read and parse waveform data from raw CSV files."
    save_when = "never"
    options = {
        "start_channel_slice": Option(default=6, type=int),
        "n_channels": Option(default=2, type=int),
        "channel_workers": Option(
            default=None,
            help="Number of parallel workers for channel-level processing (None=auto, uses min(n_channels, cpu_count))",
        ),
        "channel_executor": Option(
            default="thread",
            type=str,
            help="Executor type for channel-level parallelism: 'thread' or 'process'",
        ),
        "daq_adapter": Option(default=None, type=str, help="DAQ adapter name (e.g., 'vx2730')"),
        "n_jobs": Option(
            default=None,
            type=int,
            help="Number of parallel workers for file-level processing within each channel (None=auto, uses min(max_file_count, 50))",
        ),
        "use_process_pool": Option(
            default=False,
            type=bool,
            help="Whether to use process pool for file-level parallelism (False=thread pool for I/O, True=process pool for CPU-intensive)",
        ),
        "chunksize": Option(
            default=None,
            type=int,
            help="Chunk size for CSV reading (None=read entire file, enables PyArrow; set value to enable chunked reading but disables PyArrow)",
        ),
    }
    
    

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        """
        从原始 CSV 文件中提取波形数据

        读取并解析原始 CSV 文件，提取每个通道的波形数据。
        支持双层并行处理加速：
        - 通道级并行：多个通道同时处理（通过 channel_workers 控制）
        - 文件级并行：单个通道内的多个文件并行处理（通过 n_jobs 控制）

        性能优化特性：
        - 自动使用 PyArrow 引擎（当 chunksize=None 时，如果已安装 PyArrow）
        - n_jobs 自动计算：默认使用 min(最大文件数, 50)，可根据实际文件数自动调整
        - 支持线程池和进程池两种并行方式，适应 I/O 密集和 CPU 密集场景

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 raw_files（由 RawFilesPlugin 提供）

        Returns:
            List[np.ndarray]: 每个通道的波形数据列表

        Examples:
            >>> # 基本使用（自动优化）
            >>> waveforms = ctx.get_data('run_001', 'waveforms')
            >>> print(f"通道0波形形状: {waveforms[0].shape}")

            >>> # 手动配置并行参数
            >>> ctx.set_config({
            ...     "waveforms.channel_workers": 4,  # 4个通道并行
            ...     "waveforms.n_jobs": 8,  # 每个通道内8个文件并行
            ...     "waveforms.channel_executor": "thread",  # 通道级用线程
            ...     "waveforms.use_process_pool": False,  # 文件级用线程
            ... })
            >>> waveforms = ctx.get_data('run_001', 'waveforms')

        Notes:
            - n_jobs=None 时自动计算为 min(所有通道中最大文件数, 50)
            - chunksize=None 时自动使用 PyArrow（如果已安装），性能提升 1.5-2 倍
            - I/O 密集型场景：channel_executor="thread", use_process_pool=False
            - CPU 密集型场景：channel_executor="process", use_process_pool=True
        """
        import multiprocessing

        from waveform_analysis.core.processing.loader import get_waveforms

        # ========== 获取通道切片配置 ==========
        start = context.get_config(self, "start_channel_slice")
        n_channels = context.get_config(self, "n_channels")
        end = start + n_channels
        raw_files = context.get_data(run_id, "raw_files")

        # ========== 通道级并行配置 ==========
        # 通道级并行：多个通道同时处理，每个通道分配一个 worker
        channel_workers = context.get_config(self, "channel_workers")
        channel_executor = context.get_config(self, "channel_executor")

        # 自动计算通道级并行数：使用通道数和 CPU 核心数的较小值
        if channel_workers is None:
            channel_workers = min(n_channels, multiprocessing.cpu_count())

        # ========== 文件级并行配置 ==========
        # 文件级并行：单个通道内的多个文件并行处理
        n_jobs = context.get_config(self, "n_jobs")
        use_process_pool = context.get_config(self, "use_process_pool")
        chunksize = context.get_config(self, "chunksize")

        # 动态计算 n_jobs 默认值：基于实际文件数量，上限为 50
        # 计算方式：取所有通道中文件数的最大值，然后取 min(文件数, 50)
        # 这样可以确保：
        # - 文件数少时（如 10 个文件），使用 10 个并行任务，充分利用资源
        # - 文件数多时（如 100 个文件），限制为 50 个，避免过度并行导致开销
        if n_jobs is None:
            selected_files = raw_files[start:end]
            if selected_files:
                # 计算所有通道中文件数的最大值
                file_counts = [len(files) for files in selected_files if files]
                max_file_count = max(file_counts) if file_counts else 0
                # 使用 min(文件数, 50) 作为并行数
                n_jobs = min(max_file_count, 50) if max_file_count > 0 else 1
            else:
                n_jobs = 1

        # ========== PyArrow 自动使用说明 ==========
        # PyArrow 引擎会在 parse_and_stack_files 中自动使用，条件：
        # 1. chunksize=None（默认）：PyArrow 会自动检测并使用（如果已安装）
        # 2. PyArrow 比 pandas 'c' 引擎快 1.5-2 倍
        # 3. 如果设置了 chunksize，会自动回退到 'c' 引擎（PyArrow 不支持分块读取）
        # 注意：这里不需要额外配置，parse_and_stack_files 会自动处理

        # ========== 其他配置 ==========
        daq_adapter = context.get_config(self, "daq_adapter")
        show_progress = context.config.get("show_progress", True)

        # ========== 执行波形加载 ==========
        # 双层并行架构：
        # - 外层：通道级并行（channel_workers 个通道同时处理）
        # - 内层：文件级并行（每个通道内 n_jobs 个文件同时处理）
        # 两层并行可以叠加使用，实现最大性能提升（通常 4-12 倍）
        return get_waveforms(
            raw_filess=raw_files[start:end],
            show_progress=show_progress,
            channel_workers=channel_workers,
            channel_executor=channel_executor,
            daq_adapter=daq_adapter,
            n_jobs=n_jobs,
            use_process_pool=use_process_pool,
            chunksize=chunksize,
        )

class StWaveformsPlugin(Plugin):
    """Plugin to structure waveforms into NumPy arrays."""

    provides = "st_waveforms"
    depends_on = ["waveforms"]
    save_when = "always"
    output_dtype = np.dtype(RECORD_DTYPE)
    options = {
        "daq_adapter": Option(
            default=None,
            type=str,
            help="DAQ adapter name (e.g., 'vx2730'). If None, uses VX2730 default configuration."
        ),
    }

    def _get_record_dtype(self, daq_adapter: Optional[str]) -> np.dtype:
        from waveform_analysis.core.processing.processor import WaveformStructConfig
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
            "depends_on": {dep: context.get_lineage(dep) for dep in self.depends_on},
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
        如果未指定，则使用 VX2730 默认配置（向后兼容）。

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据，包含 waveforms（由 WaveformsPlugin 提供）

        Returns:
            List[np.ndarray]: 每个通道的结构化数组，dtype 为 RECORD_DTYPE

        Examples:
            >>> # 默认使用 VX2730 配置
            >>> st_waveforms = ctx.get_data('run_001', 'st_waveforms')
            >>> print(st_waveforms[0].dtype.names)

            >>> # 指定 DAQ 适配器
            >>> ctx.set_config({'daq_adapter': 'vx2730'}, plugin_name='st_waveforms')
            >>> st_waveforms = ctx.get_data('run_001', 'st_waveforms')
        """
        waveforms = context.get_data(run_id, "waveforms")

        # 获取 daq_adapter 配置
        daq_adapter = context.get_config(self, "daq_adapter")

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
        from waveform_analysis.core.processing.processor import WaveformStructConfig
        if daq_adapter:
            config = WaveformStructConfig.from_adapter(daq_adapter)
        else:
            config = WaveformStructConfig.default_vx2730()
        config.epoch_ns = epoch_ns
        self.output_dtype = config.get_record_dtype()
        waveform_struct = WaveformStruct(waveforms, config=config)

        # 通道号现在从CSV的BOARD/CHANNEL字段读取并映射，不再使用start_channel_slice
        # 保留start_channel_slice参数以向后兼容，但实际不再使用
        start_channel_slice = context.config.get("start_channel_slice", 0)
        st_waveforms = waveform_struct.structure_waveforms(
            show_progress=context.config.get("show_progress", True),
            start_channel_slice=start_channel_slice,  # 保留参数以兼容，但不再使用
        )
        return st_waveforms

class HitFinderPlugin(Plugin):
    """Example implementation of the HitFinder as a plugin."""

    provides = "hits"
    depends_on = ["st_waveforms"]
    output_dtype = np.dtype(PEAK_DTYPE)

    def compute(
        self, context: Any, run_id: str, threshold: float = 10.0, **kwargs
    ) -> List[np.ndarray]:
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
                hits_list.append(np.zeros(0, dtype=PEAK_DTYPE))
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
