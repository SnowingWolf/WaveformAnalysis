"""公共 record 处理工具函数，供所有 CPU 插件使用。

提供统一的接口用于：
- Record lookup（record_id → record 映射）
- 字段访问（带 fallback 和默认值）
- Record 索引解析

这些函数被多个插件共享，避免代码重复。
"""

from typing import Any

import numpy as np

# Keep the identity check bounded in memory.  ``np.array_equal(ids,
# np.arange(len(ids)))`` is convenient, but for a production records cache it
# allocates another full int64 array (hundreds of MiB for tens of millions of
# records) before the first waveform window is even read.
_IDENTITY_CHECK_CHUNK_SIZE = 1_000_000


def _is_identity_ids(ids: np.ndarray) -> bool:
    """Return whether ``ids`` is exactly ``0, 1, ..., len(ids)-1``.

    The comparison is chunked so the fast direct-lookup decision does not
    create a full-size temporary ``arange``.  The result is intentionally
    strict: non-contiguous, reordered, and duplicated record IDs still use the
    sorted lookup path.
    """
    if len(ids) == 0:
        return True
    if int(ids[0]) != 0 or int(ids[-1]) != len(ids) - 1:
        return False
    for start in range(0, len(ids), _IDENTITY_CHECK_CHUNK_SIZE):
        stop = min(start + _IDENTITY_CHECK_CHUNK_SIZE, len(ids))
        expected = np.arange(start, stop, dtype=np.int64)
        if not np.array_equal(ids[start:stop], expected):
            return False
    return True


# =============================================================================
# Record Lookup (优化的 record_id 查找)
# =============================================================================


class RecordLookup:
    """优化的 record lookup 索引。

    支持两种模式：
    - direct: record_id == array index (O(1) 访问)
    - sorted: 排序后的 record_id (O(log n) 二分查找)
    """

    __slots__ = ("mode", "_records", "_ids_sorted", "_order")

    def __init__(self, records: np.ndarray):
        """构建优化的 record lookup 索引。

        Args:
            records: 包含 record_id 字段的结构化数组
        """
        self._records = records
        names = records.dtype.names or ()

        if "record_id" not in names:
            # 没有 record_id 字段，假设 index 就是 id
            self.mode = "direct"
            self._ids_sorted = None
            self._order = None
            return

        ids = records["record_id"].astype(np.int64, copy=False)

        # 检查是否 record_id == row index（最优情况）
        if len(ids) == len(records) and _is_identity_ids(ids):
            self.mode = "direct"
            self._ids_sorted = None
            self._order = None
        else:
            # 使用排序索引
            self.mode = "sorted"
            self._order = np.argsort(ids, kind="mergesort")
            self._ids_sorted = ids[self._order]

    def get(self, record_id: int) -> Any:
        """获取指定 record_id 的 record。

        Args:
            record_id: 要查找的 record ID

        Returns:
            对应的 record（结构化数组的一行）

        Raises:
            ValueError: 如果 record_id 不存在
        """
        if self.mode == "direct":
            if record_id < 0 or record_id >= len(self._records):
                raise ValueError(f"Record lookup: could not resolve record_id={record_id}")
            return self._records[record_id]

        # mode == "sorted"
        if self._ids_sorted is None or self._order is None:
            raise RuntimeError("Sorted mode requires _ids_sorted and _order")

        pos = np.searchsorted(self._ids_sorted, record_id)

        if pos >= len(self._ids_sorted) or self._ids_sorted[pos] != record_id:
            raise ValueError(f"Record lookup: could not resolve record_id={record_id}")

        return self._records[self._order[pos]]

    def get_indices(self, record_ids: np.ndarray) -> np.ndarray:
        """批量解析 record_id 到 array index。

        Args:
            record_ids: 要查找的 record ID 数组

        Returns:
            对应的 array index 数组

        Raises:
            ValueError: 如果任何 record_id 不存在
        """
        record_ids = np.asarray(record_ids, dtype=np.int64)

        if self.mode == "direct":
            bad_mask = (record_ids < 0) | (record_ids >= len(self._records))
            if np.any(bad_mask):
                bad_id = record_ids[bad_mask][0]
                raise ValueError(f"Record lookup: could not resolve record_id={bad_id}")
            return record_ids

        # mode == "sorted"
        if self._ids_sorted is None or self._order is None:
            raise RuntimeError("Sorted mode requires _ids_sorted and _order")

        pos = np.searchsorted(self._ids_sorted, record_ids)
        bad = (pos >= len(self._ids_sorted)) | (self._ids_sorted[pos] != record_ids)
        if np.any(bad):
            bad_id = record_ids[bad][0]
            raise ValueError(f"Record lookup: could not resolve record_id={bad_id}")

        return self._order[pos]


