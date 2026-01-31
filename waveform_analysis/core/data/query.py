"""
时间范围查询优化模块

提供高效的时间范围查询和索引功能:
- 时间索引构建和管理
- 快速时间范围查询
- 多种索引策略(二分查找、区间树等)
- 查询性能优化
"""

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

if TYPE_CHECKING:
    from waveform_analysis.core.foundation.time_conversion import EpochInfo, TimeConverter

logger = logging.getLogger(__name__)
export, __all__ = exporter()


# ===========================
# 时间索引数据结构
# ===========================


@export
@dataclass
class TimeIndex:
    """
    时间索引,支持快速时间范围查询

    使用二分查找实现O(log n)的查询复杂度

    Attributes:
        times: 时间戳数组(已排序)
        indices: 对应的原始索引
        endtimes: 结束时间(如果有)
        epoch_info: Epoch 元数据(用于绝对时间查询)
    """

    times: np.ndarray  # 时间戳数组(已排序)
    indices: np.ndarray  # 对应的原始索引
    endtimes: Optional[np.ndarray] = None  # 结束时间(如果有)

    # Epoch 元数据(用于绝对时间查询)
    epoch_info: Optional["EpochInfo"] = None

    # 元数据
    min_time: int = 0
    max_time: int = 0
    n_records: int = 0

    # 索引构建时间
    build_time: float = 0.0

    # 缓存的 TimeConverter
    _converter: Optional["TimeConverter"] = None

    def __post_init__(self):
        """初始化后处理"""
        if len(self.times) > 0:
            self.min_time = int(self.times[0])
            self.max_time = int(self.times[-1])
            if self.endtimes is not None:
                self.max_time = max(self.max_time, int(self.endtimes.max()))
            self.n_records = len(self.times)

    def query_range(self, start_time: int, end_time: int) -> np.ndarray:
        """
        查询时间范围内的记录索引

        Args:
            start_time: 起始时间(包含)
            end_time: 结束时间(不包含)

        Returns:
            符合条件的原始索引数组
        """
        if self.n_records == 0:
            return np.array([], dtype=np.int64)

        # 快速边界检查
        if end_time <= self.min_time or start_time >= self.max_time:
            return np.array([], dtype=np.int64)

        # 使用二分查找定位起始和结束位置
        # searchsorted找到第一个 >= start_time的位置
        left_idx = np.searchsorted(self.times, start_time, side="left")
        # searchsorted找到第一个 >= end_time的位置
        right_idx = np.searchsorted(self.times, end_time, side="left")

        if left_idx >= right_idx:
            return np.array([], dtype=np.int64)

        # 如果有endtime,需要额外检查记录是否真正在范围内
        if self.endtimes is not None:
            # 记录的endtime必须 > start_time,且time必须 < end_time
            mask = self.endtimes[left_idx:right_idx] > start_time
            selected_indices = self.indices[left_idx:right_idx][mask]
        else:
            selected_indices = self.indices[left_idx:right_idx]

        return selected_indices

    def query_point(self, time: int) -> Optional[int]:
        """
        查询包含特定时间点的记录

        Args:
            time: 时间点

        Returns:
            记录索引,如果没有则返回None
        """
        if self.n_records == 0 or time < self.min_time or time > self.max_time:
            return None

        # 找到第一个 > time的位置,然后退一步
        idx = np.searchsorted(self.times, time, side="right") - 1

        if idx < 0 or idx >= self.n_records:
            return None

        # 如果有endtime,检查time是否在[time, endtime)内
        if self.endtimes is not None:
            if time >= self.times[idx] and time < self.endtimes[idx]:
                return self.indices[idx]
            return None
        else:
            # 只检查time是否匹配
            if self.times[idx] == time:
                return self.indices[idx]
            return None

    def overlaps_range(self, start_time: int, end_time: int) -> bool:
        """
        检查是否有记录与时间范围重叠

        Args:
            start_time: 起始时间
            end_time: 结束时间

        Returns:
            是否有重叠
        """
        if self.n_records == 0:
            return False

        # 快速边界检查
        if end_time <= self.min_time or start_time >= self.max_time:
            return False

        return len(self.query_range(start_time, end_time)) > 0

    def _get_converter(self) -> Optional["TimeConverter"]:
        """获取或创建 TimeConverter 实例"""
        if self._converter is not None:
            return self._converter

        if self.epoch_info is None:
            return None

        from waveform_analysis.core.foundation.time_conversion import TimeConverter

        self._converter = TimeConverter(self.epoch_info)
        return self._converter

    def query_range_absolute(
        self, start_dt: Optional[datetime] = None, end_dt: Optional[datetime] = None
    ) -> np.ndarray:
        """
        使用 datetime 对象查询时间范围内的记录索引

        Args:
            start_dt: 起始时间(datetime, 包含)
            end_dt: 结束时间(datetime, 不包含)

        Returns:
            符合条件的原始索引数组

        Raises:
            ValueError: 如果没有设置 epoch_info

        Example:
            >>> from datetime import datetime, timezone
            >>> start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            >>> end = datetime(2024, 1, 1, 12, 0, 10, tzinfo=timezone.utc)
            >>> indices = index.query_range_absolute(start, end)
        """
        converter = self._get_converter()
        if converter is None:
            raise ValueError(
                "无法使用绝对时间查询：未设置 epoch_info。"
                "请先调用 ctx.set_epoch() 或 ctx.auto_extract_epoch()。"
            )

        start_rel, end_rel = converter.convert_time_range(start_dt, end_dt)

        # 如果没有指定边界，使用索引的边界
        if start_rel is None:
            start_rel = self.min_time
        if end_rel is None:
            end_rel = self.max_time + 1  # +1 因为 end 不包含

        return self.query_range(start_rel, end_rel)

    def query_point_absolute(self, dt: datetime) -> Optional[int]:
        """
        使用 datetime 对象查询包含特定时间点的记录

        Args:
            dt: 时间点(datetime)

        Returns:
            记录索引,如果没有则返回None

        Raises:
            ValueError: 如果没有设置 epoch_info
        """
        converter = self._get_converter()
        if converter is None:
            raise ValueError(
                "无法使用绝对时间查询：未设置 epoch_info。"
                "请先调用 ctx.set_epoch() 或 ctx.auto_extract_epoch()。"
            )

        time_rel = converter.absolute_to_relative(dt)
        return self.query_point(int(time_rel))

    def get_time_range_absolute(self) -> Optional[Tuple[datetime, datetime]]:
        """
        获取索引覆盖的绝对时间范围

        Returns:
            (min_datetime, max_datetime) 元组，或 None 如果没有 epoch_info
        """
        converter = self._get_converter()
        if converter is None:
            return None

        min_dt = converter.relative_to_absolute(self.min_time)
        max_dt = converter.relative_to_absolute(self.max_time)
        return (min_dt, max_dt)


