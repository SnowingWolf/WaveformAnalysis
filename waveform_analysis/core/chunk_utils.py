"""
Chunk Utilities - 时间区间与分块操作

这是所有下游 plugin 正确性的基础，提供：
- endtime 计算与校验（由 time、dt、length 推导）
- 依时间切 chunk、裁剪到 time range、处理 chunk 边界
- 检查单调性、重叠、跨界违规
- 重分块（rechunk）让数据符合处理规范

受 strax 启发的时间分块处理逻辑。
"""

from dataclasses import dataclass, field
from typing import Any, Generator, Iterator, List, Optional, Tuple, Union

import numpy as np

from .utils import exporter

# 初始化 exporter
export, __all__ = exporter()

# =============================================================================
# 常量与类型定义
# =============================================================================

# 时间字段名称常量
TIME_FIELD = "time"
DT_FIELD = "dt"
LENGTH_FIELD = "length"
ENDTIME_FIELD = "endtime"
CHANNEL_FIELD = "channel"

__all__.extend(["TIME_FIELD", "DT_FIELD", "LENGTH_FIELD", "ENDTIME_FIELD", "CHANNEL_FIELD"])

# Chunk 处理默认参数
DEFAULT_CHUNK_SIZE = 50000  # 默认 chunk 大小
DEFAULT_BREAK_THRESHOLD_NS = 1_000_000_000  # 1秒间隔认为是 break

__all__.extend(["DEFAULT_CHUNK_SIZE", "DEFAULT_BREAK_THRESHOLD_NS"])


@export
class Chunk:
    """
    类似于 strax.Chunk 的数据块对象，封装了数据及其时间范围。
    """

    def __init__(
        self,
        data: np.ndarray,
        start: int,
        end: int,
        run_id: str = "unknown",
        data_type: str = "raw",
        data_kind: str = "waveforms",
    ):
        self.data = data
        self.start = int(start)
        self.end = int(end)
        self.run_id = run_id
        self.data_type = data_type
        self.data_kind = data_kind
        self.dtype = data.dtype

        # 基础校验
        if len(data) > 0:
            data_start = data[0][TIME_FIELD]
            if data_start < self.start:
                raise ValueError(f"Chunk data starts at {data_start}, before chunk start {self.start}")

            # 使用 get_endtime 获取最后一条记录的结束时间
            # 注意：这里假设 get_endtime 已经定义或在下面定义
            data_end = get_endtime(data).max()
            if data_end > self.end:
                raise ValueError(f"Chunk data ends at {data_end}, after chunk end {self.end}")

    def __len__(self):
        return len(self.data)

    @property
    def duration(self):
        return self.end - self.start

    @property
    def nbytes(self):
        return self.data.nbytes

    def __repr__(self):
        return f"Chunk({self.run_id}.{self.data_type}: {self.start} - {self.end}, {len(self)} items)"

    def split(self, t: int):
        """在时间 t 处切割 Chunk"""
        t = max(min(t, self.end), self.start)
        mask = self.data[TIME_FIELD] < t

        return (
            Chunk(self.data[mask], self.start, t, self.run_id, self.data_type, self.data_kind),
            Chunk(self.data[~mask], t, self.end, self.run_id, self.data_type, self.data_kind),
        )


@export
@dataclass
class ChunkInfo:
    """Chunk 元数据信息"""

    start_time: int  # chunk 起始时间 (ns)
    end_time: int  # chunk 结束时间 (ns)
    n_records: int  # 记录数
    chunk_i: int = 0  # chunk 索引
    run_id: str = ""  # run 标识

    @property
    def duration(self) -> int:
        """chunk 持续时间 (ns)"""
        return self.end_time - self.start_time

    def overlaps(self, other: "ChunkInfo") -> bool:
        """检查与另一个 chunk 是否有时间重叠"""
        return self.start_time < other.end_time and other.start_time < self.end_time

    def contains(self, time: int) -> bool:
        """检查时间点是否在此 chunk 内"""
        return self.start_time <= time < self.end_time

    def __repr__(self) -> str:
        return (
            f"ChunkInfo(start={self.start_time}, end={self.end_time}, n={self.n_records}, duration={self.duration}ns)"
        )


