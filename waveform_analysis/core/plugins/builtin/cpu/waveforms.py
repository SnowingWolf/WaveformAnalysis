# -*- coding: utf-8 -*-
"""
Waveforms Plugin - 波形提取插件

**加速器**: CPU (NumPy)
**功能**: 从原始 CSV 文件中提取波形数据

本模块包含两个核心插件：
1. RawFileNamesPlugin: 扫描数据目录并按通道分组原始 CSV 文件
2. WaveformsPlugin: 从原始 CSV 文件中提取波形数据

WaveformsPlugin 支持双层并行处理加速：
- 通道级并行：多个通道同时处理
- 文件级并行：单个通道内的多个文件并行处理

性能优化特性：
- 自动使用 PyArrow 引擎（如果已安装）
- 自动计算最优并行数
- 支持线程池和进程池两种并行方式
"""

from typing import Any, List

import numpy as np

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


class WaveformsPlugin(Plugin):
    """Plugin to extract waveforms from raw files."""

    version = "0.0.2"
    provides = "waveforms"
    depends_on = ["raw_files"]
    description = "Read and parse waveform data from raw CSV files."
    save_when = "never"
    output_dtype = np.ndarray
    options = {
        "channel_workers": Option(
            default=None,
            help="Number of parallel workers for channel-level processing (None=auto, uses min(len(raw_files), cpu_count))",
            track=False,
        ),
        "channel_executor": Option(
            default="thread",
            type=str,
            help="Executor type for channel-level parallelism: 'thread' or 'process'",
            track=False,
        ),
        "daq_adapter": Option(default="vx2730", type=str, help="DAQ adapter name (e.g., 'vx2730')"),
        "n_jobs": Option(
            default=None,
            type=int,
            help="Number of parallel workers for file-level processing within each channel (None=auto, uses min(max_file_count, 50))",
            track=False,
        ),
        "use_process_pool": Option(
            default=False,
            type=bool,
            help="Whether to use process pool for file-level parallelism (False=thread pool for I/O, True=process pool for CPU-intensive)",
            track=False,
        ),
        "chunksize": Option(
            default=None,
            type=int,
            help="Chunk size for CSV reading (None=read entire file, enables PyArrow; set value to enable chunked reading but disables PyArrow)",
            track=False,
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

        raw_files = context.get_data(run_id, "raw_files")
        n_channels = len(raw_files)
        if n_channels == 0:
            return []

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
            selected_files = raw_files
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
        if isinstance(daq_adapter, str):
            daq_adapter = daq_adapter.lower()
        show_progress = context.config.get("show_progress", True)

        if daq_adapter == "v1725":
            from waveform_analysis.utils.formats import get_adapter

            adapter = get_adapter(daq_adapter)

            files = []
            for group in raw_files:
                if group:
                    files.extend(group)
            # Deduplicate while preserving order
            seen = set()
            file_list = []
            for path in files:
                if path in seen:
                    continue
                seen.add(path)
                file_list.append(path)

            if not file_list:
                return np.array([], dtype=np.float64).reshape(0, 0)

            data = adapter.format_reader.read_files(file_list, show_progress=show_progress)
            if data.size == 0:
                return data
            context.logger.info("v1725 returns unsplit waveforms (single array)")
            return data

        # ========== 执行波形加载 ==========
        # 双层并行架构：
        # - 外层：通道级并行（channel_workers 个通道同时处理）
        # - 内层：文件级并行（每个通道内 n_jobs 个文件同时处理）
        # 两层并行可以叠加使用
        return get_waveforms(
            raw_filess=raw_files,
            show_progress=show_progress,
            channel_workers=channel_workers,
            channel_executor=channel_executor,
            daq_adapter=daq_adapter,
            n_channels=n_channels,
            n_jobs=n_jobs,
            use_process_pool=use_process_pool,
            chunksize=chunksize,
        )