@export
class TimeRangeQueryEngine:
    """
    时间范围查询引擎

    管理多个数据类型的时间索引,提供统一的查询接口
    """

    def __init__(self):
        """初始化查询引擎"""
        self._indices: Dict[Tuple[str, str], TimeIndex] = {}  # (run_id, data_name) -> TimeIndex
        self.logger = logging.getLogger(self.__class__.__name__)

    def build_index(
        self,
        run_id: str,
        data_name: str,
        data: np.ndarray,
        time_field: str = "time",
        endtime_field: Optional[str] = None,
        force_rebuild: bool = False,
        epoch_info: Optional["EpochInfo"] = None,
    ) -> TimeIndex:
        """
        为数据构建时间索引

        Args:
            run_id: 运行ID
            data_name: 数据名称
            data: 数据数组(结构化数组)
            time_field: 时间字段名
            endtime_field: 结束时间字段名(可选)
            force_rebuild: 强制重建索引
            epoch_info: Epoch 元数据(用于绝对时间查询)

        Returns:
            构建的时间索引
        """
        import time

        key = (run_id, data_name)

        # 检查是否已存在
        if key in self._indices and not force_rebuild:
            self.logger.debug(f"Time index for {key} already exists")
            return self._indices[key]

        start_time = time.time()

        # 提取时间字段
        if time_field not in data.dtype.names:
            raise ValueError(f"Field '{time_field}' not found in data dtype")

        times = data[time_field].copy()

        # 检查是否已排序
        if not np.all(times[:-1] <= times[1:]):
            # 需要排序
            sort_indices = np.argsort(times)
            times = times[sort_indices]
            indices = sort_indices
            self.logger.warning(f"Data for {key} is not sorted by time, sorting...")
        else:
            indices = np.arange(len(times), dtype=np.int64)

        # 提取结束时间(如果有)
        endtimes = None
        if endtime_field is not None:
            if endtime_field in data.dtype.names:
                endtimes = (
                    data[endtime_field][indices] if indices is not None else data[endtime_field]
                )
            elif endtime_field == "computed":
                # 计算endtime: time + dt * length
                if "dt" in data.dtype.names and "length" in data.dtype.names:
                    endtimes = times + data["dt"][indices] * data["length"][indices]
                else:
                    self.logger.warning(
                        f"Cannot compute endtime for {key}, dt or length field missing"
                    )

        # 创建索引
        index = TimeIndex(
            times=times,
            indices=indices,
            endtimes=endtimes,
            epoch_info=epoch_info,
            build_time=time.time() - start_time,
        )

        # 保存索引
        self._indices[key] = index

        self.logger.info(
            f"Built time index for {key}: {index.n_records} records, "
            f"time range [{index.min_time}, {index.max_time}], "
            f"build time: {index.build_time:.3f}s"
        )

        return index

    def query(
        self,
        run_id: str,
        data_name: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_point: Optional[int] = None,
    ) -> Optional[np.ndarray]:
        """
        查询时间范围

        Args:
            run_id: 运行ID
            data_name: 数据名称
            start_time: 起始时间(包含)
            end_time: 结束时间(不包含)
            time_point: 特定时间点(与start_time/end_time互斥)

        Returns:
            符合条件的记录索引,如果索引不存在返回None
        """
        key = (run_id, data_name)

        if key not in self._indices:
            self.logger.warning(f"No time index for {key}")
            return None

        index = self._indices[key]

        if time_point is not None:
            # 点查询
            idx = index.query_point(time_point)
            return (
                np.array([idx], dtype=np.int64) if idx is not None else np.array([], dtype=np.int64)
            )
        else:
            # 范围查询
            if start_time is None:
                start_time = index.min_time
            if end_time is None:
                end_time = index.max_time + 1

            return index.query_range(start_time, end_time)

    def has_index(self, run_id: str, data_name: str) -> bool:
        """检查是否存在索引"""
        return (run_id, data_name) in self._indices

    def get_index(self, run_id: str, data_name: str) -> Optional[TimeIndex]:
        """获取时间索引"""
        return self._indices.get((run_id, data_name))

    def clear_index(self, run_id: Optional[str] = None, data_name: Optional[str] = None):
        """
        清除索引

        Args:
            run_id: 运行ID,None则清除所有
            data_name: 数据名称,None则清除指定run_id的所有索引
        """
        if run_id is None:
            # 清除所有
            self._indices.clear()
            self.logger.info("Cleared all time indices")
        elif data_name is None:
            # 清除指定run_id的所有索引
            keys_to_remove = [k for k in self._indices.keys() if k[0] == run_id]
            for key in keys_to_remove:
                del self._indices[key]
            self.logger.info(f"Cleared {len(keys_to_remove)} indices for run_id '{run_id}'")
        else:
            # 清除特定索引
            key = (run_id, data_name)
            if key in self._indices:
                del self._indices[key]
                self.logger.info(f"Cleared index for {key}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_indices": len(self._indices),
            "indices": {
                f"{k[0]}.{k[1]}": {
                    "n_records": idx.n_records,
                    "time_range": (idx.min_time, idx.max_time),
                    "build_time": idx.build_time,
                    "has_endtime": idx.endtimes is not None,
                }
                for k, idx in self._indices.items()
            },
        }


