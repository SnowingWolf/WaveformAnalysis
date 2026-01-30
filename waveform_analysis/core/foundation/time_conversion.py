"""时间转换模块：相对时间与绝对时间的双向转换

本模块提供全局时间戳（绝对时间索引）功能，允许用户使用 Python datetime 对象
进行数据查询，同时保持与现有相对时间系统的向后兼容。

核心组件：
-----------
1. EpochInfo: Epoch 元数据数据类
2. TimeConverter: 相对时间 ↔ 绝对时间双向转换器
3. EpochExtractor: 从多种来源自动提取 epoch

使用示例：
---------
>>> from datetime import datetime, timezone
>>> from waveform_analysis.core.foundation.time_conversion import (
...     EpochInfo, TimeConverter, EpochExtractor
... )
>>>
>>> # 从文件名提取 epoch
>>> extractor = EpochExtractor()
>>> epoch_dt = extractor.extract_from_filename("data_2024-01-01_12-00-00.csv")
>>>
>>> # 创建转换器
>>> epoch_info = EpochInfo.from_datetime(epoch_dt, source="filename")
>>> converter = TimeConverter(epoch_info)
>>>
>>> # 相对时间 → 绝对时间
>>> relative_ns = 1_000_000_000  # 1秒后
>>> absolute_dt = converter.relative_to_absolute(relative_ns)
>>>
>>> # 绝对时间 → 相对时间
>>> query_dt = datetime(2024, 1, 1, 12, 0, 10, tzinfo=timezone.utc)
>>> relative_ns = converter.absolute_to_relative(query_dt)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.utils.formats.base import TimestampUnit

export, __all__ = exporter()


@export
@dataclass
class EpochInfo:
    """Epoch 元数据

    存储运行的时间基准信息，用于相对时间和绝对时间之间的转换。

    Attributes:
        epoch_timestamp: Unix 时间戳（浮点数，秒）
        epoch_datetime: Python datetime 对象（带时区）
        epoch_source: Epoch 来源："filename", "csv_header", "first_event", "manual"
        time_unit: 相对时间的单位（默认 ns）
        timezone_name: 时区名称（如 "UTC", "Asia/Shanghai"）

    Example:
        >>> from datetime import datetime, timezone
        >>> epoch = EpochInfo.from_datetime(
        ...     datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        ...     source="filename"
        ... )
        >>> epoch.epoch_timestamp
        1704110400.0
    """

    epoch_timestamp: float  # Unix 时间戳（秒）
    epoch_datetime: datetime  # Python datetime（带时区）
    epoch_source: str  # 来源类型
    time_unit: TimestampUnit = TimestampUnit.NANOSECONDS  # 相对时间单位
    timezone_name: str = "UTC"  # 时区名称

    def __post_init__(self):
        """验证数据一致性"""
        # 确保 datetime 有时区信息
        if self.epoch_datetime.tzinfo is None:
            # 如果没有时区，假定为 UTC
            self.epoch_datetime = self.epoch_datetime.replace(tzinfo=timezone.utc)
            self.timezone_name = "UTC"

        # 验证 epoch_timestamp 与 epoch_datetime 一致
        expected_ts = self.epoch_datetime.timestamp()
        if abs(self.epoch_timestamp - expected_ts) > 1e-6:  # 容差 1 微秒
            # 以 datetime 为准，更新 timestamp
            self.epoch_timestamp = expected_ts

    @classmethod
    def from_datetime(
        cls,
        dt: datetime,
        source: str = "manual",
        time_unit: TimestampUnit = TimestampUnit.NANOSECONDS,
    ) -> "EpochInfo":
        """从 datetime 对象创建 EpochInfo

        Args:
            dt: Python datetime 对象
            source: Epoch 来源标识
            time_unit: 相对时间单位

        Returns:
            EpochInfo 实例
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return cls(
            epoch_timestamp=dt.timestamp(),
            epoch_datetime=dt,
            epoch_source=source,
            time_unit=time_unit,
            timezone_name=str(dt.tzinfo),
        )

    @classmethod
    def from_timestamp(
        cls,
        ts: float,
        source: str = "manual",
        time_unit: TimestampUnit = TimestampUnit.NANOSECONDS,
        tz: timezone = timezone.utc,
    ) -> "EpochInfo":
        """从 Unix 时间戳创建 EpochInfo

        Args:
            ts: Unix 时间戳（秒）
            source: Epoch 来源标识
            time_unit: 相对时间单位
            tz: 时区（默认 UTC）

        Returns:
            EpochInfo 实例
        """
        dt = datetime.fromtimestamp(ts, tz=tz)
        return cls(
            epoch_timestamp=ts,
            epoch_datetime=dt,
            epoch_source=source,
            time_unit=time_unit,
            timezone_name=str(tz),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 序列化）

        Returns:
            可序列化的字典
        """
        return {
            "epoch_timestamp": self.epoch_timestamp,
            "epoch_datetime": self.epoch_datetime.isoformat(),
            "epoch_source": self.epoch_source,
            "time_unit": self.time_unit.value,
            "timezone_name": self.timezone_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpochInfo":
        """从字典创建 EpochInfo（用于 JSON 反序列化）

        Args:
            data: 字典数据

        Returns:
            EpochInfo 实例
        """
        dt = datetime.fromisoformat(data["epoch_datetime"])
        time_unit = TimestampUnit(data.get("time_unit", "ns"))

        return cls(
            epoch_timestamp=data["epoch_timestamp"],
            epoch_datetime=dt,
            epoch_source=data["epoch_source"],
            time_unit=time_unit,
            timezone_name=data.get("timezone_name", "UTC"),
        )

    def __repr__(self) -> str:
        """可读的字符串表示"""
        return (
            f"EpochInfo(datetime={self.epoch_datetime.isoformat()}, "
            f"source={self.epoch_source}, unit={self.time_unit.value})"
        )


@export
class TimeConverter:
    """相对时间与绝对时间的双向转换器

    使用 NumPy 向量化操作实现高性能时间转换，支持批量处理大规模数据。

    Attributes:
        epoch_info: Epoch 元数据
        _scale_to_seconds: 相对时间单位到秒的转换因子

    Example:
        >>> from datetime import datetime, timezone
        >>> epoch = EpochInfo.from_datetime(
        ...     datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        ...     source="manual"
        ... )
        >>> converter = TimeConverter(epoch)
        >>>
        >>> # 相对时间 → 绝对时间
        >>> abs_time = converter.relative_to_absolute(1_000_000_000)  # 1秒
        >>> abs_time
        datetime.datetime(2024, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)
        >>>
        >>> # 绝对时间 → 相对时间
        >>> rel_time = converter.absolute_to_relative(abs_time)
        >>> rel_time
        1000000000
    """

    def __init__(self, epoch_info: EpochInfo):
        """初始化转换器

        Args:
            epoch_info: Epoch 元数据
        """
        self.epoch_info = epoch_info
        self._scale_to_seconds = self._get_time_unit_scale()

    def _get_time_unit_scale(self) -> float:
        """获取时间单位到秒的转换因子

        Returns:
            转换因子（相对时间单位 → 秒）
        """
        scales = {
            TimestampUnit.PICOSECONDS: 1e-12,
            TimestampUnit.NANOSECONDS: 1e-9,
            TimestampUnit.MICROSECONDS: 1e-6,
            TimestampUnit.MILLISECONDS: 1e-3,
            TimestampUnit.SECONDS: 1.0,
        }
        return scales.get(self.epoch_info.time_unit, 1e-9)

    def relative_to_absolute(
        self, relative_time: Union[int, np.ndarray]
    ) -> Union[datetime, np.ndarray]:
        """相对时间 → 绝对时间（datetime）

        支持标量和数组输入。对于数组输入，返回 datetime64[ns] 数组。

        Args:
            relative_time: 相对时间（整数或数组，单位由 epoch_info.time_unit 指定）

        Returns:
            - 标量输入: Python datetime 对象
            - 数组输入: NumPy datetime64[ns] 数组

        Example:
            >>> # 标量转换
            >>> dt = converter.relative_to_absolute(1_000_000_000)
            >>>
            >>> # 数组转换（向量化）
            >>> times = np.array([0, 1_000_000_000, 2_000_000_000])
            >>> dts = converter.relative_to_absolute(times)
        """
        if isinstance(relative_time, np.ndarray):
            # 向量化转换：相对时间 → Unix 时间戳（秒）→ datetime64
            relative_seconds = relative_time * self._scale_to_seconds
            absolute_timestamps = self.epoch_info.epoch_timestamp + relative_seconds

            # 转换为 datetime64[ns]
            # 注意：NumPy datetime64 基于 Unix epoch (1970-01-01)
            datetime64_ns = (absolute_timestamps * 1e9).astype("datetime64[ns]")
            return datetime64_ns

        else:
            # 标量转换
            relative_seconds = relative_time * self._scale_to_seconds
            absolute_timestamp = self.epoch_info.epoch_timestamp + relative_seconds

            return datetime.fromtimestamp(
                absolute_timestamp, tz=self.epoch_info.epoch_datetime.tzinfo
            )

    def absolute_to_relative(
        self, absolute_time: Union[datetime, np.ndarray]
    ) -> Union[int, np.ndarray]:
        """绝对时间（datetime）→ 相对时间

        支持 Python datetime 对象和 NumPy datetime64 数组。

        Args:
            absolute_time: 绝对时间（datetime 对象或 datetime64 数组）

        Returns:
            - datetime 输入: 整数相对时间
            - datetime64 数组输入: 整数数组

        Example:
            >>> # 标量转换
            >>> dt = datetime(2024, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
            >>> rel_time = converter.absolute_to_relative(dt)
            >>>
            >>> # 数组转换
            >>> dts = np.array(['2024-01-01T00:00:01', '2024-01-01T00:00:02'],
            ...                 dtype='datetime64[ns]')
            >>> rel_times = converter.absolute_to_relative(dts)
        """
        if isinstance(absolute_time, np.ndarray):
            # NumPy datetime64 数组
            # datetime64[ns] → Unix 时间戳（秒）
            absolute_timestamps = absolute_time.astype("datetime64[s]").astype(float)
            relative_seconds = absolute_timestamps - self.epoch_info.epoch_timestamp

            # 秒 → 相对时间单位
            relative_time = relative_seconds / self._scale_to_seconds
            return relative_time.astype(np.int64)

        else:
            # Python datetime 对象
            if absolute_time.tzinfo is None:
                # 如果没有时区，假定为 epoch 的时区
                absolute_time = absolute_time.replace(tzinfo=self.epoch_info.epoch_datetime.tzinfo)

            absolute_timestamp = absolute_time.timestamp()
            relative_seconds = absolute_timestamp - self.epoch_info.epoch_timestamp

            # 秒 → 相对时间单位
            relative_time = relative_seconds / self._scale_to_seconds
            return int(relative_time)

    def convert_time_range(
        self, start_dt: Optional[datetime], end_dt: Optional[datetime]
    ) -> Tuple[Optional[int], Optional[int]]:
        """转换时间范围（datetime → 相对时间）

        便捷方法，用于查询接口。

        Args:
            start_dt: 起始时间（datetime，可为 None）
            end_dt: 结束时间（datetime，可为 None）

        Returns:
            (start_relative, end_relative) 元组

        Example:
            >>> start = datetime(2024, 1, 1, 0, 0, 10, tzinfo=timezone.utc)
            >>> end = datetime(2024, 1, 1, 0, 0, 20, tzinfo=timezone.utc)
            >>> start_rel, end_rel = converter.convert_time_range(start, end)
        """
        start_rel = int(self.absolute_to_relative(start_dt)) if start_dt else None
        end_rel = int(self.absolute_to_relative(end_dt)) if end_dt else None
        return start_rel, end_rel


@export
class EpochExtractor:
    """Epoch 提取器：从多种来源自动提取时间基准

    支持的提取策略：
    1. 文件名解析（多种常见格式）
    2. CSV 头部元数据
    3. 首个事件时间戳
    4. 手动配置

    Attributes:
        filename_patterns: 文件名正则表达式模式列表
        csv_metadata_keys: CSV 元数据字段名列表

    Example:
        >>> extractor = EpochExtractor()
        >>>
        >>> # 从文件名提取
        >>> epoch_dt = extractor.extract_from_filename("data_2024-01-01_12-00-00.csv")
        >>>
        >>> # 从 CSV 头部提取
        >>> epoch_dt = extractor.extract_from_csv_header("data.csv")
        >>>
        >>> # 自动检测最佳来源
        >>> epoch_info = extractor.auto_extract(["file1.csv", "file2.csv"])
    """

    # 默认文件名模式（优先级从高到低）
    DEFAULT_FILENAME_PATTERNS = [
        # ISO 8601 格式：2024-01-01_12-00-00 或 2024-01-01T12:00:00
        (
            r"(\d{4})-(\d{2})-(\d{2})[_T](\d{2})[:-](\d{2})[:-](\d{2})",
            "%Y-%m-%d %H:%M:%S",
        ),
        # 紧凑格式：20240101120000
        (r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", "%Y%m%d%H%M%S"),
        # 下划线分隔：2024_01_01_120000
        (
            r"(\d{4})_(\d{2})_(\d{2})_(\d{2})(\d{2})(\d{2})",
            "%Y_%m_%d_%H%M%S",
        ),
        # 仅日期：2024-01-01 (默认 00:00:00)
        (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),
        # 仅日期（紧凑）：20240101
        (r"(\d{4})(\d{2})(\d{2})", "%Y%m%d"),
    ]

    # CSV 元数据字段名（检查头部注释行）
    DEFAULT_CSV_METADATA_KEYS = [
        "epoch",
        "start_time",
        "acquisition_start",
        "timestamp",
        "datetime",
    ]

    def __init__(
        self,
        filename_patterns: Optional[List[tuple]] = None,
        csv_metadata_keys: Optional[List[str]] = None,
    ):
        """初始化提取器

        Args:
            filename_patterns: 自定义文件名模式列表 [(regex, format_str), ...]
            csv_metadata_keys: 自定义 CSV 元数据字段名列表
        """
        self.filename_patterns = filename_patterns or self.DEFAULT_FILENAME_PATTERNS
        self.csv_metadata_keys = csv_metadata_keys or self.DEFAULT_CSV_METADATA_KEYS

    def extract_from_filename(
        self, filepath: Union[str, Path], tz: timezone = timezone.utc
    ) -> Optional[datetime]:
        """从文件名解析 epoch

        尝试匹配所有注册的文件名模式，返回第一个成功的匹配。

        Args:
            filepath: 文件路径或文件名
            tz: 时区（默认 UTC）

        Returns:
            解析成功返回 datetime，否则返回 None

        Example:
            >>> extractor = EpochExtractor()
            >>>
            >>> # 示例1: ISO 8601 格式
            >>> dt = extractor.extract_from_filename("data_2024-01-01_12-00-00.csv")
            >>>
            >>> # 示例2: 紧凑格式
            >>> dt = extractor.extract_from_filename("run_20240101120000_CH0.csv")
            >>>
            >>> # 示例3: 不匹配
            >>> dt = extractor.extract_from_filename("unknown_format.csv")
            >>> dt is None
            True
        """
        filename = Path(filepath).name

        for pattern, _format_str in self.filename_patterns:
            match = re.search(pattern, filename)
            if match:
                try:
                    # 提取匹配的数字组
                    groups = match.groups()

                    # 构造时间字符串（统一使用 ISO 格式）
                    if len(groups) == 6:
                        # 完整日期时间
                        time_str = f"{groups[0]}-{groups[1]}-{groups[2]} {groups[3]}:{groups[4]}:{groups[5]}"
                        parse_format = "%Y-%m-%d %H:%M:%S"
                    elif len(groups) == 3:
                        # 仅日期
                        time_str = f"{groups[0]}-{groups[1]}-{groups[2]}"
                        parse_format = "%Y-%m-%d"
                    else:
                        continue

                    # 解析 datetime（使用统一格式）
                    dt = datetime.strptime(time_str, parse_format)
                    return dt.replace(tzinfo=tz)

                except (ValueError, IndexError):
                    continue

        return None

    def extract_from_csv_header(
        self, filepath: Union[str, Path], max_header_lines: int = 20, tz: timezone = timezone.utc
    ) -> Optional[datetime]:
        """从 CSV 头部注释提取 epoch

        检查文件前几行的注释，查找包含时间戳的元数据字段。

        Args:
            filepath: CSV 文件路径
            max_header_lines: 最多检查的行数
            tz: 时区（默认 UTC）

        Returns:
            解析成功返回 datetime，否则返回 None

        Example:
            >>> # CSV 文件头部示例:
            >>> # # Epoch: 2024-01-01T12:00:00Z
            >>> # # Start Time: 1704110400
            >>> # BOARD;CHANNEL;TIMETAG;...
            >>>
            >>> dt = extractor.extract_from_csv_header("data.csv")
        """
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    if i >= max_header_lines:
                        break

                    # 跳过非注释行
                    line = line.strip()
                    if not line.startswith("#"):
                        continue

                    # 移除注释符号
                    line = line.lstrip("#").strip()

                    # 检查是否包含元数据字段
                    for key in self.csv_metadata_keys:
                        if key.lower() in line.lower():
                            # 尝试提取时间值
                            parts = line.split(":", 1)
                            if len(parts) == 2:
                                value = parts[1].strip()

                                # 尝试解析为 Unix 时间戳
                                try:
                                    ts = float(value)
                                    return datetime.fromtimestamp(ts, tz=tz)
                                except ValueError:
                                    pass

                                # 尝试解析为 ISO 8601
                                try:
                                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                                    return dt.astimezone(tz)
                                except ValueError:
                                    pass

        except OSError:
            pass

        return None

    def extract_from_first_event(
        self,
        filepath: Union[str, Path],
        timestamp_column: int = 2,
        header_rows: int = 2,
        delimiter: str = ";",
        time_unit: TimestampUnit = TimestampUnit.PICOSECONDS,
        tz: timezone = timezone.utc,
    ) -> Optional[datetime]:
        """从首个事件的时间戳推导 epoch

        假设相对时间戳从 0 开始，使用首个事件的时间戳作为偏移量。
        注意：这种方法假定首个事件时间戳接近 0，可能不准确。

        Args:
            filepath: CSV 文件路径
            timestamp_column: 时间戳列索引（默认 2，对应 TIMETAG）
            header_rows: 跳过的头部行数
            delimiter: CSV 分隔符
            time_unit: 时间戳单位
            tz: 时区

        Returns:
            推导的 epoch datetime，或 None

        Example:
            >>> # 如果首个事件时间戳为 0（或接近 0），
            >>> # 则 epoch 为文件修改时间减去相对时间
            >>> dt = extractor.extract_from_first_event("data.csv")
        """
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                # 跳过头部
                for _ in range(header_rows):
                    next(f, None)

                # 读取首行数据
                first_line = f.readline().strip()
                if not first_line:
                    return None

                parts = first_line.split(delimiter)
                if len(parts) <= timestamp_column:
                    return None

                # 提取时间戳
                first_timestamp = int(parts[timestamp_column])

                # 获取文件修改时间作为参考
                file_mtime = Path(filepath).stat().st_mtime
                file_dt = datetime.fromtimestamp(file_mtime, tz=tz)

                # 计算 epoch（文件时间 - 首个事件的相对时间）
                time_scales = {
                    TimestampUnit.PICOSECONDS: 1e-12,
                    TimestampUnit.NANOSECONDS: 1e-9,
                    TimestampUnit.MICROSECONDS: 1e-6,
                    TimestampUnit.MILLISECONDS: 1e-3,
                    TimestampUnit.SECONDS: 1.0,
                }
                scale = time_scales.get(time_unit, 1e-9)
                offset_seconds = first_timestamp * scale

                epoch_dt = file_dt - timedelta(seconds=offset_seconds)
                return epoch_dt

        except (OSError, ValueError, IndexError):
            return None

    def auto_extract(
        self,
        file_paths: List[Union[str, Path]],
        strategy: str = "auto",
        time_unit: TimestampUnit = TimestampUnit.PICOSECONDS,
        tz: timezone = timezone.utc,
    ) -> EpochInfo:
        """自动检测并提取 epoch

        按优先级尝试多种提取策略，返回第一个成功的结果。

        优先级顺序：
        1. filename（最可靠）
        2. csv_header（较可靠）
        3. first_event（不太可靠，作为 fallback）

        Args:
            file_paths: 数据文件路径列表
            strategy: 提取策略（"auto", "filename", "csv_header", "first_event"）
            time_unit: 相对时间单位
            tz: 时区

        Returns:
            EpochInfo 实例

        Raises:
            ValueError: 如果所有策略都失败

        Example:
            >>> files = ["data_2024-01-01_12-00-00_CH0.csv",
            ...          "data_2024-01-01_12-00-00_CH1.csv"]
            >>> epoch_info = extractor.auto_extract(files)
            >>> epoch_info.epoch_source
            'filename'
        """
        if not file_paths:
            raise ValueError("文件路径列表不能为空")

        # 优先使用第一个文件
        primary_file = file_paths[0]

        strategies = []
        if strategy == "auto":
            strategies = ["filename", "csv_header", "first_event"]
        else:
            strategies = [strategy]

        for strat in strategies:
            epoch_dt = None

            if strat == "filename":
                # 尝试所有文件，找到第一个匹配的
                for fpath in file_paths:
                    epoch_dt = self.extract_from_filename(fpath, tz=tz)
                    if epoch_dt:
                        break

            elif strat == "csv_header":
                epoch_dt = self.extract_from_csv_header(primary_file, tz=tz)

            elif strat == "first_event":
                epoch_dt = self.extract_from_first_event(primary_file, time_unit=time_unit, tz=tz)

            if epoch_dt:
                return EpochInfo.from_datetime(epoch_dt, source=strat, time_unit=time_unit)

        # 所有策略都失败
        raise ValueError(
            f"无法从文件中提取 epoch。尝试的策略: {strategies}。"
            f"请手动设置 epoch 或确保文件名包含时间戳信息。"
        )