@export
@dataclass
class ValidationResult:
    """数据校验结果"""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.is_valid

    def raise_if_invalid(self, prefix: str = ""):
        """如果无效则抛出异常"""
        if not self.is_valid:
            msg = "; ".join(self.errors)
            raise ValueError(f"{prefix}{msg}" if prefix else msg)


# =============================================================================
# Endtime 计算与校验
# =============================================================================


@export
def compute_endtime(data: np.ndarray) -> np.ndarray:
    """
    计算 endtime = time + dt * length

    Args:
        data: 包含 time, dt, length 字段的结构化数组

    Returns:
        endtime 数组 (int64)

    Raises:
        KeyError: 缺少必要字段
    """
    _validate_time_fields(data, require_length=True)

    time = data[TIME_FIELD]
    dt = data[DT_FIELD]
    length = data[LENGTH_FIELD]

    # 使用 int64 防止溢出
    return time.astype(np.int64) + dt.astype(np.int64) * length.astype(np.int64)


@export
def add_endtime_field(data: np.ndarray, inplace: bool = False) -> np.ndarray:
    """
    为结构化数组添加 endtime 字段

    Args:
        data: 包含 time, dt, length 字段的结构化数组
        inplace: 是否原地修改（需要 data 已有 endtime 字段）

    Returns:
        包含 endtime 字段的结构化数组
    """
    endtime = compute_endtime(data)

    if inplace:
        if ENDTIME_FIELD not in data.dtype.names:
            raise ValueError(f"Cannot modify inplace: '{ENDTIME_FIELD}' field not in dtype")
        data[ENDTIME_FIELD] = endtime
        return data

    # 创建新数组，添加 endtime 字段
    if ENDTIME_FIELD in data.dtype.names:
        # 已有字段，直接复制并更新
        result = data.copy()
        result[ENDTIME_FIELD] = endtime
        return result

    # 需要添加新字段
    new_dtype = np.dtype(data.dtype.descr + [(ENDTIME_FIELD, "<i8")])
    result = np.zeros(len(data), dtype=new_dtype)

    # 复制原有字段
    for name in data.dtype.names:
        result[name] = data[name]
    result[ENDTIME_FIELD] = endtime

    return result


@export
def validate_endtime(data: np.ndarray, tolerance_ns: int = 0) -> ValidationResult:
    """
    校验 endtime 是否与 time + dt * length 一致

    Args:
        data: 包含 time, dt, length, endtime 字段的结构化数组
        tolerance_ns: 允许的误差 (纳秒)

    Returns:
        ValidationResult
    """
    result = ValidationResult(is_valid=True)

    if ENDTIME_FIELD not in data.dtype.names:
        result.is_valid = False
        result.errors.append(f"Missing '{ENDTIME_FIELD}' field")
        return result

    expected = compute_endtime(data)
    actual = data[ENDTIME_FIELD]
    diff = np.abs(actual.astype(np.int64) - expected.astype(np.int64))

    n_mismatch = np.sum(diff > tolerance_ns)
    if n_mismatch > 0:
        result.is_valid = False
        max_diff = np.max(diff)
        result.errors.append(f"Endtime mismatch: {n_mismatch}/{len(data)} records differ by up to {max_diff}ns")

    result.stats = {
        "n_records": len(data),
        "n_mismatch": int(n_mismatch),
        "max_diff_ns": int(np.max(diff)) if len(diff) > 0 else 0,
    }

    return result


@export
def get_endtime(data: np.ndarray) -> np.ndarray:
    """
    获取 endtime，如果没有 endtime 字段则计算

    Args:
        data: 结构化数组

    Returns:
        endtime 数组
    """
    if ENDTIME_FIELD in data.dtype.names:
        return data[ENDTIME_FIELD]
    return compute_endtime(data)


# =============================================================================
# 单调性与重叠检查
# =============================================================================


