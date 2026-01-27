# -*- coding: utf-8 -*-
"""
Processor 模块 - 波形信号处理与特征提取核心逻辑。

本模块负责将原始 DAQ 采集的 NumPy 数组转换为结构化数据，并执行物理特征提取。
核心功能包括：
1. **数据结构化**：定义 `RECORD_DTYPE` (波形+元数据) 与 `PEAK_DTYPE` (脉冲特征)。
2. **特征提取**：提供 `find_hits` (向量化寻峰)、基线扣除、电荷积分 (Charge) 与幅度 (Peak) 计算。
3. **链式处理**：通过 `WaveformStruct` 维护波形结构化逻辑，支持流式或批处理流程。
4. **事件聚类**：`group_multi_channel_hits` 基于时间窗口将多通道 Hit 聚类为物理事件。
5. **通道编码**：提供二进制掩码 (Bitmask) 与权重编码工具，用于多通道符合逻辑筛选。

主要类说明：
- `WaveformStruct`: 处理原始数组到结构化 `RECORD_DTYPE` 的转换，管理时间戳索引与配对长度。
- `WaveformStructConfig`: 波形结构化配置类，解耦 DAQ 设备依赖。
- `WaveformProcessor`: 高层封装接口，支持批量处理数据块 (Chunks) 并构建 Pandas DataFrame。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import warnings
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from waveform_analysis.core.execution.manager import get_executor
from waveform_analysis.core.foundation.constants import FeatureDefaults
from waveform_analysis.core.foundation.utils import exporter

if TYPE_CHECKING:
    from waveform_analysis.utils.formats.base import FormatSpec

# Setup logger
logger = logging.getLogger(__name__)

# 尝试导入numba（可选）
try:
    from numba import jit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # 定义占位符
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    prange = range

# 初始化 exporter
export, __all__ = exporter()

# Strax-inspired dtypes for structured data
# Record: A single waveform with metadata
DEFAULT_WAVE_LENGTH = export(800, name="DEFAULT_WAVE_LENGTH")

RECORD_DTYPE = export(

    [
        ("baseline", "f8"),  # float64 for baseline
        ("timestamp", "i8"),  # int64 for ps-level timestamps (ADC raw)
        ("event_length", "i8"),  # length of the event
        ("channel", "i2"),  # int16 for channel index (physical channel number)
        ("wave", "f4", (DEFAULT_WAVE_LENGTH,)),  # fixed length array for performance

    ],
    name="RECORD_DTYPE",
)


@export
def create_record_dtype(wave_length: int) -> np.dtype:
    """
    根据实际的波形长度动态创建 RECORD_DTYPE。

    参数:
        wave_length: 波形数据的实际长度（采样点数）

    返回:
        动态创建的 RECORD_DTYPE，wave 字段长度为 wave_length

    示例:
        >>> dtype = create_record_dtype(1600)
        >>> arr = np.zeros(10, dtype=dtype)
        >>> print(arr["wave"].shape)  # (10, 1600)
    """
    return np.dtype([
        ("baseline", "f8"),  # float64 for baseline
        ("timestamp", "i8"),  # int64 for ps-level timestamps (ADC raw)
        ("event_length", "i8"),  # length of the event
        ("channel", "i2"),  # int16 for channel index (physical channel number)
        ("wave", "f4", (wave_length,)),  # dynamic length array based on actual data
    ])


@export
@dataclass
class WaveformStructConfig:
    """波形结构化配置 - 解耦 DAQ 设备依赖

    通过配置类封装 DAQ 格式的列映射和波形长度信息，使 WaveformStruct
    不再硬编码 VX2730 特定的列索引。

    Attributes:
        format_spec: DAQ 格式规范（包含列映射、时间戳单位等）
        wave_length: 可选的波形长度覆盖值。None 时使用 format_spec.expected_samples

    示例:
        >>> from waveform_analysis.utils.formats import VX2730_SPEC
        >>> config = WaveformStructConfig(format_spec=VX2730_SPEC)
        >>> print(config.get_wave_length())  # 800

        >>> # 自定义配置
        >>> from waveform_analysis.utils.formats import FormatSpec, ColumnMapping
        >>> custom_spec = FormatSpec(
        ...     name="custom_daq",
        ...     columns=ColumnMapping(
        ...         board=0, channel=1, timestamp=3,
        ...         samples_start=10, baseline_start=10, baseline_end=50
        ...     ),
        ...     expected_samples=1000
        ... )
        >>> config = WaveformStructConfig(format_spec=custom_spec)
    """
    format_spec: "FormatSpec"
    wave_length: Optional[int] = None
    epoch_ns: Optional[int] = None  # 文件创建时间 (Unix ns)

    @classmethod
    def default_vx2730(cls) -> "WaveformStructConfig":
        """返回 VX2730 默认配置（向后兼容）

        Returns:
            使用 VX2730_SPEC 的 WaveformStructConfig 实例

        示例:
            >>> config = WaveformStructConfig.default_vx2730()
            >>> print(config.format_spec.name)  # 'vx2730_csv'
        """
        from waveform_analysis.utils.formats import VX2730_SPEC
        return cls(format_spec=VX2730_SPEC, wave_length=800)

    @classmethod
    def from_adapter(cls, adapter_name: str = "vx2730") -> "WaveformStructConfig":
        """从已注册的 DAQ 适配器创建配置

        Args:
            adapter_name: 适配器名称（如 'vx2730'）

        Returns:
            WaveformStructConfig 实例

        Raises:
            ValueError: 如果适配器未注册

        示例:
            >>> config = WaveformStructConfig.from_adapter("vx2730")
        """
        from waveform_analysis.utils.formats import get_adapter
        adapter = get_adapter(adapter_name)
        return cls(
            format_spec=adapter.format_spec,
            wave_length=adapter.format_spec.expected_samples
        )

    def get_wave_length(self) -> int:
        """获取实际波形长度

        优先级: wave_length > format_spec.expected_samples > DEFAULT_WAVE_LENGTH

        Returns:
            波形长度（采样点数）
        """
        if self.wave_length is not None:
            return self.wave_length
        if self.format_spec.expected_samples is not None:
            return self.format_spec.expected_samples
        return DEFAULT_WAVE_LENGTH

    def get_record_dtype(self) -> np.dtype:
        """获取对应的 RECORD_DTYPE

        Returns:
            根据波形长度动态创建的 RECORD_DTYPE
        """
        return create_record_dtype(self.get_wave_length())

# Peak: A detected peak in a waveform
PEAK_DTYPE = export(
    [
        ("time", "i8"),  # time of the peak
        ("area", "f4"),  # area of the peak
        ("height", "f4"),  # height of the peak
        ("width", "f4"),  # width of the peak
        ("channel", "i2"),  # channel index
        ("event_index", "i8"),  # index of the event in the dataset
    ],
    name="PEAK_DTYPE", 
)


@export
def find_hits(
    waves: np.ndarray,
    baselines: np.ndarray,
    threshold: float,
    left_extension: int = 2,
    right_extension: int = 2,
) -> np.ndarray:
    """
    Vectorized hit-finding. Finds contiguous regions where (baseline - wave) > threshold.

    Args:
        waves: 2D array of waveforms (n_events, n_samples)
        baselines: 1D array of baselines (n_events)
        threshold: threshold for hit detection
        left_extension: number of samples to extend hit to the left
        right_extension: number of samples to extend hit to the right

    Returns:
        A structured array of hits (PEAK_DTYPE).
        Note: This returns a flat array of all hits found across all events.
    """
    if waves.size == 0:
        return np.zeros(0, dtype=PEAK_DTYPE)

    # Signal is baseline - wave (assuming negative pulses)
    signal = baselines[:, np.newaxis] - waves
    mask = signal > threshold

    # Find starts and ends of contiguous regions
    # We pad with False to catch hits at the boundaries
    mask_padded = np.pad(mask, ((0, 0), (1, 1)), mode="constant", constant_values=False)
    diff = np.diff(mask_padded.astype(np.int8), axis=1)

    starts = np.where(diff == 1)
    ends = np.where(diff == -1)

    # starts and ends are tuples (event_indices, sample_indices)
    event_indices = starts[0]
    s_starts = starts[1]
    s_ends = ends[1]

    n_hits = len(event_indices)
    hits = np.zeros(n_hits, dtype=PEAK_DTYPE)

    hits["event_index"] = event_indices
    hits["time"] = s_starts  # Relative to start of waveform
    # Note: area, height, width calculation would go here or in a separate step
    # For now we just return the hits with time and event_index
    return hits


@export
def create_channel_mapping(board_channel_pairs: List[Tuple[int, int]]) -> Dict[Tuple[int, int], int]:
    """
    创建 (BOARD, CHANNEL) 到物理通道号的映射。

    物理通道号直接使用 CHANNEL 值（假设所有数据来自同一个 BOARD）。

    参数:
        board_channel_pairs: (BOARD, CHANNEL) 元组列表

    返回:
        映射字典：{(BOARD, CHANNEL): 物理通道号}

    示例:
        >>> pairs = [(0, 0), (0, 2), (0, 3)]
        >>> mapping = create_channel_mapping(pairs)
        >>> mapping
        {(0, 0): 0, (0, 2): 2, (0, 3): 3}
    """
    unique_pairs = set(board_channel_pairs)
    # 物理通道号直接使用 CHANNEL 值
    return {(board, channel): channel for board, channel in unique_pairs}


@export
class WaveformStruct:
    """波形结构化处理器

    将原始 DAQ 采集的 NumPy 数组转换为结构化数组（RECORD_DTYPE）。

    支持两种使用方式：
    1. 无配置（向后兼容）：使用 VX2730 默认列索引
    2. 使用配置：通过 WaveformStructConfig 指定列索引，支持多种 DAQ 格式

    Attributes:
        waveforms: 原始波形数据列表
        config: 结构化配置（列映射、波形长度等）
        record_dtype: 根据配置创建的 RECORD_DTYPE
        event_length: 每个通道的事件数
        waveform_structureds: 结构化后的波形数据

    示例:
        >>> # 方式1: 向后兼容（无参数，默认 VX2730）
        >>> struct = WaveformStruct(waveforms)
        >>> st_waveforms = struct.structure_waveforms()

        >>> # 方式2: 使用配置
        >>> config = WaveformStructConfig.default_vx2730()
        >>> struct = WaveformStruct(waveforms, config=config)

        >>> # 方式3: 从适配器名称创建
        >>> struct = WaveformStruct.from_adapter(waveforms, "vx2730")

        >>> # 方式4: 自定义格式
        >>> from waveform_analysis.utils.formats import FormatSpec, ColumnMapping
        >>> custom_spec = FormatSpec(
        ...     name="custom_daq",
        ...     columns=ColumnMapping(timestamp=3, samples_start=10),
        ...     expected_samples=1000
        ... )
        >>> config = WaveformStructConfig(format_spec=custom_spec)
        >>> struct = WaveformStruct(waveforms, config=config)
    """

    def __init__(
        self,
        waveforms: List[np.ndarray],
        config: Optional[WaveformStructConfig] = None
    ):
        """初始化 WaveformStruct。

        Args:
            waveforms: 原始波形数据列表，每个元素对应一个通道的数据
            config: 结构化配置。None 时使用 VX2730 默认配置（向后兼容）
        """
        self.waveforms = waveforms
        self.config = config or WaveformStructConfig.default_vx2730()
        self.record_dtype = self.config.get_record_dtype()
        self.event_length = None
        self.waveform_structureds = None

    @classmethod
    def from_adapter(
        cls,
        waveforms: List[np.ndarray],
        adapter_name: str = "vx2730"
    ) -> "WaveformStruct":
        """从 DAQ 适配器创建 WaveformStruct（便捷方法）

        Args:
            waveforms: 原始波形数据列表
            adapter_name: 适配器名称（如 'vx2730'）

        Returns:
            WaveformStruct 实例

        示例:
            >>> struct = WaveformStruct.from_adapter(waveforms, "vx2730")
        """
        config = WaveformStructConfig.from_adapter(adapter_name)
        return cls(waveforms, config)

    def _structure_waveform(
        self,
        waves: Optional[np.ndarray] = None,
        channel_mapping: Optional[Dict[Tuple[int, int], int]] = None
    ) -> np.ndarray:
        """将波形数组转换为结构化数组。

        参数:
            waves: 波形数组，如果为 None 则使用第一个通道
            channel_mapping: (BOARD, CHANNEL) 到物理通道号的映射字典
        """
        # If no explicit waves passed, use the first channel
        if waves is None:
            if not self.waveforms:
                return np.zeros(0, dtype=self.record_dtype)
            waves = self.waveforms[0]

        # If waves is empty, return an empty structured array
        if len(waves) == 0:
            return np.zeros(0, dtype=self.record_dtype)

        # 从配置获取列映射
        cols = self.config.format_spec.columns
        config_wave_length = self.config.get_wave_length()

        # 确定实际的波形长度（从 samples_start 列开始）
        samples_end = cols.samples_end if cols.samples_end is not None else waves.shape[1]
        if waves.shape[1] > cols.samples_start:
            wave_data = waves[:, cols.samples_start:samples_end]
        else:
            wave_data = np.zeros((len(waves), 0))
        actual_wave_length = wave_data.shape[1] if wave_data.size > 0 else 0

        # 确定使用的 dtype 和波形长度
        if actual_wave_length == 0:
            record_dtype = self.record_dtype
            wave_length = config_wave_length
        else:
            # 如果实际长度与配置长度相同，使用实例 dtype 以保持兼容性
            if actual_wave_length == config_wave_length:
                record_dtype = self.record_dtype
                wave_length = config_wave_length
            else:
                # 使用实际波形长度创建动态 dtype
                wave_length = actual_wave_length
                record_dtype = create_record_dtype(wave_length)
                logger.debug(
                    f"使用动态波形长度: {wave_length} (配置长度: {config_wave_length})"
                )

        waveform_structured = np.zeros(len(waves), dtype=record_dtype)

        # 从 CSV 数据中提取 BOARD 和 CHANNEL（使用配置的列索引）
        try:
            board_vals = waves[:, cols.board].astype(int)
            channel_vals = waves[:, cols.channel].astype(int)
        except Exception:
            # 回退：如果无法读取 BOARD/CHANNEL，使用默认值
            logger.warning("无法从波形数据中提取 BOARD/CHANNEL，使用回退逻辑")
            board_vals = np.zeros(len(waves), dtype=int)
            channel_vals = np.zeros(len(waves), dtype=int)

        # 使用通道映射转换为物理通道号
        if channel_mapping:
            physical_channels = np.array([
                channel_mapping.get((int(b), int(c)), -1)
                for b, c in zip(board_vals, channel_vals)
            ])
            # 检查是否有未映射的通道
            if np.any(physical_channels == -1):
                unmapped = set(zip(
                    board_vals[physical_channels == -1],
                    channel_vals[physical_channels == -1]
                ))
                logger.warning(f"发现未映射的 (BOARD, CHANNEL) 组合: {unmapped}")
        else:
            # 回退：只使用 CHANNEL（向后兼容）
            logger.debug("未提供通道映射，使用 CHANNEL 字段作为物理通道号")
            physical_channels = channel_vals

        # Safely compute baseline（使用配置的基线范围）
        try:
            baseline_vals = np.mean(
                waves[:, cols.baseline_start:cols.baseline_end].astype(float),
                axis=1
            )
        except Exception:
            # Fallback: compute per-row mean for rows that have enough samples
            baselines = []
            for row in waves:
                try:
                    vals = np.asarray(row[cols.samples_start:], dtype=float)
                    if vals.size > 0:
                        baselines.append(np.mean(vals))
                    else:
                        baselines.append(np.nan)
                except Exception:
                    baselines.append(np.nan)
            baseline_vals = np.array(baselines, dtype=float)

        # 提取时间戳（使用配置的列索引）
        try:
            timestamps = waves[:, cols.timestamp].astype(np.int64)
        except Exception:
            # Fallback: extract element from each row
            timestamps = np.array(
                [int(row[cols.timestamp]) for row in waves],
                dtype=np.int64
            )

        # 统一时间戳单位为 ps（不同 DAQ 适配器使用不同单位）
        timestamp_scale = self.config.format_spec.get_timestamp_scale_to_ps()
        if timestamp_scale != 1.0:
            if float(timestamp_scale).is_integer():
                timestamps = timestamps * int(timestamp_scale)
            else:
                timestamps = (timestamps.astype(np.float64) * timestamp_scale).astype(np.int64)

        waveform_structured["baseline"] = baseline_vals
        waveform_structured["timestamp"] = timestamps
        waveform_structured["channel"] = physical_channels

        # 填充 time 字段（绝对系统时间 ns）
        if "time" in waveform_structured.dtype.names:
            if self.config.epoch_ns is not None:
                # time = epoch_ns + timestamp_ps // 1000
                waveform_structured["time"] = self.config.epoch_ns + timestamps // 1000
            else:
                # 默认：相对时间 ns（向后兼容）
                waveform_structured["time"] = timestamps // 1000

        # Vectorized assignment for wave data
        # 使用实际波形长度，但不超过 dtype 中定义的长度
        if wave_data.size > 0:
            n_samples = min(wave_data.shape[1], wave_length)
            waveform_structured["wave"][:, :n_samples] = wave_data[:, :n_samples].astype(np.float32)

        return waveform_structured

    def structure_waveforms(
        self,
        show_progress: bool = False,
        start_channel_slice: int = 0
    ) -> List[np.ndarray]:
        """将所有通道的波形转换为结构化数组。

        参数:
            show_progress: 是否显示进度条
            start_channel_slice: 起始通道偏移量（保留以兼容，已弃用）
        """
        # 从配置获取列映射
        cols = self.config.format_spec.columns

        # 第一步：扫描所有波形数据，收集所有唯一的 (BOARD, CHANNEL) 组合
        all_board_channel_pairs = []
        has_data = False
        for waves in self.waveforms:
            if len(waves) > 0:
                has_data = True
                try:
                    # 从 CSV 数据中提取 BOARD 和 CHANNEL（使用配置的列索引）
                    boards = waves[:, cols.board].astype(int)
                    channels = waves[:, cols.channel].astype(int)
                    all_board_channel_pairs.extend(zip(boards, channels))
                except Exception:
                    logger.warning("无法从波形数据中提取 BOARD/CHANNEL，跳过该通道")
                    continue

        # 创建 (BOARD, CHANNEL) 到物理通道号的映射
        if not has_data:
            self.waveform_structureds = [
                self._structure_waveform(waves, channel_mapping=None)
                for waves in self.waveforms
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

        # 第二步：使用映射处理每个通道
        if show_progress:
            try:
                from tqdm import tqdm

                pbar = tqdm(self.waveforms, desc="Structuring waveforms", leave=False)
            except ImportError:
                pbar = self.waveforms
        else:
            pbar = self.waveforms

        self.waveform_structureds = [
            self._structure_waveform(waves, channel_mapping=channel_mapping)
            for waves in pbar
        ]
        return self.waveform_structureds

    def get_event_length(self) -> np.ndarray:
        """Compute per-channel event lengths.

        Each channel uses its own actual event count (no forced pairing).
        """
        # 每个通道使用自己的实际长度，不再强制配对
        self.event_length = np.array([len(wave) for wave in self.waveforms])
        return self.event_length


@export
class WaveformProcessor:
    """
    负责波形处理、特征提取和 DataFrame 构建。
    """

    def __init__(self, n_channels: int = 2):
        """
        初始化波形处理器

        Args:
            n_channels: 通道数量（默认2）

        初始化内容:
        - 通道数配置
        - 默认的峰值和电荷计算范围
        - 特征函数注册字典
        """
        self.n_channels = n_channels
        self.peaks_range = FeatureDefaults.PEAK_RANGE
        self.charge_range = FeatureDefaults.CHARGE_RANGE
        self.feature_fns: Dict[str, Tuple[Callable[..., List[np.ndarray]], Dict[str, Any]]] = {}

    def structure_waveforms(self, waveforms: List[np.ndarray]) -> List[np.ndarray]:
        """
        将原始波形数组转换为结构化数组。
        """
        structurer = WaveformStruct(waveforms)
        return structurer.structure_waveforms()

    def compute_basic_features(
        self,
        st_waveforms: List[np.ndarray],
        peaks_range: Optional[Tuple[int, int]] = None,
        charge_range: Optional[Tuple[int, Optional[int]]] = None,
        waveforms_override: Optional[List[np.ndarray]] = None,
    ) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        计算基础特征：peaks 和 charges。
        
        每个通道使用自己的全部事件数（不再需要 event_length 限制）。
        """
        if peaks_range is not None:
            self.peaks_range = peaks_range
        if charge_range is not None:
            self.charge_range = charge_range

        start_p, end_p = self.peaks_range
        start_c, end_c = self.charge_range

        peaks = []
        charges = []

        for i in range(len(st_waveforms)):
            st_ch = st_waveforms[i]
            if len(st_ch) == 0:
                peaks.append(np.zeros(0))
                charges.append(np.zeros(0))
                continue

            waves = st_ch["wave"]
            if waveforms_override is not None:
                if i < len(waveforms_override):
                    waves = waveforms_override[i]
                else:
                    waves = None

            if waves is None or len(waves) == 0:
                peaks.append(np.zeros(0))
                charges.append(np.zeros(0))
                continue
            if waves.ndim != 2:
                warnings.warn(
                    f"Waveforms for channel {i} are not 2D; skip feature calculation.",
                    UserWarning,
                )
                peaks.append(np.zeros(0))
                charges.append(np.zeros(0))
                continue

            n_events = len(st_ch)
            if waves.shape[0] != n_events:
                n_events = min(waves.shape[0], n_events)
                if n_events == 0:
                    peaks.append(np.zeros(0))
                    charges.append(np.zeros(0))
                    continue
                warnings.warn(
                    f"Waveforms length mismatch on channel {i}: "
                    f"{waves.shape[0]} vs {len(st_ch)}; truncating to {n_events}.",
                    UserWarning,
                )

            # Vectorized peak calculation
            # st_ch["wave"] is (N, DEFAULT_WAVE_LENGTH)
            waves_p = waves[:n_events, start_p:end_p]
            p_vals = np.max(waves_p, axis=1) - np.min(waves_p, axis=1)
            peaks.append(p_vals)

            # Vectorized charge calculation
            waves_c = waves[:n_events, start_c:end_c]
            baselines = st_ch["baseline"][:n_events]
            # baseline - wave, then sum over samples
            q_vals = np.sum(baselines[:, np.newaxis] - waves_c, axis=1)
            charges.append(q_vals)

        return peaks, charges

    def build_dataframe(
        self,
        st_waveforms: List[np.ndarray],
        peaks: List[np.ndarray],
        charges: List[np.ndarray],
        extra_features: Optional[Dict[str, List[np.ndarray]]] = None,
        start_channel_slice: int = 0,
    ) -> pd.DataFrame:
        """
        构建波形 DataFrame。
        
        每个通道使用自己的全部事件数（不再需要 event_length 限制）。
        
        参数:
            start_channel_slice: 起始通道偏移量（保留以向后兼容，但不再使用；通道号现在从st_waveforms中的channel字段读取，该字段由BOARD/CHANNEL映射得到）
        """
        # 使用实际的 st_waveforms 长度，确保处理所有通道
        df = build_waveform_df(
            st_waveforms, peaks, charges, 
            n_channels=len(st_waveforms),  # 使用实际长度而不是 self.n_channels
            start_channel_slice=start_channel_slice
        )

        if extra_features:
            for name, feat_list in extra_features.items():
                # 使用每个特征数组的完整长度
                all_feat = np.concatenate([feat for feat in feat_list])
                df[name] = all_feat

        return df.sort_values("timestamp")

    def process_chunk(
        self,
        chunk: np.ndarray,
        peaks_range: Tuple[int, int],
        charge_range: Tuple[int, Optional[int]],
    ) -> Dict[str, np.ndarray]:
        """
        处理一个数据块，提取特征。
        """
        start_p, end_p = peaks_range
        start_c, end_c = charge_range

        if chunk.shape[1] <= 7:
            return {}

        waves = chunk[:, 7:].astype(float)
        baseline_vals = np.nanmean(waves[:, :40], axis=1)
        ts = chunk[:, 2].astype(np.int64)

        p_seg = waves[:, start_p:end_p]
        c_seg = waves[:, start_c:end_c]

        peaks_vals = np.nanmax(p_seg, axis=1) - np.nanmin(p_seg, axis=1)
        charges_vals = np.nansum(baseline_vals[:, None] - c_seg, axis=1)

        return {
            "baseline": baseline_vals,
            "timestamp": ts,
            "peak": peaks_vals,
            "charge": charges_vals,
        }


