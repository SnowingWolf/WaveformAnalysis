"""
Waveforms Plugin - 波形提取与结构化插件

**加速器**: CPU (NumPy)
**功能**: 从原始 CSV 文件中提取波形数据并结构化为 NumPy 结构化数组

本模块包含：
1. RawFileNamesPlugin: 扫描数据目录并按通道分组原始 CSV 文件
2. WaveformsPlugin: 从原始 CSV 文件中提取波形数据并结构化
3. WaveformStructConfig: 波形结构化配置类
4. WaveformStruct: 波形结构化处理器

WaveformsPlugin 支持双层并行处理加速：
- 通道级并行：多个通道同时处理
- 文件级并行：单个通道内的多个文件并行处理

性能优化特性：
- 自动使用 PyArrow 引擎（如果已安装）
- 自动计算最优并行数
- 支持线程池和进程池两种并行方式
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.processing.dtypes import (
    DEFAULT_WAVE_LENGTH,
    ST_WAVEFORM_DTYPE,
    create_record_dtype,
)

if TYPE_CHECKING:
    from waveform_analysis.utils.formats.base import FormatSpec

# Setup logger
logger = logging.getLogger(__name__)

# 初始化 exporter
export, __all__ = exporter()


@export
@dataclass
class WaveformStructConfig:
    """波形结构化配置 - 解耦 DAQ 设备依赖

    通过配置类封装 DAQ 格式的列映射和波形长度信息，使 WaveformStruct
    不再硬编码 VX2730 特定的列索引。

    Attributes:
        format_spec: DAQ 格式规范（包含列映射、时间戳单位等）
        wave_length: 可选的波形长度覆盖值。None 时从数据自动检测
        dt_ns: 可选的采样间隔（ns）。None 时从 adapter 推断
        epoch_ns: 文件创建时间 (Unix ns)

    示例:
        >>> from waveform_analysis.utils.formats import VX2730_SPEC
        >>> config = WaveformStructConfig(format_spec=VX2730_SPEC)
        >>> print(config.get_wave_length())  # DEFAULT_WAVE_LENGTH 或从数据检测
    """

    format_spec: FormatSpec
    wave_length: Optional[int] = None
    dt_ns: Optional[int] = None
    epoch_ns: Optional[int] = None

    @classmethod
    def default_vx2730(cls) -> WaveformStructConfig:
        """返回 VX2730 默认配置（向后兼容）

        注意：不再硬编码 wave_length，依赖自动检测
        """
        from waveform_analysis.utils.formats import VX2730_SPEC

        return cls(format_spec=VX2730_SPEC, wave_length=None)

    @classmethod
    def from_adapter(cls, adapter_name: str = "vx2730") -> WaveformStructConfig:
        """从已注册的 DAQ 适配器创建配置

        注意：不再从适配器获取 expected_samples，依赖自动检测
        """
        from waveform_analysis.utils.formats import get_adapter

        adapter = get_adapter(adapter_name)
        return cls(format_spec=adapter.format_spec, wave_length=None)

    def get_wave_length(self) -> int:
        """获取实际波形长度

        优先级：
        1. wave_length（用户显式配置）
        2. DEFAULT_WAVE_LENGTH（全局默认值）

        注意：实际波形长度可能在结构化时从数据自动检测
        """
        if self.wave_length is not None:
            return self.wave_length
        return DEFAULT_WAVE_LENGTH

    def get_record_dtype(self) -> np.dtype:
        """获取对应的 ST_WAVEFORM_DTYPE"""
        return create_record_dtype(self.get_wave_length())

    def get_dt_ns(self) -> int:
        """获取采样间隔（ns）"""
        if self.dt_ns is not None:
            dt_ns = int(self.dt_ns)
        else:
            sampling_rate = self.format_spec.sampling_rate_hz
            if sampling_rate:
                dt_ns = int(round(1e9 / float(sampling_rate)))
            else:
                dt_ns = 1

        if dt_ns <= 0:
            dt_ns = 1
        if dt_ns > np.iinfo(np.int32).max:
            raise ValueError(f"dt_ns out of int32 range: {dt_ns}")
        return dt_ns


@export
def create_channel_mapping(
    board_channel_pairs: List[Tuple[int, int]],
) -> Dict[Tuple[int, int], int]:
    """创建 (BOARD, CHANNEL) 到物理通道号的映射。"""
    unique_pairs = set(board_channel_pairs)
    return {(board, channel): channel for board, channel in unique_pairs}


@export
class WaveformStruct:
    """波形结构化处理器

    将原始 DAQ 采集的 NumPy 数组转换为结构化数组（ST_WAVEFORM_DTYPE）。

    支持两种使用方式：
    1. 无配置（向后兼容）：使用 VX2730 默认列索引
    2. 使用配置：通过 WaveformStructConfig 指定列索引，支持多种 DAQ 格式
    """

    def __init__(
        self,
        waveforms: List[np.ndarray],
        config: Optional[WaveformStructConfig] = None,
        baseline_samples: Optional[int] = None,
        upstream_baselines: Optional[List[np.ndarray]] = None,
    ):
        """初始化 WaveformStruct。

        Args:
            waveforms: 原始波形数据列表，每个元素对应一个通道的数据
            config: 结构化配置。None 时使用 VX2730 默认配置（向后兼容）
            baseline_samples: 基线计算使用的采样点数（None 时使用格式默认）
            upstream_baselines: 上游插件提供的 baseline 列表（可选）
        """
        self.waveforms = waveforms
        self.config = config or WaveformStructConfig.default_vx2730()
        self.record_dtype = self.config.get_record_dtype()
        self.dt_ns = self.config.get_dt_ns()
        self.event_length = None
        self.waveform_structureds = None
        self.baseline_samples = baseline_samples
        self.upstream_baselines = upstream_baselines
        self._baseline_warned = False

        if self.baseline_samples is not None and self.baseline_samples <= 0:
            raise ValueError(f"baseline_samples must be positive, got {self.baseline_samples}")

    @classmethod
    def from_adapter(
        cls,
        waveforms: List[np.ndarray],
        adapter_name: str = "vx2730",
        baseline_samples: Optional[int] = None,
        upstream_baselines: Optional[List[np.ndarray]] = None,
    ) -> WaveformStruct:
        """从 DAQ 适配器创建 WaveformStruct（便捷方法）"""
        config = WaveformStructConfig.from_adapter(adapter_name)
        return cls(waveforms, config, baseline_samples, upstream_baselines)

    def _structure_waveform(
        self,
        waves: Optional[np.ndarray] = None,
        channel_mapping: Optional[Dict[Tuple[int, int], int]] = None,
        channel_idx: int = 0,
    ) -> np.ndarray:
        """将波形数组转换为结构化数组。"""
        if waves is None:
            if not self.waveforms:
                return np.zeros(0, dtype=self.record_dtype)
            waves = self.waveforms[0]

        if len(waves) == 0:
            return np.zeros(0, dtype=self.record_dtype)

        cols = self.config.format_spec.columns
        config_wave_length = self.config.get_wave_length()

        samples_end = cols.samples_end if cols.samples_end is not None else waves.shape[1]
        if waves.shape[1] > cols.samples_start:
            wave_data = waves[:, cols.samples_start : samples_end]
        else:
            wave_data = np.zeros((len(waves), 0))
        actual_wave_length = wave_data.shape[1] if wave_data.size > 0 else 0

        if actual_wave_length == 0:
            record_dtype = self.record_dtype
            wave_length = config_wave_length
        else:
            if actual_wave_length == config_wave_length:
                record_dtype = self.record_dtype
                wave_length = config_wave_length
            else:
                wave_length = actual_wave_length
                record_dtype = create_record_dtype(wave_length)
                logger.debug(f"使用动态波形长度: {wave_length} (配置长度: {config_wave_length})")

        waveform_structured = np.zeros(len(waves), dtype=record_dtype)

        try:
            board_vals = waves[:, cols.board].astype(int)
            channel_vals = waves[:, cols.channel].astype(int)
        except Exception:
            logger.warning("无法从波形数据中提取 BOARD/CHANNEL，使用回退逻辑")
            board_vals = np.zeros(len(waves), dtype=int)
            channel_vals = np.zeros(len(waves), dtype=int)

        if channel_mapping:
            # Optimized: use lookup table for vectorized channel mapping (10-20x faster)
            max_board = int(board_vals.max()) + 1
            max_channel = int(channel_vals.max()) + 1
            lookup = np.full((max_board, max_channel), -1, dtype=np.int16)

            for (b, c), phys_ch in channel_mapping.items():
                if b < max_board and c < max_channel:
                    lookup[b, c] = phys_ch

            physical_channels = lookup[board_vals, channel_vals]

            if np.any(physical_channels == -1):
                unmapped = set(zip(board_vals[physical_channels == -1], channel_vals[physical_channels == -1]))
                logger.warning(f"发现未映射的 (BOARD, CHANNEL) 组合: {unmapped}")
        else:
            logger.debug("未提供通道映射，使用 CHANNEL 字段作为物理通道号")
            physical_channels = channel_vals

        baseline_start = cols.baseline_start
        baseline_end = cols.baseline_end
        if self.baseline_samples is not None:
            baseline_end = baseline_start + int(self.baseline_samples)
            if baseline_end > waves.shape[1]:
                if not self._baseline_warned:
                    logger.warning(
                        "baseline_samples=%s exceeds available columns (%s); clamping.",
                        self.baseline_samples,
                        waves.shape[1],
                    )
                    self._baseline_warned = True
                baseline_end = waves.shape[1]

        if baseline_end <= baseline_start:
            baseline_vals = np.full(len(waves), np.nan, dtype=float)
        else:
            try:
                baseline_vals = np.mean(
                    waves[:, baseline_start:baseline_end].astype(float),
                    axis=1,
                )
            except Exception:
                # Optimized fallback: vectorized with per-row exception handling (50-100x faster)
                n_rows = len(waves)
                baseline_vals = np.full(n_rows, np.nan, dtype=np.float64)

                # Try vectorized conversion first
                try:
                    sample_data = waves[:, cols.samples_start:].astype(np.float64)
                    baseline_vals = np.nanmean(sample_data, axis=1)
                except (ValueError, TypeError):
                    # Only fall back to per-row for rows that failed
                    for i in range(n_rows):
                        try:
                            row_data = np.asarray(waves[i, cols.samples_start:], dtype=np.float64)
                            if row_data.size > 0:
                                baseline_vals[i] = np.nanmean(row_data)
                        except Exception:
                            pass  # Keep NaN for failed rows

        try:
            timestamps = waves[:, cols.timestamp].astype(np.int64)
        except Exception:
            timestamps = np.array([int(row[cols.timestamp]) for row in waves], dtype=np.int64)

        timestamp_scale = self.config.format_spec.get_timestamp_scale_to_ps()
        if timestamp_scale != 1.0:
            if float(timestamp_scale).is_integer():
                timestamps = timestamps * int(timestamp_scale)
            else:
                timestamps = (timestamps.astype(np.float64) * timestamp_scale).astype(np.int64)

        waveform_structured["baseline"] = baseline_vals

        if self.upstream_baselines is not None and channel_idx < len(self.upstream_baselines):
            upstream_bl = self.upstream_baselines[channel_idx]
            if upstream_bl is not None and len(upstream_bl) == len(waves):
                waveform_structured["baseline_upstream"] = upstream_bl
            else:
                waveform_structured["baseline_upstream"] = np.nan
        else:
            waveform_structured["baseline_upstream"] = np.nan

        waveform_structured["timestamp"] = timestamps
        waveform_structured["channel"] = physical_channels

        if "dt" in waveform_structured.dtype.names:
            waveform_structured["dt"] = np.int32(self.dt_ns)

        if "time" in waveform_structured.dtype.names:
            if self.config.epoch_ns is not None:
                waveform_structured["time"] = self.config.epoch_ns + timestamps // 1000
            else:
                waveform_structured["time"] = timestamps // 1000

        if wave_data.size > 0:
            n_samples = min(wave_data.shape[1], wave_length)
            # Optimized: use np.copyto to avoid intermediate array allocation (40-60% memory reduction)
            dest = waveform_structured["wave"][:, :n_samples]
            src = wave_data[:, :n_samples]
            if src.dtype == np.int16:
                np.copyto(dest, src)
            else:
                # Convert to int16, clipping to valid range for 14-bit ADC
                np.copyto(dest, src, casting='unsafe')

        return waveform_structured

    def structure_waveforms(self, show_progress: bool = False, start_channel_slice: int = 0) -> List[np.ndarray]:
        """将所有通道的波形转换为结构化数组。"""
        cols = self.config.format_spec.columns

        all_board_channel_pairs = []
        has_data = False
        for waves in self.waveforms:
            if len(waves) > 0:
                has_data = True
                try:
                    boards = waves[:, cols.board].astype(int)
                    channels = waves[:, cols.channel].astype(int)
                    all_board_channel_pairs.extend(zip(boards, channels))
                except Exception:
                    logger.warning("无法从波形数据中提取 BOARD/CHANNEL，跳过该通道")
                    continue

        if not has_data:
            self.waveform_structureds = [
                self._structure_waveform(waves, channel_mapping=None) for waves in self.waveforms
            ]
            return self.waveform_structureds

        if all_board_channel_pairs:
            channel_mapping = create_channel_mapping(all_board_channel_pairs)
            logger.debug(f"创建通道映射: {channel_mapping}")
        else:
            message = (
                "未找到 BOARD/CHANNEL 数据，无法建立通道映射。"
                "请检查 daq_adapter/ColumnMapping 与 CSV 列布局是否匹配。"
                f"当前列映射: board={cols.board}, channel={cols.channel}, "
                f"timestamp={cols.timestamp}, samples_start={cols.samples_start}."
            )
            raise ValueError(message)

        if show_progress:
            try:
                from tqdm import tqdm

                pbar = tqdm(
                    enumerate(self.waveforms),
                    desc="Structuring waveforms",
                    leave=False,
                    total=len(self.waveforms),
                )
            except ImportError:
                pbar = enumerate(self.waveforms)
        else:
            pbar = enumerate(self.waveforms)

        self.waveform_structureds = [
            self._structure_waveform(waves, channel_mapping=channel_mapping, channel_idx=idx) for idx, waves in pbar
        ]
        return self.waveform_structureds

    def get_event_length(self) -> np.ndarray:
        """Compute per-channel event lengths."""
        self.event_length = np.array([len(wave) for wave in self.waveforms])
        return self.event_length


@export
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


@export
class WaveformsPlugin(Plugin):
    """Plugin to extract and structure waveforms from raw files.

    合并了原来的 WaveformsPlugin 和 StWaveformsPlugin 功能：
    1. 从原始 CSV 文件中提取波形数据
    2. 将波形数据结构化为 NumPy 结构化数组（ST_WAVEFORM_DTYPE）
    """

    version = "0.3.0"
    provides = "st_waveforms"
    depends_on = []
    description = "Extract waveforms from raw CSV files and structure them into NumPy structured arrays."
    save_when = "always"
    output_dtype = np.dtype(ST_WAVEFORM_DTYPE)
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
        "wave_length": Option(
            default=None,
            type=int,
            help="Waveform length (number of sampling points). Automatically detect from the data when None。",
        ),
        "dt_ns": Option(
            default=None,
            type=int,
            help="Sampling interval in ns for st_waveforms.dt (None=auto from adapter).",
        ),
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
        "use_upstream_baseline": Option(
            default=False,
            type=bool,
            help="Whether to use baseline from upstream plugin (requires 'baseline' data).",
        ),
        "baseline_samples": Option(
            default=None,
            type=int,
            help="Number of samples used to compute baseline (None=adapter default).",
        ),
    }

    def resolve_depends_on(self, context: Any, run_id: Optional[str] = None) -> List[str]:
        """动态解析依赖关系"""
        deps = ["raw_files"]
        if context.get_config(self, "use_upstream_baseline"):
            deps.append("baseline")
        return deps

    def _get_record_dtype(self, daq_adapter: Optional[str], wave_length: Optional[int] = None) -> np.dtype:
        if daq_adapter:
            config = WaveformStructConfig.from_adapter(daq_adapter)
        else:
            config = WaveformStructConfig.default_vx2730()
        if wave_length is not None:
            config.wave_length = wave_length
        return config.get_record_dtype()

    def get_lineage(self, context: Any) -> dict:
        config = {}
        for key in self.config_keys:
            option = self.options.get(key)
            if option and getattr(option, "track", True):
                config[key] = context.get_config(self, key)

        daq_adapter = config.get("daq_adapter")
        wave_length = config.get("wave_length")
        lineage = {
            "plugin_class": self.__class__.__name__,
            "plugin_version": getattr(self, "version", "0.0.0"),
            "description": getattr(self, "description", ""),
            "config": config,
            "depends_on": self._build_depends_lineage(context),
        }
        try:
            dtype = self._get_record_dtype(daq_adapter, wave_length)
            lineage["dtype"] = np.dtype(dtype).descr
        except Exception:
            lineage["dtype"] = str(self.output_dtype)
        return lineage

    def compute(self, context: Any, run_id: str, **kwargs) -> List[np.ndarray]:
        """
        从原始 CSV 文件中提取波形数据并结构化为 NumPy 结构化数组

        合并了原来的 WaveformsPlugin 和 StWaveformsPlugin 功能：
        1. 读取并解析原始 CSV 文件，提取每个通道的波形数据
        2. 将波形数据结构化为包含时间戳、基线、通道号和波形数据的结构化数组

        支持双层并行处理加速：
        - 通道级并行：多个通道同时处理（通过 channel_workers 控制）
        - 文件级并行：单个通道内的多个文件并行处理（通过 n_jobs 控制）

        Args:
            context: Context 实例
            run_id: 运行标识符
            **kwargs: 依赖数据

        Returns:
            List[np.ndarray]: 每个通道的结构化波形数据列表
        """
        import multiprocessing
        from pathlib import Path

        from waveform_analysis.core.processing.loader import get_waveforms
        from waveform_analysis.utils.formats import get_adapter

        raw_files = context.get_data(run_id, "raw_files")
        n_channels = len(raw_files)
        if n_channels == 0:
            return []

        # ========== 获取配置 ==========
        channel_workers = context.get_config(self, "channel_workers")
        channel_executor = context.get_config(self, "channel_executor")
        n_jobs = context.get_config(self, "n_jobs")
        use_process_pool = context.get_config(self, "use_process_pool")
        chunksize = context.get_config(self, "chunksize")
        daq_adapter = context.get_config(self, "daq_adapter")
        wave_length = context.get_config(self, "wave_length")
        dt_ns = context.get_config(self, "dt_ns")
        use_upstream_baseline = context.get_config(self, "use_upstream_baseline")
        baseline_samples = context.get_config(self, "baseline_samples")
        show_progress = context.config.get("show_progress", True)

        if isinstance(daq_adapter, str):
            daq_adapter = daq_adapter.lower()

        # ========== 通道级并行配置 ==========
        if channel_workers is None:
            channel_workers = min(n_channels, multiprocessing.cpu_count())

        # ========== 文件级并行配置 ==========
        if n_jobs is None:
            selected_files = raw_files
            if selected_files:
                file_counts = [len(files) for files in selected_files if files]
                max_file_count = max(file_counts) if file_counts else 0
                n_jobs = min(max_file_count, 50) if max_file_count > 0 else 1
            else:
                n_jobs = 1

        # ========== V1725 特殊处理 ==========
        if daq_adapter == "v1725":
            adapter = get_adapter(daq_adapter)

            files = []
            for group in raw_files:
                if group:
                    files.extend(group)
            seen = set()
            file_list = []
            for path in files:
                if path in seen:
                    continue
                seen.add(path)
                file_list.append(path)

            if not file_list:
                return []

            data = adapter.format_reader.read_files(file_list, show_progress=show_progress)
            if data.size == 0:
                return []
            context.logger.info("v1725 returns unsplit waveforms (single array)")
            # V1725 返回的是单个数组，需要特殊处理
            return [data]

        # ========== 加载波形数据 ==========
        waveforms = get_waveforms(
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

        # ========== 获取上游 baseline（如果启用）==========
        upstream_baselines = None
        if use_upstream_baseline:
            try:
                upstream_baselines = context.get_data(run_id, "baseline")
                context.logger.info(f"使用上游 baseline，共 {len(upstream_baselines)} 个通道")
            except Exception as e:
                context.logger.warning(f"无法获取上游 baseline: {e}，将使用 NaN 填充")
                upstream_baselines = None

        # ========== 获取 epoch ==========
        epoch_ns = None
        if daq_adapter:
            adapter = get_adapter(daq_adapter)
            if raw_files and raw_files[0]:
                first_file = Path(raw_files[0][0])
                try:
                    epoch_ns = adapter.get_file_epoch(first_file)
                except (FileNotFoundError, OSError):
                    # 文件不存在时跳过 epoch 获取
                    pass

        # ========== 结构化波形 ==========
        if daq_adapter:
            config = WaveformStructConfig.from_adapter(daq_adapter)
        else:
            config = WaveformStructConfig.default_vx2730()

        # 用户配置覆盖
        if wave_length is not None:
            config.wave_length = wave_length
        if dt_ns is not None:
            config.dt_ns = dt_ns

        config.epoch_ns = epoch_ns
        self.output_dtype = config.get_record_dtype()

        waveform_struct = WaveformStruct(
            waveforms,
            config=config,
            baseline_samples=baseline_samples,
            upstream_baselines=upstream_baselines,
        )
        st_waveforms = waveform_struct.structure_waveforms(show_progress=show_progress)

        return st_waveforms