@export
def check_monotonic(data: np.ndarray, field: str = TIME_FIELD, strict: bool = False) -> ValidationResult:
    """
    检查字段是否单调递增

    Args:
        data: 结构化数组
        field: 要检查的字段名
        strict: True 表示严格递增（不允许相等），False 表示非递减

    Returns:
        ValidationResult
    """
    result = ValidationResult(is_valid=True)

    if len(data) <= 1:
        result.stats = {"n_records": len(data), "is_sorted": True}
        return result

    if field not in data.dtype.names:
        result.is_valid = False
        result.errors.append(f"Field '{field}' not found in data")
        return result

    values = data[field]
    diff = np.diff(values.astype(np.int64))

    if strict:
        violations = np.sum(diff <= 0)
        violation_type = "non-strictly-increasing"
    else:
        violations = np.sum(diff < 0)
        violation_type = "decreasing"

    if violations > 0:
        result.is_valid = False
        # 找到第一个违规位置
        if strict:
            first_violation = np.argmax(diff <= 0)
        else:
            first_violation = np.argmax(diff < 0)
        result.errors.append(
            f"Field '{field}' is {violation_type}: {violations} violations found, "
            f"first at index {first_violation} (value {values[first_violation]} -> {values[first_violation + 1]})"
        )

    result.stats = {
        "n_records": len(data),
        "n_violations": int(violations),
        "is_sorted": violations == 0,
        "min_diff": int(np.min(diff)) if len(diff) > 0 else 0,
        "max_diff": int(np.max(diff)) if len(diff) > 0 else 0,
    }

    return result


@export
def check_no_overlap(data: np.ndarray) -> ValidationResult:
    """
    检查记录之间是否有时间重叠（endtime[i] <= time[i+1]）

    Args:
        data: 包含 time 和 endtime（或 time, dt, length）的结构化数组

    Returns:
        ValidationResult
    """
    result = ValidationResult(is_valid=True)

    if len(data) <= 1:
        result.stats = {"n_records": len(data), "n_overlaps": 0}
        return result

    time = data[TIME_FIELD]
    endtime = get_endtime(data)

    # 排序后检查
    sort_idx = np.argsort(time)
    sorted_time = time[sort_idx]
    sorted_endtime = endtime[sort_idx]

    # 检查 endtime[i] > time[i+1] 的情况
    overlaps = sorted_endtime[:-1] > sorted_time[1:]
    n_overlaps = np.sum(overlaps)

    if n_overlaps > 0:
        result.is_valid = False
        first_overlap = np.argmax(overlaps)
        result.errors.append(
            f"Found {n_overlaps} overlapping records. "
            f"First at index {first_overlap}: endtime={sorted_endtime[first_overlap]} > time={sorted_time[first_overlap + 1]}"
        )

    result.stats = {
        "n_records": len(data),
        "n_overlaps": int(n_overlaps),
        "max_overlap_ns": int(np.max(sorted_endtime[:-1] - sorted_time[1:])) if n_overlaps > 0 else 0,
    }

    return result


@export
def check_sorted_by_time(data: np.ndarray) -> ValidationResult:
    """
    检查数据是否按时间排序（综合检查）

    Args:
        data: 结构化数组

    Returns:
        ValidationResult 包含单调性和重叠检查
    """
    result = ValidationResult(is_valid=True)

    # 1. 检查 time 单调性
    mono_result = check_monotonic(data, TIME_FIELD, strict=False)
    if not mono_result.is_valid:
        result.is_valid = False
        result.errors.extend(mono_result.errors)

    # 2. 检查无重叠
    overlap_result = check_no_overlap(data)
    if not overlap_result.is_valid:
        result.is_valid = False
        result.errors.extend(overlap_result.errors)

    result.stats = {
        **mono_result.stats,
        "n_overlaps": overlap_result.stats.get("n_overlaps", 0),
    }

    return result


# =============================================================================
# 时间范围操作
# =============================================================================


@export
def get_time_range(data: np.ndarray) -> Tuple[int, int]:
    """
    获取数据的时间范围 [min_time, max_endtime)

    Args:
        data: 结构化数组

    Returns:
        (start_time, end_time) 元组
    """
    if len(data) == 0:
        return (0, 0)

    time = data[TIME_FIELD]
    endtime = get_endtime(data)

    return (int(np.min(time)), int(np.max(endtime)))


@export
def select_time_range(
    data: np.ndarray,
    start: Optional[int] = None,
    end: Optional[int] = None,
    strict: bool = False,
) -> np.ndarray:
    """
    选择时间范围内的记录

    Args:
        data: 结构化数组
        start: 起始时间 (inclusive)，None 表示无下界
        end: 结束时间 (exclusive)，None 表示无上界
        strict: True 表示记录必须完全在范围内，False 表示只要有交集即可

    Returns:
        筛选后的数组
    """
    if len(data) == 0:
        return data

    time = data[TIME_FIELD]
    endtime = get_endtime(data)

    mask = np.ones(len(data), dtype=bool)

    if strict:
        # 严格模式：记录完全在范围内
        if start is not None:
            mask &= time >= start
        if end is not None:
            mask &= endtime <= end
    else:
        # 宽松模式：只要有交集
        if start is not None:
            mask &= endtime > start  # endtime 超过 start
        if end is not None:
            mask &= time < end  # time 在 end 之前

    return data[mask]


