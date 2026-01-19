# -*- coding: utf-8 -*-
"""
DAQ 数据格式基础定义 - FormatSpec, ColumnMapping, TimestampUnit, FormatReader

本模块定义了 DAQ 数据格式适配器的核心抽象，包括：
- TimestampUnit: 时间戳单位枚举
- ColumnMapping: CSV 列映射配置
- FormatSpec: 格式规范数据类
- FormatReader: 格式读取器抽象基类

Examples:
    >>> from waveform_analysis.utils.formats import FormatSpec, ColumnMapping, TimestampUnit
    >>> spec = FormatSpec(
    ...     name="my_format",
    ...     columns=ColumnMapping(timestamp=3),
    ...     timestamp_unit=TimestampUnit.NANOSECONDS,
    ... )
    >>> print(spec.get_timestamp_scale())  # 1.0 (ns -> ns)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
class TimestampUnit(Enum):
    """时间戳单位枚举

    定义 DAQ 系统中常见的时间戳单位，用于在读取数据时进行单位转换。
    所有时间戳最终会被转换为纳秒 (ns) 作为内部统一单位。

    Attributes:
        PICOSECONDS: 皮秒 (1e-12 秒)
        NANOSECONDS: 纳秒 (1e-9 秒)
        MICROSECONDS: 微秒 (1e-6 秒)
        MILLISECONDS: 毫秒 (1e-3 秒)
        SECONDS: 秒
    """
    PICOSECONDS = "ps"      # 1e-12 秒
    NANOSECONDS = "ns"      # 1e-9 秒
    MICROSECONDS = "us"     # 1e-6 秒
    MILLISECONDS = "ms"     # 1e-3 秒
    SECONDS = "s"           # 1 秒


@export
@dataclass
class ColumnMapping:
    """CSV 列映射配置

    定义 CSV 文件中各数据列的索引位置。不同 DAQ 系统的 CSV 格式可能有不同的列布局，
    通过 ColumnMapping 可以灵活配置列索引。

    Attributes:
        board: BOARD 列索引（板卡编号）
        channel: CHANNEL 列索引（通道编号）
        timestamp: TIMETAG 列索引（时间戳）
        samples_start: 波形采样起始列索引
        samples_end: 波形采样结束列索引（None 表示到行末）
        baseline_start: 基线计算起始列索引
        baseline_end: 基线计算结束列索引

    Examples:
        >>> cols = ColumnMapping(board=0, channel=1, timestamp=2, samples_start=7)
        >>> cols.samples_end  # None，表示到行末
    """
    board: int = 0              # BOARD 列索引
    channel: int = 1            # CHANNEL 列索引
    timestamp: int = 2          # TIMETAG 列索引
    samples_start: int = 7      # 波形采样起始列
    samples_end: Optional[int] = None  # 波形采样结束列 (None = 到末尾)
    baseline_start: int = 7     # 基线计算起始列
    baseline_end: int = 47      # 基线计算结束列


@export
@dataclass
class FormatSpec:
    """DAQ 数据格式规范

    完整描述一种 DAQ 数据格式，包括列映射、时间戳单位、文件模式、头部处理等。

    Attributes:
        name: 格式名称（唯一标识符）
        version: 格式版本号
        columns: 列映射配置
        timestamp_unit: 时间戳单位
        file_pattern: 文件 glob 模式
        header_rows_first_file: 首个文件跳过的头部行数
        header_rows_other_files: 其他文件跳过的头部行数
        delimiter: CSV 分隔符
        expected_samples: 预期的波形采样点数（可选）
        metadata: 额外元数据字典

    Examples:
        >>> spec = FormatSpec(
        ...     name="vx2730_csv",
        ...     columns=ColumnMapping(),
        ...     timestamp_unit=TimestampUnit.PICOSECONDS,
        ...     header_rows_first_file=2,
        ...     expected_samples=800,
        ... )
        >>> spec.get_timestamp_scale()  # 返回 ps -> ns 的转换因子
        0.001
    """
    name: str                           # 格式名称
    version: str = "1.0"                # 格式版本
    columns: ColumnMapping = field(default_factory=ColumnMapping)
    timestamp_unit: TimestampUnit = TimestampUnit.PICOSECONDS
    file_pattern: str = "*CH*.CSV"      # 文件 glob 模式
    header_rows_first_file: int = 2     # 首文件头部行数
    header_rows_other_files: int = 0    # 其他文件头部行数
    delimiter: str = ";"                # CSV 分隔符
    expected_samples: Optional[int] = None  # 预期采样点数
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_timestamp_scale(self) -> float:
        """获取时间戳到纳秒的转换因子

        Returns:
            转换因子，乘以原始时间戳后得到纳秒值
        """
        scales = {
            TimestampUnit.PICOSECONDS: 1e-3,     # ps -> ns
            TimestampUnit.NANOSECONDS: 1.0,      # ns -> ns
            TimestampUnit.MICROSECONDS: 1e3,     # us -> ns
            TimestampUnit.MILLISECONDS: 1e6,     # ms -> ns
            TimestampUnit.SECONDS: 1e9,          # s -> ns
        }
        return scales.get(self.timestamp_unit, 1.0)

    def get_timestamp_scale_to_ps(self) -> float:
        """获取时间戳到皮秒的转换因子

        为了向后兼容，部分代码仍使用皮秒作为内部单位。

        Returns:
            转换因子，乘以原始时间戳后得到皮秒值
        """
        scales = {
            TimestampUnit.PICOSECONDS: 1.0,      # ps -> ps
            TimestampUnit.NANOSECONDS: 1e3,      # ns -> ps
            TimestampUnit.MICROSECONDS: 1e6,     # us -> ps
            TimestampUnit.MILLISECONDS: 1e9,     # ms -> ps
            TimestampUnit.SECONDS: 1e12,         # s -> ps
        }
        return scales.get(self.timestamp_unit, 1.0)


@export
class FormatReader(ABC):
    """DAQ 数据格式读取器抽象基类

    定义了读取 DAQ 数据文件的标准接口。子类需要实现具体的文件读取逻辑。

    Attributes:
        spec: 格式规范

    Examples:
        >>> class MyReader(FormatReader):
        ...     def read_file(self, file_path, is_first_file=True):
        ...         # 实现具体读取逻辑
        ...         pass
        ...     def read_files(self, file_paths, show_progress=False):
        ...         pass
        ...     def read_files_generator(self, file_paths, chunk_size=10):
        ...         pass
    """

    def __init__(self, spec: FormatSpec):
        """初始化格式读取器

        Args:
            spec: 格式规范
        """
        self.spec = spec

    @abstractmethod
    def read_file(
        self,
        file_path: Union[str, Path],
        is_first_file: bool = True
    ) -> np.ndarray:
        """读取单个文件

        Args:
            file_path: 文件路径
            is_first_file: 是否为首个文件（决定是否跳过头部）

        Returns:
            二维 NumPy 数组，每行一条记录
        """
        pass

    @abstractmethod
    def read_files(
        self,
        file_paths: List[Union[str, Path]],
        show_progress: bool = False
    ) -> np.ndarray:
        """读取并堆叠多个文件

        Args:
            file_paths: 文件路径列表
            show_progress: 是否显示进度条

        Returns:
            所有文件数据垂直堆叠后的二维数组
        """
        pass

    @abstractmethod
    def read_files_generator(
        self,
        file_paths: List[Union[str, Path]],
        chunk_size: int = 10
    ) -> Iterator[np.ndarray]:
        """生成器模式读取

        Args:
            file_paths: 文件路径列表
            chunk_size: 每次返回的文件数量

        Yields:
            每个 chunk 的数据数组
        """
        pass

    def extract_columns(self, data: np.ndarray) -> Dict[str, np.ndarray]:
        """从原始数据提取各列

        根据列映射配置，从原始数据中提取 board、channel、timestamp、samples、baseline 等列。

        Args:
            data: 原始数据数组

        Returns:
            包含各列数据的字典:
            - 'board': 板卡编号数组
            - 'channel': 通道编号数组
            - 'timestamp': 时间戳数组（原始单位）
            - 'samples': 波形采样数组
            - 'baseline': 基线值数组
        """
        if data.size == 0:
            return {
                'board': np.array([], dtype=int),
                'channel': np.array([], dtype=int),
                'timestamp': np.array([], dtype=np.int64),
                'samples': np.array([]).reshape(0, 0),
                'baseline': np.array([], dtype=float),
            }

        cols = self.spec.columns

        # 提取各列
        board = data[:, cols.board].astype(int)
        channel = data[:, cols.channel].astype(int)
        timestamp = data[:, cols.timestamp].astype(np.int64)

        # 提取波形采样
        samples_end = cols.samples_end if cols.samples_end is not None else data.shape[1]
        samples = data[:, cols.samples_start:samples_end].astype(float)

        # 计算基线（取均值）
        baseline_data = data[:, cols.baseline_start:cols.baseline_end].astype(float)
        baseline = np.mean(baseline_data, axis=1)

        return {
            'board': board,
            'channel': channel,
            'timestamp': timestamp,
            'samples': samples,
            'baseline': baseline,
        }

    def convert_timestamp_to_ns(self, timestamps: np.ndarray) -> np.ndarray:
        """将时间戳转换为纳秒

        Args:
            timestamps: 原始时间戳数组

        Returns:
            纳秒单位的时间戳数组
        """
        scale = self.spec.get_timestamp_scale()
        if scale == 1.0:
            return timestamps.astype(np.int64)
        return (timestamps * scale).astype(np.int64)

    def convert_timestamp_to_ps(self, timestamps: np.ndarray) -> np.ndarray:
        """将时间戳转换为皮秒（向后兼容）

        Args:
            timestamps: 原始时间戳数组

        Returns:
            皮秒单位的时间戳数组
        """
        scale = self.spec.get_timestamp_scale_to_ps()
        if scale == 1.0:
            return timestamps.astype(np.int64)
        return (timestamps * scale).astype(np.int64)

    def validate_data(self, data: np.ndarray) -> bool:
        """验证数据是否符合格式规范

        检查数据列数是否满足最低要求，以及采样点数是否符合预期。

        Args:
            data: 数据数组

        Returns:
            验证是否通过

        Raises:
            ValueError: 如果数据不符合规范
        """
        if data.size == 0:
            return True

        # 检查最小列数
        min_cols = max(
            self.spec.columns.board,
            self.spec.columns.channel,
            self.spec.columns.timestamp,
            self.spec.columns.samples_start,
        ) + 1

        if data.shape[1] < min_cols:
            raise ValueError(
                f"数据列数不足: 期望至少 {min_cols} 列, 实际 {data.shape[1]} 列"
            )

        # 检查采样点数
        if self.spec.expected_samples is not None:
            samples_end = self.spec.columns.samples_end or data.shape[1]
            actual_samples = samples_end - self.spec.columns.samples_start
            if actual_samples != self.spec.expected_samples:
                # 只发出警告，不抛出异常（允许不同长度的波形）
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    f"采样点数与预期不符: 期望 {self.spec.expected_samples}, "
                    f"实际 {actual_samples}"
                )

        return True
