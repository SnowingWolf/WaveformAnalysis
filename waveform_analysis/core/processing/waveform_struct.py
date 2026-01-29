# -*- coding: utf-8 -*-
"""
Waveform structuring utilities.

包含 WaveformStruct/WaveformStructConfig 等结构化工具。
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import numpy as np

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.processing.dtypes import (
    DEFAULT_WAVE_LENGTH as _DEFAULT_WAVE_LENGTH,
)
from waveform_analysis.core.processing.dtypes import (
    ST_WAVEFORM_DTYPE as _ST_WAVEFORM_DTYPE,
)
from waveform_analysis.core.processing.dtypes import (
    create_record_dtype as _create_record_dtype,
)

if TYPE_CHECKING:
    from waveform_analysis.utils.formats.base import FormatSpec

# Setup logger
logger = logging.getLogger(__name__)

# 初始化 exporter
export, __all__ = exporter()

DEFAULT_WAVE_LENGTH = export(_DEFAULT_WAVE_LENGTH, name="DEFAULT_WAVE_LENGTH")
ST_WAVEFORM_DTYPE = export(_ST_WAVEFORM_DTYPE, name="ST_WAVEFORM_DTYPE")
create_record_dtype = export(_create_record_dtype, name="create_record_dtype")


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
        return cls(format_spec=adapter.format_spec, wave_length=adapter.format_spec.expected_samples)
                   
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
        """获取对应的 ST_WAVEFORM_DTYPE

        Returns:
            根据波形长度动态创建的 ST_WAVEFORM_DTYPE
        """
        return create_record_dtype(self.get_wave_length())


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

    将原始 DAQ 采集的 NumPy 数组转换为结构化数组（ST_WAVEFORM_DTYPE）。

    支持两种使用方式：
    1. 无配置（向后兼容）：使用 VX2730 默认列索引
    2. 使用配置：通过 WaveformStructConfig 指定列索引，支持多种 DAQ 格式

    Attributes:
        waveforms: 原始波形数据列表
        config: 结构化配置（列映射、波形长度等）
        record_dtype: 根据配置创建的 ST_WAVEFORM_DTYPE
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
        config: Optional[WaveformStructConfig] = None,
        upstream_baselines: Optional[List[np.ndarray]] = None,
    ):
        """初始化 WaveformStruct。

        Args:
            waveforms: 原始波形数据列表，每个元素对应一个通道的数据
            config: 结构化配置。None 时使用 VX2730 默认配置（向后兼容）
            upstream_baselines: 上游插件提供的 baseline 列表（可选）
                               每个元素是一个通道的 baseline 数组
        """
        self.waveforms = waveforms
        self.config = config or WaveformStructConfig.default_vx2730()
        self.record_dtype = self.config.get_record_dtype()
        self.event_length = None
        self.waveform_structureds = None
        self.upstream_baselines = upstream_baselines

    @classmethod
    def from_adapter(
        cls,
        waveforms: List[np.ndarray],
        adapter_name: str = "vx2730",
        upstream_baselines: Optional[List[np.ndarray]] = None,
    ) -> "WaveformStruct":
        """从 DAQ 适配器创建 WaveformStruct（便捷方法）

        Args:
            waveforms: 原始波形数据列表
            adapter_name: 适配器名称（如 'vx2730'）
            upstream_baselines: 上游插件提供的 baseline 列表（可选）

        Returns:
            WaveformStruct 实例

        示例:
            >>> struct = WaveformStruct.from_adapter(waveforms, "vx2730")
        """
        config = WaveformStructConfig.from_adapter(adapter_name)
        return cls(waveforms, config, upstream_baselines)

    def _structure_waveform(
        self,
        waves: Optional[np.ndarray] = None,
        channel_mapping: Optional[Dict[Tuple[int, int], int]] = None,
        channel_idx: int = 0,
    ) -> np.ndarray:
        """将波形数组转换为结构化数组。

        参数:
            waves: 波形数组，如果为 None 则使用第一个通道
            channel_mapping: (BOARD, CHANNEL) 到物理通道号的映射字典
            channel_idx: 当前通道索引，用于获取对应的 upstream_baseline
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
            wave_data = waves[:, cols.samples_start : samples_end]
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
                logger.debug(f"使用动态波形长度: {wave_length} (配置长度: {config_wave_length})")

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
                channel_mapping.get((int(b), int(c)), -1) for b, c in zip(board_vals, channel_vals)
            ])
            # 检查是否有未映射的通道
            if np.any(physical_channels == -1):
                unmapped = set(zip(board_vals[physical_channels == -1], channel_vals[physical_channels == -1]))
                logger.warning(f"发现未映射的 (BOARD, CHANNEL) 组合: {unmapped}")
        else:
            # 回退：只使用 CHANNEL（向后兼容）
            logger.debug("未提供通道映射，使用 CHANNEL 字段作为物理通道号")
            physical_channels = channel_vals

        # Safely compute baseline（使用配置的基线范围）
        try:
            baseline_vals = np.mean(waves[:, cols.baseline_start : cols.baseline_end].astype(float), axis=1)
        except Exception:
            # Fallback: compute per-row mean for rows that have enough samples
            baselines = []
            for row in waves:
                try:
                    vals = np.asarray(row[cols.samples_start :], dtype=float)
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
            timestamps = np.array([int(row[cols.timestamp]) for row in waves], dtype=np.int64)

        # 统一时间戳单位为 ps（不同 DAQ 适配器使用不同单位）
        timestamp_scale = self.config.format_spec.get_timestamp_scale_to_ps()
        if timestamp_scale != 1.0:
            if float(timestamp_scale).is_integer():
                timestamps = timestamps * int(timestamp_scale)
            else:
                timestamps = (timestamps.astype(np.float64) * timestamp_scale).astype(np.int64)

        waveform_structured["baseline"] = baseline_vals

        # 赋值 baseline_upstream 字段（新增逻辑）
        if self.upstream_baselines is not None and channel_idx < len(self.upstream_baselines):
            upstream_bl = self.upstream_baselines[channel_idx]
            if upstream_bl is not None and len(upstream_bl) == len(waves):
                waveform_structured["baseline_upstream"] = upstream_bl
            else:
                # 长度不匹配或为 None，填充 NaN
                waveform_structured["baseline_upstream"] = np.nan
        else:
            # 没有上游 baseline，填充 NaN
            waveform_structured["baseline_upstream"] = np.nan

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

    def structure_waveforms(self, show_progress: bool = False, start_channel_slice: int = 0) -> List[np.ndarray]:
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

        # 处理无数据情况
        if not has_data:
            self.waveform_structureds = [
                self._structure_waveform(waves, channel_mapping=None) for waves in self.waveforms
            ]
            return self.waveform_structureds
        # 创建通道映射
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

                pbar = tqdm(
                    enumerate(self.waveforms), desc="Structuring waveforms", leave=False, total=len(self.waveforms)
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
        """Compute per-channel event lengths.

        Each channel uses its own actual event count (no forced pairing).
        """
        # 每个通道使用自己的实际长度，不再强制配对
        self.event_length = np.array([len(wave) for wave in self.waveforms])
        return self.event_length