@export
def clip_to_time_range(
    data: np.ndarray,
    start: Optional[int] = None,
    end: Optional[int] = None,
) -> np.ndarray:
    """
    裁剪记录到指定时间范围（会调整 time/length/endtime）

    注意：这会修改记录的时间信息，适用于波形数据的部分截取

    Args:
        data: 结构化数组（需要有 time, dt, length 字段）
        start: 起始时间 (inclusive)
        end: 结束时间 (exclusive)

    Returns:
        裁剪后的数组（新数组）
    """
    if len(data) == 0:
        return data

    # 先筛选有交集的记录
    result = select_time_range(data, start, end, strict=False).copy()
    if len(result) == 0:
        return result

    time = result[TIME_FIELD].astype(np.int64)
    dt = result[DT_FIELD].astype(np.int64)
    length = result[LENGTH_FIELD].astype(np.int64)
    endtime = time + dt * length

    # 裁剪起始边界
    if start is not None:
        # 需要调整 time 和 length
        clip_start = time < start
        if np.any(clip_start):
            # 计算需要跳过的样本数
            time_diff = start - time[clip_start]
            samples_to_skip = (time_diff + dt[clip_start] - 1) // dt[clip_start]  # 向上取整
            samples_to_skip = np.minimum(samples_to_skip, length[clip_start])

            # 更新 time 和 length
            result[TIME_FIELD][clip_start] = time[clip_start] + samples_to_skip * dt[clip_start]
            result[LENGTH_FIELD][clip_start] = length[clip_start] - samples_to_skip

    # 裁剪结束边界
    if end is not None:
        # 重新计算 endtime
        time = result[TIME_FIELD].astype(np.int64)
        dt = result[DT_FIELD].astype(np.int64)
        length = result[LENGTH_FIELD].astype(np.int64)
        endtime = time + dt * length

        clip_end = endtime > end
        if np.any(clip_end):
            # 计算新的 length
            new_endtime = np.minimum(endtime[clip_end], end)
            new_length = (new_endtime - time[clip_end]) // dt[clip_end]
            result[LENGTH_FIELD][clip_end] = new_length

    # 移除 length <= 0 的记录
    valid = result[LENGTH_FIELD] > 0
    result = result[valid]

    # 更新 endtime（如果有该字段）
    if ENDTIME_FIELD in result.dtype.names:
        result[ENDTIME_FIELD] = compute_endtime(result)

    return result


# =============================================================================
# Chunk 分割与合并
# =============================================================================


@export
def split_by_time(
    data: np.ndarray,
    chunk_duration_ns: int,
    start_time: Optional[int] = None,
) -> Generator[Tuple[np.ndarray, ChunkInfo], None, None]:
    """
    按固定时间间隔分割数据

    Args:
        data: 结构化数组
        chunk_duration_ns: 每个 chunk 的时间长度 (纳秒)
        start_time: 起始时间，默认使用数据中的最小时间

    Yields:
        (chunk_data, chunk_info) 元组
    """
    if len(data) == 0:
        return

    time = data[TIME_FIELD]
    if start_time is None:
        start_time = int(np.min(time))

    endtime = get_endtime(data)
    max_endtime = int(np.max(endtime))

    chunk_i = 0
    current_start = start_time

    while current_start < max_endtime:
        current_end = current_start + chunk_duration_ns

        # 选择在此时间范围内的记录
        chunk_data = select_time_range(data, current_start, current_end, strict=False)

        if len(chunk_data) > 0:
            chunk_endtime = get_endtime(chunk_data)
            info = ChunkInfo(
                start_time=current_start,
                end_time=min(current_end, int(np.max(chunk_endtime))),
                n_records=len(chunk_data),
                chunk_i=chunk_i,
            )
            yield chunk_data, info
            chunk_i += 1

        current_start = current_end