def build_record_lookup_legacy(records: np.ndarray) -> dict[int, Any]:
    """遗留的 dict-based record lookup（已弃用，请使用 RecordLookup）。

    Args:
        records: 结构化数组

    Returns:
        record_id → record 的字典映射
    """
    names = records.dtype.names or ()
    if "record_id" in names:
        return {int(rec["record_id"]): rec for rec in records}
    return dict(enumerate(records))


# =============================================================================
# 字段访问（带 fallback 和默认值）
# =============================================================================


def get_field_safe(
    arr: np.ndarray, *candidates: str, default: Any = None, dtype: type | None = None
) -> np.ndarray:
    """安全地从结构化数组中获取字段，支持多个候选名称和默认值。

    按顺序尝试候选字段名，返回第一个存在的字段。
    如果所有候选都不存在：
    - 如果提供了 default，返回填充该默认值的数组
    - 否则抛出 ValueError

    Args:
        arr: 结构化数组
        *candidates: 候选字段名（按优先级顺序）
        default: 如果字段不存在时的默认值（可选）
        dtype: 返回数组的 dtype（可选，默认推断）

    Returns:
        字段数组或默认值数组

    Raises:
        ValueError: 如果所有候选字段都不存在且未提供 default

    Example:
        >>> # 尝试 "dt" 或 "dt_ns"，不存在则返回 10
        >>> dt_values = get_field_safe(records, "dt", "dt_ns", default=10, dtype=np.int64)
    """
    names = arr.dtype.names or ()

    # 尝试每个候选字段
    for name in candidates:
        if name in names:
            result = arr[name]
            if dtype is not None:
                return np.asarray(result, dtype=dtype)
            return result

    # 所有候选都不存在
    if default is not None:
        if dtype is None:
            dtype = type(default)
        return np.full(len(arr), default, dtype=dtype)

    raise ValueError(
        f"None of the candidate fields {candidates} found in array. " f"Available fields: {names}"
    )


def field_or_default(
    arr: np.ndarray, name: str, default: Any, dtype: type | None = None
) -> np.ndarray:
    """从结构化数组中获取字段，不存在则返回默认值。

    这是 get_field_safe 的简化版本，仅支持单个字段名。

    Args:
        arr: 结构化数组
        name: 字段名
        default: 字段不存在时的默认值
        dtype: 返回数组的 dtype（可选）

    Returns:
        字段数组或默认值数组
    """
    if dtype is None:
        dtype = type(default)

    names = arr.dtype.names or ()
    if name in names:
        return np.asarray(arr[name], dtype=dtype)
    return np.full(len(arr), default, dtype=dtype)


# =============================================================================
# Record 索引解析
# =============================================================================


def resolve_record_indices(records: np.ndarray, record_ids: np.ndarray) -> np.ndarray:
    """将 record_id 转换为 records 数组的行索引。

    优先处理 record_id == row index 的快路径（O(1)）。
    否则使用排序 + 二分查找（O(n log n) + O(m log n)）。

    Args:
        records: 包含 record_id 字段的结构化数组
        record_ids: 要解析的 record ID 数组

    Returns:
        对应的行索引数组

    Raises:
        ValueError: 如果任何 record_id 不存在
    """
    # 使用 RecordLookup 的批量接口
    lookup = RecordLookup(records)
    return lookup.get_indices(record_ids)