@export
def build_waveform_df(
    st_waveforms: List[np.ndarray],
    peaks: List[np.ndarray],
    charges: List[np.ndarray],
    n_channels: Optional[int] = None,
    start_channel_slice: int = 0,
) -> pd.DataFrame:
    """把每个通道的 timestamp / charge / peak / channel 拼成一个 DataFrame.
    
    每个通道使用自己的全部事件数（不再需要 event_length 限制）。
    
    参数:
        n_channels: 通道数量（可选），如果未提供则使用 len(st_waveforms)
        start_channel_slice: 起始通道偏移量（保留以向后兼容，但不再使用；通道号现在从st_waveforms中的channel字段读取，该字段由BOARD/CHANNEL映射得到）
    """
    # 使用实际的 st_waveforms 长度，确保处理所有有数据的通道
    actual_n_channels = len(st_waveforms)
    if n_channels is not None and n_channels != actual_n_channels:
        logger.warning(
            f"build_waveform_df: n_channels ({n_channels}) != len(st_waveforms) ({actual_n_channels}), "
            f"using actual length {actual_n_channels}"
        )
    n_channels = actual_n_channels
    
    # 验证 peaks 和 charges 的长度匹配
    if len(peaks) != n_channels:
        raise ValueError(
            f"peaks list length ({len(peaks)}) != st_waveforms length ({n_channels})"
        )
    if len(charges) != n_channels:
        raise ValueError(
            f"charges list length ({len(charges)}) != st_waveforms length ({n_channels})"
        )
    
    all_timestamps = []
    all_charges = []
    all_peaks = []
    all_channels = []

    for ch in range(n_channels):
        # 使用每个通道的全部事件数
        ts = np.asarray(st_waveforms[ch]["timestamp"])
        qs = np.asarray(charges[ch])
        ps = np.asarray(peaks[ch])

        all_timestamps.append(ts)
        all_charges.append(qs)
        all_peaks.append(ps)
        # 从 st_waveforms 中提取实际的 channel 值（从 BOARD/CHANNEL 映射得到）
        actual_channels = np.asarray(st_waveforms[ch]["channel"])
        all_channels.append(actual_channels)

    all_timestamps = np.concatenate(all_timestamps)
    all_charges = np.concatenate(all_charges)
    all_peaks = np.concatenate(all_peaks)
    all_channels = np.concatenate(all_channels)

    return pd.DataFrame({
        "timestamp": all_timestamps,
        "charge": all_charges,
        "peak": all_peaks,
        "channel": all_channels,
    })