@export
def split_by_count(
    data: np.ndarray,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Generator[Tuple[np.ndarray, ChunkInfo], None, None]:
    """
    按记录数量分割数据

    Args:
        data: 结构化数组（应已按时间排序）
        chunk_size: 每个 chunk 的记录数

    Yields:
        (chunk_data, chunk_info) 元组
    """
    if len(data) == 0:
        return

    n_chunks = (len(data) + chunk_size - 1) // chunk_size

    for chunk_i in range(n_chunks):
        start_idx = chunk_i * chunk_size
        end_idx = min(start_idx + chunk_size, len(data))

        chunk_data = data[start_idx:end_idx]
        if len(chunk_data) == 0:
            continue

        time = chunk_data[TIME_FIELD]
        endtime = get_endtime(chunk_data)

        info = ChunkInfo(
            start_time=int(np.min(time)),
            end_time=int(np.max(endtime)),
            n_records=len(chunk_data),
            chunk_i=chunk_i,
        )
        yield chunk_data, info


@export
def split_by_breaks(
    data: np.ndarray,
    break_threshold_ns: int = DEFAULT_BREAK_THRESHOLD_NS,
    min_chunk_size: int = 1,
) -> Generator[Tuple[np.ndarray, ChunkInfo], None, None]:
    """
    按时间间隙分割数据（在大间隙处断开）

    Args:
        data: 结构化数组（应已按时间排序）
        break_threshold_ns: 间隙阈值 (纳秒)，超过此值则断开
        min_chunk_size: 最小 chunk 大小

    Yields:
        (chunk_data, chunk_info) 元组
    """
    if len(data) == 0:
        return

    time = data[TIME_FIELD]
    endtime = get_endtime(data)

    # 计算记录之间的间隙
    gaps = time[1:].astype(np.int64) - endtime[:-1].astype(np.int64)

    # 找到断点（间隙超过阈值）
    break_indices = np.where(gaps > break_threshold_ns)[0] + 1

    # 添加首尾
    break_indices = np.concatenate([[0], break_indices, [len(data)]])

    chunk_i = 0
    for i in range(len(break_indices) - 1):
        start_idx = break_indices[i]
        end_idx = break_indices[i + 1]

        if end_idx - start_idx < min_chunk_size:
            continue

        chunk_data = data[start_idx:end_idx]

        chunk_time = chunk_data[TIME_FIELD]
        chunk_endtime = get_endtime(chunk_data)

        info = ChunkInfo(
            start_time=int(np.min(chunk_time)),
            end_time=int(np.max(chunk_endtime)),
            n_records=len(chunk_data),
            chunk_i=chunk_i,
        )
        yield chunk_data, info
        chunk_i += 1


@export
def merge_chunks(chunks: Iterator[np.ndarray], sort: bool = True) -> np.ndarray:
    """
    合并多个 chunk 为单个数组

    Args:
        chunks: chunk 迭代器
        sort: 是否按时间排序

    Returns:
        合并后的数组
    """
    chunk_list = list(chunks)

    if len(chunk_list) == 0:
        return np.array([])

    result = np.concatenate(chunk_list)

    if sort and len(result) > 0 and TIME_FIELD in result.dtype.names:
        result = result[np.argsort(result[TIME_FIELD])]

    return result


# =============================================================================
# Rechunk（重分块）
# =============================================================================


@export
def rechunk(
    chunks: Iterator[Tuple[np.ndarray, ChunkInfo]],
    target_size: int = DEFAULT_CHUNK_SIZE,
    max_size: Optional[int] = None,
) -> Generator[Tuple[np.ndarray, ChunkInfo], None, None]:
    """
    重新分块，使每个 chunk 大小接近目标值

    这对于上游产生不规则 chunk 的情况很有用，可以让下游处理更均匀。

    Args:
        chunks: 输入 chunk 迭代器
        target_size: 目标 chunk 大小
        max_size: 最大 chunk 大小，默认为 target_size * 2

    Yields:
        (chunk_data, chunk_info) 元组
    """
    if max_size is None:
        max_size = target_size * 2

    buffer: List[np.ndarray] = []
    buffer_size = 0
    chunk_i = 0

    def flush_buffer() -> Tuple[np.ndarray, ChunkInfo]:
        nonlocal buffer, buffer_size, chunk_i
        if not buffer:
            return None, None

        merged = np.concatenate(buffer) if len(buffer) > 1 else buffer[0]
        time = merged[TIME_FIELD]
        endtime = get_endtime(merged)

        info = ChunkInfo(
            start_time=int(np.min(time)),
            end_time=int(np.max(endtime)),
            n_records=len(merged),
            chunk_i=chunk_i,
        )
        chunk_i += 1
        buffer = []
        buffer_size = 0
        return merged, info

    for data, _ in chunks:
        if len(data) == 0:
            continue

        # 如果单个 chunk 已经超过 max_size，直接 yield
        if len(data) >= max_size:
            # 先 flush buffer
            if buffer_size > 0:
                merged, info = flush_buffer()
                if merged is not None:
                    yield merged, info

            # 分割大 chunk
            for sub_chunk, sub_info in split_by_count(data, target_size):
                sub_info.chunk_i = chunk_i
                chunk_i += 1
                yield sub_chunk, sub_info
            continue

        # 添加到 buffer
        buffer.append(data)
        buffer_size += len(data)

        # 检查是否需要 flush
        if buffer_size >= target_size:
            merged, info = flush_buffer()
            if merged is not None:
                yield merged, info

    # 最后 flush 剩余的
    if buffer_size > 0:
        merged, info = flush_buffer()
        if merged is not None:
            yield merged, info


@export
def rechunk_to_boundaries(
    chunks: Iterator[Tuple[np.ndarray, ChunkInfo]],
    boundary_times: np.ndarray,
) -> Generator[Tuple[np.ndarray, ChunkInfo], None, None]:
    """
    重新分块到指定的时间边界

    这对于让多个数据流对齐到相同的 chunk 边界很有用。

    Args:
        chunks: 输入 chunk 迭代器
        boundary_times: 边界时间数组（已排序）

    Yields:
        (chunk_data, chunk_info) 元组
    """
    if len(boundary_times) == 0:
        yield from chunks
        return

    # 确保边界排序
    boundary_times = np.sort(boundary_times)

    buffer: List[np.ndarray] = []
    current_boundary_idx = 0
    chunk_i = 0

    for data, _ in chunks:
        if len(data) == 0:
            continue

        buffer.append(data)

        # 检查是否有数据超过当前边界
        merged = np.concatenate(buffer) if len(buffer) > 1 else buffer[0]
        endtime = get_endtime(merged)
        max_endtime = np.max(endtime)

        while current_boundary_idx < len(boundary_times) and max_endtime >= boundary_times[current_boundary_idx]:
            boundary = boundary_times[current_boundary_idx]

            # 分割出 boundary 之前的数据
            before = select_time_range(merged, end=boundary, strict=False)
            after = select_time_range(merged, start=boundary, strict=False)

            if len(before) > 0:
                time = before[TIME_FIELD]
                before_endtime = get_endtime(before)
                info = ChunkInfo(
                    start_time=int(np.min(time)),
                    end_time=int(np.max(before_endtime)),
                    n_records=len(before),
                    chunk_i=chunk_i,
                )
                chunk_i += 1
                yield before, info

            # 更新 merged 为剩余数据
            merged = after
            buffer = [merged] if len(merged) > 0 else []
            current_boundary_idx += 1

            if len(merged) == 0:
                break
            max_endtime = np.max(get_endtime(merged))

    # Flush 剩余数据
    if buffer:
        merged = np.concatenate(buffer) if len(buffer) > 1 else buffer[0]
        if len(merged) > 0:
            time = merged[TIME_FIELD]
            endtime = get_endtime(merged)
            info = ChunkInfo(
                start_time=int(np.min(time)),
                end_time=int(np.max(endtime)),
                n_records=len(merged),
                chunk_i=chunk_i,
            )
            yield merged, info


# =============================================================================
# Chunk 边界检查
# =============================================================================


@export
def check_chunk_boundaries(
    data: np.ndarray,
    chunk_start: int,
    chunk_end: int,
) -> ValidationResult:
    """
    检查数据是否违反 chunk 边界

    违规情况：
    - 记录 time < chunk_start
    - 记录 endtime > chunk_end

    Args:
        data: 结构化数组
        chunk_start: chunk 起始时间
        chunk_end: chunk 结束时间

    Returns:
        ValidationResult
    """
    result = ValidationResult(is_valid=True)

    if len(data) == 0:
        result.stats = {"n_records": 0, "violations": 0}
        return result

    time = data[TIME_FIELD]
    endtime = get_endtime(data)

    # 检查起始边界
    before_start = time < chunk_start
    n_before = np.sum(before_start)
    if n_before > 0:
        result.is_valid = False
        min_time = np.min(time[before_start])
        result.errors.append(f"{n_before} records start before chunk boundary (earliest: {min_time} < {chunk_start})")

    # 检查结束边界
    after_end = endtime > chunk_end
    n_after = np.sum(after_end)
    if n_after > 0:
        result.is_valid = False
        max_endtime = np.max(endtime[after_end])
        result.errors.append(f"{n_after} records extend beyond chunk boundary (latest: {max_endtime} > {chunk_end})")

    result.stats = {
        "n_records": len(data),
        "n_before_start": int(n_before),
        "n_after_end": int(n_after),
        "violations": int(n_before + n_after),
    }

    return result


@export
def check_chunk_continuity(
    chunks: List[Tuple[np.ndarray, ChunkInfo]],
    allow_gaps: bool = False,
    max_gap_ns: int = 0,
) -> ValidationResult:
    """
    检查 chunk 序列的连续性

    Args:
        chunks: (data, info) 元组列表
        allow_gaps: 是否允许间隙
        max_gap_ns: 允许的最大间隙 (纳秒)

    Returns:
        ValidationResult
    """
    result = ValidationResult(is_valid=True)

    if len(chunks) <= 1:
        result.stats = {"n_chunks": len(chunks), "n_gaps": 0, "n_overlaps": 0}
        return result

    infos = [info for _, info in chunks]
    n_gaps = 0
    n_overlaps = 0
    max_gap = 0

    for i in range(len(infos) - 1):
        gap = infos[i + 1].start_time - infos[i].end_time

        if gap < 0:
            # 重叠
            n_overlaps += 1
            result.errors.append(
                f"Chunks {i} and {i + 1} overlap by {-gap}ns "
                f"(chunk {i} ends at {infos[i].end_time}, chunk {i + 1} starts at {infos[i + 1].start_time})"
            )
        elif gap > max_gap_ns:
            # 间隙
            n_gaps += 1
            max_gap = max(max_gap, gap)
            if not allow_gaps:
                result.errors.append(
                    f"Gap of {gap}ns between chunks {i} and {i + 1} (exceeds max allowed {max_gap_ns}ns)"
                )

    if n_overlaps > 0 or (not allow_gaps and n_gaps > 0):
        result.is_valid = False

    if n_gaps > 0 and allow_gaps:
        result.warnings.append(f"Found {n_gaps} gaps between chunks (max: {max_gap}ns)")

    result.stats = {
        "n_chunks": len(chunks),
        "n_gaps": n_gaps,
        "n_overlaps": n_overlaps,
        "max_gap_ns": max_gap,
    }

    return result


# =============================================================================
# 工具函数
# =============================================================================


def _validate_time_fields(data: np.ndarray, require_length: bool = True):
    """验证数组包含必要的时间字段"""
    if not hasattr(data, "dtype") or data.dtype.names is None:
        raise TypeError("Data must be a structured numpy array")

    required = [TIME_FIELD, DT_FIELD]
    if require_length:
        required.append(LENGTH_FIELD)

    missing = [f for f in required if f not in data.dtype.names]
    if missing:
        raise KeyError(f"Missing required fields: {missing}")


@export
def sort_by_time(data: np.ndarray) -> np.ndarray:
    """按时间排序数组"""
    if len(data) == 0:
        return data
    return data[np.argsort(data[TIME_FIELD])]


@export
def concat_sorted(arrays: List[np.ndarray], already_sorted: bool = False) -> np.ndarray:
    """
    连接多个数组并保持时间排序

    Args:
        arrays: 数组列表
        already_sorted: 如果为 True，假设每个数组内部已排序，使用归并

    Returns:
        合并并排序的数组
    """
    arrays = [a for a in arrays if len(a) > 0]

    if len(arrays) == 0:
        return np.array([])
    if len(arrays) == 1:
        return arrays[0]

    result = np.concatenate(arrays)

    if already_sorted:
        # TODO: 可以实现更高效的归并排序
        pass

    return sort_by_time(result)


@export
def time_to_samples(time_ns: int, dt_ns: int) -> int:
    """将时间转换为样本数"""
    return time_ns // dt_ns


@export
def samples_to_time(samples: int, dt_ns: int) -> int:
    """将样本数转换为时间"""
    return samples * dt_ns