# ===========================
# Context集成辅助函数
# ===========================


@export
def query_data_time_range(
    context: Any,
    run_id: str,
    data_name: str,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    time_field: str = "time",
    endtime_field: Optional[str] = None,
    auto_build_index: bool = True,
) -> np.ndarray:
    """
    查询数据的时间范围

    这是一个便捷函数,用于在Context中查询数据的时间范围

    Args:
        context: Context对象
        run_id: 运行ID
        data_name: 数据名称
        start_time: 起始时间
        end_time: 结束时间
        time_field: 时间字段名
        endtime_field: 结束时间字段名
        auto_build_index: 自动构建索引

    Returns:
        符合条件的数据子集
    """
    # 获取查询引擎
    if not hasattr(context, "_time_query_engine"):
        context._time_query_engine = TimeRangeQueryEngine()

    engine = context._time_query_engine

    # 获取完整数据
    data = context.get_data(run_id, data_name)

    if data is None or len(data) == 0:
        return np.array([], dtype=data.dtype if data is not None else np.float64)

    # 如果没有时间字段,返回完整数据
    if time_field not in data.dtype.names:
        logger.warning(f"Time field '{time_field}' not found in {data_name}, returning full data")
        return data

    # 构建索引(如果需要)
    if auto_build_index and not engine.has_index(run_id, data_name):
        engine.build_index(run_id, data_name, data, time_field, endtime_field)

    # 查询
    if engine.has_index(run_id, data_name):
        indices = engine.query(run_id, data_name, start_time, end_time)
        if indices is not None and len(indices) > 0:
            return data[indices]
        else:
            return np.array([], dtype=data.dtype)
    else:
        # 回退到直接过滤
        logger.warning(f"No index for {data_name}, using direct filtering")
        times = data[time_field]

        if start_time is None:
            start_time = times.min()
        if end_time is None:
            end_time = times.max() + 1

        mask = (times >= start_time) & (times < end_time)
        return data[mask]


# ===========================
# 性能优化工具
# ===========================


@export
class TimeRangeCache:
    """
    时间范围查询结果缓存

    缓存最近的查询结果,避免重复查询
    """

    def __init__(self, max_size: int = 100):
        """
        初始化缓存

        Args:
            max_size: 最大缓存条目数
        """
        self.max_size = max_size
        self._cache: Dict[Tuple, Any] = {}
        self._access_order: List[Tuple] = []

    def get(
        self, run_id: str, data_name: str, start_time: Optional[int], end_time: Optional[int]
    ) -> Optional[np.ndarray]:
        """获取缓存结果"""
        key = (run_id, data_name, start_time, end_time)

        if key in self._cache:
            # 更新访问顺序
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]

        return None

    def put(
        self,
        run_id: str,
        data_name: str,
        start_time: Optional[int],
        end_time: Optional[int],
        result: np.ndarray,
    ):
        """存储查询结果"""
        key = (run_id, data_name, start_time, end_time)

        # 如果缓存已满,移除最旧的条目
        if len(self._cache) >= self.max_size and key not in self._cache:
            oldest_key = self._access_order.pop(0)
            del self._cache[oldest_key]

        self._cache[key] = result

        if key not in self._access_order:
            self._access_order.append(key)

    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._access_order.clear()