@export
def group_multi_channel_hits(
    df: pd.DataFrame,
    time_window_ns: float,
    use_numba: bool = True,
    n_processes: Optional[int] = None,
) -> pd.DataFrame:
    """
    在 df 中按 timestamp 聚类，找"同一事件的多通道触发"，并在簇内部
    按 channel 从小到大对 (channels, charges, peaks, timestamps) 同步排序。
    
    参数:
        df: 包含 timestamp, channel, charge, peak 列的 DataFrame
            - timestamp 列的单位为 ps（皮秒）
        time_window_ns: 时间窗口（纳秒），默认值为100ns
            - 内部会转换为 ps 单位与 timestamp 进行比较
            - 例如：100ns = 100,000ps
        use_numba: 是否使用numba加速（默认True，如果numba可用）
        n_processes: 多进程数量（None=单进程，>1=多进程，默认None）
    
    注意:
        - timestamp 列的单位为 ps（皮秒）
        - time_window_ns 参数单位为 ns（纳秒），内部会自动转换为 ps 进行比较
        - 时间窗口转换：time_window_ps = time_window_ns * 1e3
    
    性能优化:
        - 使用numba JIT编译加速边界查找（如果可用）
        - 支持多进程并行处理事件簇（适用于超大数据集）
        - 优化DataFrame构建方式
        - 减少不必要的数组复制
    
    示例:
        # 使用numba加速（单进程），时间窗口100ns
        df_events = group_multi_channel_hits(df, time_window_ns=100)
        
        # 使用多进程（4个进程）
        df_events = group_multi_channel_hits(df, time_window_ns=100, n_processes=4)
        
        # 禁用numba，使用多进程
        df_events = group_multi_channel_hits(df, time_window_ns=100, use_numba=False, n_processes=4)
    """
    time_window_ps = time_window_ns * 1e3

    # 先按时间排序一次
    df_sorted = df.sort_values("timestamp").reset_index(drop=True)

    # 一次性取成 numpy 数组，后面循环只处理索引，少做 iloc / array 构造
    ts_all = df_sorted["timestamp"].to_numpy()
    ch_all = df_sorted["channel"].to_numpy()
    q_all = df_sorted["charge"].to_numpy()
    p_all = df_sorted["peak"].to_numpy()

    n = len(df_sorted)
    if n == 0:
        return pd.DataFrame(
            columns=[
                "event_id",
                "t_min",
                "t_max",
                "dt/ns",
                "n_hits",
                "channels",
                "charges",
                "peaks",
                "timestamps",
            ]
        )

    # 查找边界（使用numba加速如果可用）
    if use_numba and NUMBA_AVAILABLE:
        boundaries = _find_cluster_boundaries_numba(ts_all, time_window_ps)
    else:
        boundaries = [0]
        curr = 0
        while curr < n:
            next_idx = np.searchsorted(ts_all, ts_all[curr] + time_window_ps, side="right")
            boundaries.append(next_idx)
            curr = next_idx
        boundaries = np.array(boundaries)

    n_events = len(boundaries) - 1
    
    # 多进程处理（适用于超大数据集）
    if n_processes and n_processes > 1 and n_events > 1000:  # 只有事件数足够多时才使用多进程
        # 将事件分块
        chunk_size = max(1, n_events // n_processes)
        chunks = []
        for i in range(0, n_events, chunk_size):
            chunks.append((i, min(i + chunk_size, n_events)))
        
        # 准备参数
        args_list = [
            (ts_all, ch_all, q_all, p_all, boundaries, start, end)
            for start, end in chunks
        ]
        
        # 多进程处理（使用全局执行器管理器）
        records = []
        from concurrent.futures import as_completed
        
        with get_executor(
            "event_grouping",
            executor_type="process",
            max_workers=n_processes,
            reuse=True
        ) as executor:
            futures = {executor.submit(_process_event_chunk, args): args for args in args_list}
            for future in as_completed(futures):
                try:
                    chunk_records = future.result()
                    records.extend(chunk_records)
                except (MemoryError, KeyboardInterrupt):
                    # 致命错误：立即抛出
                    raise
                except Exception as e:
                    logger.warning(f"Multiprocessing chunk failed ({e}), falling back to single-process")
                    # 可恢复错误：回退到单进程处理该块
                    args = futures[future]
                    chunk_records = _process_event_chunk(args)
                    records.extend(chunk_records)
        
        # 按event_id排序（因为多进程处理顺序可能不同）
        records.sort(key=lambda x: x["event_id"])
        
        # 构建DataFrame
        return pd.DataFrame(records)
    
    else:
        # 单进程处理（优化版本）
        event_ids = np.arange(n_events, dtype=np.int64)
        t_mins = np.zeros(n_events, dtype=np.int64)
        t_maxs = np.zeros(n_events, dtype=np.int64)
        dt_ns = np.zeros(n_events, dtype=np.float64)
        n_hits_list = np.zeros(n_events, dtype=np.int32)
        
        channels_list = []
        charges_list = []
        peaks_list = []
        timestamps_list = []

        # 处理每个事件
        for event_id in range(n_events):
            start, end = boundaries[event_id], boundaries[event_id + 1]

            ts = ts_all[start:end]
            chs = ch_all[start:end]
            qs = q_all[start:end]
            ps = p_all[start:end]

            # 按channel排序
            sort_idx = np.argsort(chs)
            ts_sorted = ts[sort_idx]
            chs_sorted = chs[sort_idx]
            qs_sorted = qs[sort_idx]
            ps_sorted = ps[sort_idx]

            t_min = ts_sorted[0]
            t_max = ts_sorted[-1]

            # 存储结果
            t_mins[event_id] = t_min
            t_maxs[event_id] = t_max
            dt_ns[event_id] = (t_max - t_min) / 1e3
            n_hits_list[event_id] = len(ts_sorted)
            
            channels_list.append(chs_sorted)
            charges_list.append(qs_sorted)
            peaks_list.append(ps_sorted)
            timestamps_list.append(ts_sorted)

        # 使用字典方式构建DataFrame
        return pd.DataFrame({
            "event_id": event_ids,
            "t_min": t_mins,
            "t_max": t_maxs,
            "dt/ns": dt_ns,
            "n_hits": n_hits_list,
            "channels": channels_list,
            "charges": charges_list,
            "peaks": peaks_list,
            "timestamps": timestamps_list,
        })


# Numba加速的边界查找函数（模块级别定义，numba要求）
if NUMBA_AVAILABLE:
    @jit(nopython=True, cache=True)
    def _find_cluster_boundaries_numba(ts_all: np.ndarray, time_window_ps: float) -> np.ndarray:
        """
        使用numba加速的边界查找。
        
        参数:
            ts_all: 已排序的时间戳数组
            time_window_ps: 时间窗口（皮秒）
        
        返回:
            边界索引数组
        """
        n = len(ts_all)
        if n == 0:
            return np.array([0])
        
        boundaries = [0]
        curr = 0
        
        while curr < n:
            target = ts_all[curr] + time_window_ps
            # 二分查找（比searchsorted稍快，因为numba编译）
            left, right = curr, n
            while left < right:
                mid = (left + right) // 2
                if ts_all[mid] <= target:
                    left = mid + 1
                else:
                    right = mid
            next_idx = left
            boundaries.append(next_idx)
            curr = next_idx
        
        return np.array(boundaries)
else:
    def _find_cluster_boundaries_numba(ts_all: np.ndarray, time_window_ps: float) -> np.ndarray:
        """回退到numpy实现"""
        n = len(ts_all)
        if n == 0:
            return np.array([0])
        boundaries = [0]
        curr = 0
        while curr < n:
            next_idx = np.searchsorted(ts_all, ts_all[curr] + time_window_ps, side="right")
            boundaries.append(next_idx)
            curr = next_idx
        return np.array(boundaries)


def _process_event_chunk(args: Tuple) -> List[Dict]:
    """
    处理事件块（用于多进程）。
    
    参数:
        args: (ts_all, ch_all, q_all, p_all, boundaries, start_idx, end_idx)
        注意：numpy数组在多进程间传递时需要确保是可序列化的
    
    返回:
        事件记录列表
    """
    # 解包参数
    ts_all, ch_all, q_all, p_all, boundaries, start_idx, end_idx = args
    
    # 确保是numpy数组（多进程传递后可能变成列表）
    ts_all = np.asarray(ts_all)
    ch_all = np.asarray(ch_all)
    q_all = np.asarray(q_all)
    p_all = np.asarray(p_all)
    boundaries = np.asarray(boundaries)
    
    records = []
    for i in range(start_idx, end_idx):
        if i >= len(boundaries) - 1:
            break
        start, end = int(boundaries[i]), int(boundaries[i + 1])
        
        ts = ts_all[start:end]
        chs = ch_all[start:end]
        qs = q_all[start:end]
        ps = p_all[start:end]
        
        # 按channel排序
        sort_idx = np.argsort(chs)
        ts_sorted = ts[sort_idx]
        chs_sorted = chs[sort_idx]
        qs_sorted = qs[sort_idx]
        ps_sorted = ps[sort_idx]
        
        t_min = int(ts_sorted[0])
        t_max = int(ts_sorted[-1])
        
        records.append({
            "event_id": int(i),
            "t_min": t_min,
            "t_max": t_max,
            "dt/ns": float((t_max - t_min) / 1e3),
            "n_hits": int(len(ts_sorted)),
            "channels": chs_sorted,  # 只读访问，无需复制
            "charges": qs_sorted,
            "peaks": ps_sorted,
            "timestamps": ts_sorted,
        })
    
    return records


GROUP_MAP = {
    0: 1,
    1: 1,  # group0: channels [0,1]
    2: 3,
    3: 3,  # group1: channels [2,3]
    4: 7,
    5: 7,  # group2: channels [4,5]
}

# 组合权重（用于组完整性编码）
GROUP_WEIGHTS = {
    1: {0, 1},  # weight 1 → 组 {0,1}
    3: {2, 3},  # weight 3 → 组 {2,3}
    7: {4, 5},  # weight 7 → 组 {4,5}
}


@export
def encode_groups_binary(channels: List[int]) -> int:
    """
    任意组出现了部分成员（不成对） -> 整体返回 0（异常）
    所有组要么完整出现，要么完全不出现。
    """
    if channels is None or len(channels) == 0:
        return 0

    ch_set = set(map(int, channels))
    code = 0

    for weight, group_members in GROUP_WEIGHTS.items():
        # 交集：channels 中出现了该组里的多少个
        inter = ch_set & group_members

        if len(inter) == 0:
            # 该组完全没出现 → OK
            continue
        elif inter == group_members:
            # 全部出现 → 加权
            code += weight
        else:
            # 只出现部分成员 → 异常
            return 0

    return code


@export
def encode_channels_binary(channels: List[int]) -> int:
    """
    将 channel 列表转换为二进制位掩码。
    例如 [0,3,5] → 1<<0 | 1<<3 | 1<<5 = 41
    """
    if channels is None or len(channels) == 0:
        return 0
    # 向量化位运算
    return int(np.bitwise_or.reduce(1 << np.asarray(channels, dtype=int)))


@export
def encode_channels_binary_legacy(channels: List[int]) -> int:
    """保留旧名称以防万一，但内部使用优化后的版本"""
    return encode_channels_binary(channels)


@export
def mask_to_channels(mask: int) -> List[int]:
    """
    将 bitmask 转回 channel 列表。
    例如 41 (0b101001) → [0,3,5]
    """
    if mask is None or mask == 0:
        return []

    # 使用位运算提取所有置位
    channels = []
    for i in range(mask.bit_length()):
        if (mask >> i) & 1:
            channels.append(i)
    return channels


@export
def channels_to_mask(channels: List[int]) -> int:
    """
    将 channels 列表转换为 bitmask。
    """
    return encode_channels_binary(channels)


@export
def get_paired_data(df_events: pd.DataFrame, group_mask: int, char: str) -> np.ndarray:
    """
    根据 encode_groups_binary 的加权结果筛选事件，
    并返回 (char) 对应的 numpy 数组。
    """

    # 1. 解码：mask → 哪些 group 出现
    # 直接利用 bit 运算：mask 扣哪个 weight，就说明哪个 group 出现
    selected_groups = []
    for weight, members in GROUP_WEIGHTS.items():
        if group_mask & weight:  # bit on → 已包含该 group
            selected_groups.append(sorted(members))

    # print(f"groups {selected_groups} (mask={group_mask})")

    # 2. 过滤 DataFrame
    dft = df_events[df_events["group_code"] == group_mask]

    # 3. 返回目标字段
    return np.array(dft[char].to_list(), dtype=np.float64)


@export
def energy_rec(data: Tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    x, y = data
    energy = np.sqrt(np.prod([x, y], axis=0)) * 2
    return energy


@export
def lr_log_ratio(data: Tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    x, y = data
    log_ratio = np.log(x) - np.log(y)
    return log_ratio


@export
class ResultData:
    def __init__(self, cache_dir: str) -> None:
        """
        初始化结果数据加载器

        从缓存目录加载预处理的 DataFrame 结果。

        Args:
            cache_dir: 缓存目录路径，应包含 df.feather 和 df_events.feather

        Raises:
            FileNotFoundError: 如果缓存文件不存在

        Examples:
            >>> result = ResultData('./cache')
            >>> print(result.df.head())
            >>> print(result.df_events.head())
        """
        self.cache_dir = cache_dir
        df_file = os.path.join(cache_dir, "df.feather")
        event_file = os.path.join(cache_dir, "df_events.feather")

        self.df = pd.read_feather(df_file)
        self.df_events = pd.read_feather(event_file)


@export
def hist_count_ratio(
    data_a: np.ndarray, data_b: np.ndarray, bins: Any
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    counts_a, bin_edges = np.histogram(data_a, bins=bins)
    counts_b, _ = np.histogram(data_b, bins=bins)
    ratio = np.divide(
        counts_a,
        counts_b,
        out=np.zeros_like(counts_a, dtype=float),
        where=counts_b > 0,
    )
    return bin_edges, counts_a, counts_b, ratio
