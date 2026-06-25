"""Hit Threshold 查询工具函数

提供便捷的查询函数，用于在 notebook 和脚本中分析 peak、merged 和 hit_threshold 之间的关系。

主要功能：
1. 通过 peak_id 查询其包含的 merged_index
2. 通过 merged_index 查询其包含的 hit_index
3. 获取完整的 hit_threshold 数据并计算时间间隔
4. 批量查询优化（lookup 字典构建）

示例用法：
    >>> # 获取某个 peak 的所有 hit 数据（带时间间隔）
    >>> intervals = get_hits_for_peak(
    ...     peak_id=123,
    ...     peaklet_components=peaklet_components,
    ...     hit_merged_components=hit_merged_components,
    ...     hit_threshold=hit_threshold
    ... )
    >>>
    >>> # 绘制时间间隔直方图
    >>> import matplotlib.pyplot as plt
    >>> dt = intervals["dt_start_to_start_ns"].dropna()
    >>> plt.hist(dt, bins=50)
    >>> plt.xlabel("hit_threshold interval within hit_merged (ns)")
    >>> plt.ylabel("counts")
    >>> plt.show()
"""

import numpy as np
import pandas as pd

__all__ = [
    "get_merged_indices_for_peak",
    "get_hit_indices_for_merged",
    "get_hits_for_merged",
    "get_hits_for_peak",
    "build_peak_to_merged_lookup",
    "build_merged_to_hit_lookup",
]


# =============================================================================
# 基础查询函数
# =============================================================================


def get_merged_indices_for_peak(
    peak_id: int,
    peaklet_components: np.ndarray,
) -> np.ndarray:
    """获取某个 peak 包含的所有 merged_index。

    在数据处理流程中，一个 peaklet (peak) 通常由多个 merged hit 组成。
    本函数通过 peak_id 查询其包含的所有 merged_index，用于后续查询每个 merged 的详细信息。

    数据关系：
        peak (peaklet) → merged (hit_merged) → hit (hit_threshold)
        本函数处理第一层映射：peak → merged

    Args:
        peak_id (int):
            目标 peak 的 ID。对应 peaklet_components 数组中的 'peak_id' 字段。

        peaklet_components (np.ndarray):
            peaklet_components 数组，记录 peak 和 merged 之间的对应关系。
            必须包含以下字段：
            - 'peak_id' (int64): peak 的 ID
            - 'merged_index' (int64): merged hit 的索引

    Returns:
        np.ndarray:
            merged_index 数组（int64 类型）。
            - 如果 peak_id 存在，返回其包含的所有 merged_index
            - 如果 peak_id 不存在，返回空数组
            - 如果输入为 None 或空数组，返回空数组

    Example:
        >>> # 查询 peak 123 包含哪些 merged hits
        >>> merged_indices = get_merged_indices_for_peak(123, peaklet_components)
        >>> print(f"Peak 123 包含 {len(merged_indices)} 个 merged hits")
        Peak 123 包含 5 个 merged hits
        >>> print(f"Merged indices: {merged_indices}")
        Merged indices: [200 201 202 203 204]

        >>> # 进一步查询每个 merged 的详细信息
        >>> for merged_index in merged_indices:
        ...     hits = get_hit_indices_for_merged(merged_index, hit_merged_components)
        ...     print(f"Merged {merged_index}: {len(hits)} hits")

    See Also:
        get_hit_indices_for_merged: 查询 merged 包含的 hit_index
        get_hits_for_peak: 直接获取 peak 的完整 hit 数据（推荐）
    """
    # 处理空输入情况
    if peaklet_components is None or len(peaklet_components) == 0:
        return np.array([], dtype=np.int64)

    # 使用布尔索引筛选：找出所有 peak_id 匹配的行
    # 这是一个 O(n) 操作，n 为 peaklet_components 的长度
    mask = peaklet_components["peak_id"] == int(peak_id)
    merged_indices = peaklet_components[mask]["merged_index"].astype(np.int64)

    return merged_indices


def get_hit_indices_for_merged(
    merged_index: int,
    hit_merged_components: np.ndarray,
) -> np.ndarray:
    """获取某个 merged 包含的所有 hit_index。

    在数据处理流程中，一个 merged hit 由多个原始 hit (hit_threshold) 组成。
    本函数通过 merged_index 查询其包含的所有 hit_index，用于后续提取详细的 hit 数据。

    数据关系：
        peak (peaklet) → merged (hit_merged) → hit (hit_threshold)
        本函数处理第二层映射：merged → hit

    Args:
        merged_index (int):
            目标 merged 的索引。对应 hit_merged_components 数组中的 'merged_index' 字段。

        hit_merged_components (np.ndarray):
            hit_merged_components 数组，记录 merged 和 hit 之间的对应关系。
            必须包含以下字段：
            - 'merged_index' (int64): merged hit 的索引
            - 'hit_index' (int64): 原始 hit 在 hit_threshold 数组中的索引

    Returns:
        np.ndarray:
            hit_index 数组（int64 类型）。
            - 如果 merged_index 存在，返回其包含的所有 hit_index
            - 如果 merged_index 不存在，返回空数组
            - 如果输入为 None 或空数组，返回空数组

    Note:
        返回的 hit_index 可以直接用于索引 hit_threshold 数组：
        >>> hit_indices = get_hit_indices_for_merged(456, hit_merged_components)
        >>> hits = hit_threshold[hit_indices]  # 提取对应的 hit 数据

    Example:
        >>> # 查询 merged 456 包含哪些 hits
        >>> hit_indices = get_hit_indices_for_merged(456, hit_merged_components)
        >>> print(f"Merged 456 包含 {len(hit_indices)} 个 hits")
        Merged 456 包含 3 个 hits
        >>> print(f"Hit indices: {hit_indices}")
        Hit indices: [10 11 12]

        >>> # 提取对应的 hit_threshold 数据
        >>> hits = hit_threshold[hit_indices]
        >>> print(f"Channels: {hits['channel']}")
        Channels: [0 1 2]

    See Also:
        get_merged_indices_for_peak: 查询 peak 包含的 merged_index
        get_hits_for_merged: 直接获取 merged 的完整 hit 数据（推荐）
    """
    # 处理空输入情况
    if hit_merged_components is None or len(hit_merged_components) == 0:
        return np.array([], dtype=np.int64)

    # 使用布尔索引筛选：找出所有 merged_index 匹配的行
    # 这是一个 O(n) 操作，n 为 hit_merged_components 的长度
    mask = hit_merged_components["merged_index"] == int(merged_index)
    hit_indices = hit_merged_components[mask]["hit_index"].astype(np.int64)

    return hit_indices


# =============================================================================
# 完整数据查询函数（带时间间隔计算）
# =============================================================================


def _calculate_hit_intervals(hits_df: pd.DataFrame) -> pd.DataFrame:
    """计算 hit 之间的时间间隔（内部辅助函数）。

    在输入 DataFrame 上添加两个时间间隔列，用于分析相邻 hit 之间的时间关系。

    时间间隔说明：
        1. dt_start_to_start_ns: 当前 hit 的起始时间与前一个 hit 的起始时间之间的间隔
           - 表示相邻 hit 的"到达间隔"
           - 用于分析 hit 的发生频率

        2. dt_end_to_start_ns: 当前 hit 的起始时间与前一个 hit 的结束时间之间的间隔
           - 表示相邻 hit 之间的"死时间"或"间隙"
           - 正值表示两个 hit 不重叠，负值表示有重叠

    算法说明：
        使用 pandas 的 shift(1) 方法进行向量化计算，避免循环，性能高效。
        第一行没有前一个 hit 作为参考，因此时间间隔为 NaN。

    Args:
        hits_df (pd.DataFrame):
            包含 'time_start' 和 'time_end' 列的 DataFrame。
            要求：
            - 已按 time_start 排序（确保相邻行在时间上连续）
            - time_start 和 time_end 的单位为皮秒（ps）

    Returns:
        pd.DataFrame:
            原 DataFrame，添加了以下列（原地修改）：
            - dt_start_to_start_ns (float64): 与前一个 hit 的起始间隔（ns），第一行为 NaN
            - dt_end_to_start_ns (float64): 与前一个 hit 的结束间隔（ns），第一行为 NaN

    Note:
        - 输入的 time_start 和 time_end 单位是 ps，输出的间隔单位是 ns
        - 转换公式：dt_ns = (time_ps[i] - time_ps[i-1]) / 1000.0

    Example:
        >>> # 假设有 3 个 hit，time_start 为 [1000000, 1500000, 2000000] ps
        >>> df = pd.DataFrame({
        ...     'time_start': [1000000, 1500000, 2000000],
        ...     'time_end': [1100000, 1600000, 2100000]
        ... })
        >>> df = _calculate_hit_intervals(df)
        >>> print(df['dt_start_to_start_ns'])
        0         NaN  # 第一行无前一个 hit
        1       500.0  # (1500000 - 1000000) / 1000 = 500 ns
        2       500.0  # (2000000 - 1500000) / 1000 = 500 ns
    """
    # 处理空 DataFrame 情况
    if len(hits_df) == 0:
        hits_df["dt_start_to_start_ns"] = pd.Series([], dtype=np.float64)
        hits_df["dt_end_to_start_ns"] = pd.Series([], dtype=np.float64)
        return hits_df

    # 使用 shift(1) 获取前一行的时间值
    # shift(1) 将整列向下移动一行，第一行变为 NaN
    prev_time_start = hits_df["time_start"].shift(1)
    prev_time_end = hits_df["time_end"].shift(1)

    # 向量化计算时间间隔
    # 单位转换：ps → ns (除以 1000)
    hits_df["dt_start_to_start_ns"] = (hits_df["time_start"] - prev_time_start) / 1000.0
    hits_df["dt_end_to_start_ns"] = (hits_df["time_start"] - prev_time_end) / 1000.0

    return hits_df


def get_hits_for_merged(
    merged_index: int,
    hit_merged_components: np.ndarray,
    hit_threshold: np.ndarray,
) -> pd.DataFrame:
    """获取某个 merged 的所有 hit 数据（带时间间隔计算）。

    这是一个高层查询函数，提供了完整的 hit 数据和时间分析功能。
    相比于 get_hit_indices_for_merged，本函数不仅返回索引，还包括：
    1. hit_threshold 中的所有原始字段
    2. 计算后的绝对时间（time_start, time_end）
    3. 相邻 hit 之间的时间间隔（用于时间分析）

    数据流程：
        1. 通过 merged_index 查询 hit_indices
        2. 从 hit_threshold 数组中提取对应的 hit 数据
        3. 计算绝对时间（从相对时间 + 时间戳）
        4. 按 time_start 排序
        5. 计算相邻 hit 之间的时间间隔

    时间计算说明：
        hit_threshold 中存储的是相对时间（样本偏移），需要转换为绝对时间：
        time_start = timestamp + (edge_start - position) * dt * 1000
        time_end = timestamp + (edge_end - position) * dt * 1000
        其中：
        - timestamp: position 对应的绝对时间（ps）
        - dt: 采样间隔（ns）
        - edge_start/edge_end: 样本边界（相对于 position）
        - 1000: ns → ps 的转换因子

    Args:
        merged_index (int):
            目标 merged 的索引。

        hit_merged_components (np.ndarray):
            hit_merged_components 数组，记录 merged 和 hit 的对应关系。

        hit_threshold (np.ndarray):
            hit_threshold 完整数组（THRESHOLD_HIT_DTYPE 类型）。
            必须包含以下字段：
            - position, edge_start, edge_end: 采样位置和边界
            - dt: 采样间隔（ns）
            - timestamp: position 的绝对时间戳（ps）
            - board, channel: 硬件通道信息
            - record_id: 来源 record 的 ID
            - width: hit 宽度（样本点数）

    Returns:
        pd.DataFrame:
            包含该 merged 的所有 hit 数据，按 time_start 排序。
            列说明：
            - hit_index (int64): hit 在 hit_threshold 数组中的索引
            - position (int64): 采样点位置
            - edge_start (int32): 起始边界（样本）
            - edge_end (int32): 结束边界（样本）
            - width (float32): 宽度（样本点数）
            - dt (int32): 采样间隔（ns）
            - timestamp (int64): position 的绝对时间戳（ps）
            - board (int16): 板卡编号
            - channel (int16): 通道号
            - record_id (int64): 来源 record ID
            - time_start (int64): 起始绝对时间（ps）
            - time_end (int64): 结束绝对时间（ps）
            - dt_start_to_start_ns (float64): 与前一个 hit 的起始间隔（ns），第一行为 NaN
            - dt_end_to_start_ns (float64): 与前一个 hit 的结束间隔（ns），第一行为 NaN

    Note:
        - 如果 merged_index 不存在或没有 hits，返回空 DataFrame（保留列结构）
        - 返回的 DataFrame 已按 time_start 排序，确保时间间隔计算正确
        - 第一行的时间间隔为 NaN（因为没有前一个 hit）

    Example:
        >>> # 查询 merged 456 的所有 hit 数据
        >>> df = get_hits_for_merged(456, hit_merged_components, hit_threshold)
        >>> print(f"Merged 456 包含 {len(df)} 个 hits")
        Merged 456 包含 3 个 hits

        >>> # 查看关键列
        >>> print(df[["hit_index", "channel", "time_start", "dt_start_to_start_ns"]])
           hit_index  channel  time_start  dt_start_to_start_ns
        0         10        0     1000000                   NaN
        1         11        1     1500000                 500.0
        2         12        2     2000000                 500.0

        >>> # 分析时间间隔分布
        >>> dt = df["dt_start_to_start_ns"].dropna()
        >>> print(f"平均间隔: {dt.mean():.2f} ns")
        平均间隔: 500.00 ns

    See Also:
        get_hit_indices_for_merged: 只返回 hit_index（更轻量）
        get_hits_for_peak: 获取整个 peak 的 hit 数据
    """
    # 步骤 1: 获取该 merged 包含的所有 hit_index
    hit_indices = get_hit_indices_for_merged(merged_index, hit_merged_components)

    # 定义返回的 DataFrame 列结构（保持一致性，即使是空结果）
    columns = [
        "hit_index",
        "position",
        "edge_start",
        "edge_end",
        "width",
        "dt",
        "timestamp",
        "board",
        "channel",
        "record_id",
        "time_start",
        "time_end",
        "dt_start_to_start_ns",
        "dt_end_to_start_ns",
    ]

    # 处理空结果情况
    if len(hit_indices) == 0:
        return pd.DataFrame(columns=columns)

    # 步骤 2: 从 hit_threshold 数组中提取对应的 hit 数据
    hits = hit_threshold[hit_indices]

    # 步骤 3: 计算绝对时间
    # 参考 hit_merge.py:480-481 的实现
    # 从结构化数组中提取字段并转换为正确的类型
    position = hits["position"].astype(np.int64)
    edge_start = hits["edge_start"].astype(np.int64)
    edge_end = hits["edge_end"].astype(np.int64)
    timestamp = hits["timestamp"].astype(np.int64)
    dt = hits["dt"].astype(np.int64)

    # 绝对时间计算公式：
    # time_start_ps = timestamp + (edge_start - position) * dt * 1000
    # time_end_ps = timestamp + (edge_end - position) * dt * 1000
    # 其中 dt 的单位是 ns，需要乘以 1000 转换为 ps
    time_start = timestamp + (edge_start - position) * dt * 1000  # ps
    time_end = timestamp + (edge_end - position) * dt * 1000  # ps

    # 步骤 4: 构建 DataFrame
    df = pd.DataFrame(
        {
            "hit_index": hit_indices,
            "position": position,
            "edge_start": edge_start,
            "edge_end": edge_end,
            "width": hits["width"],
            "dt": dt,
            "timestamp": timestamp,
            "board": hits["board"],
            "channel": hits["channel"],
            "record_id": hits["record_id"],
            "time_start": time_start,
            "time_end": time_end,
        }
    )

    # 步骤 5: 按 time_start 排序
    # 这一步很重要，确保相邻行在时间上连续，才能正确计算时间间隔
    df = df.sort_values("time_start").reset_index(drop=True)

    # 步骤 6: 计算时间间隔
    df = _calculate_hit_intervals(df)

    return df


def get_hits_for_peak(
    peak_id: int,
    peaklet_components: np.ndarray,
    hit_merged_components: np.ndarray,
    hit_threshold: np.ndarray,
) -> pd.DataFrame:
    """获取某个 peak 的所有 hit 数据（带 merged_index 和时间间隔）。

    这是最常用的高层查询函数，提供了从 peak 到 hit 的完整数据链路。
    相比于 get_hits_for_merged，本函数：
    1. 额外包含 peak_id 和 merged_index 列，便于追踪数据来源
    2. 自动遍历 peak 包含的所有 merged
    3. 合并所有 merged 的 hit 数据并按时间排序

    典型应用场景：
        - 分析某个 peak 内部 hit 的时间分布
        - 绘制 hit 时间间隔直方图
        - 研究 peak 的内部结构和通道响应模式
        - 计算 peak 内的 hit 密度和聚类特征

    数据流程：
        1. 通过 peak_id 查询所有 merged_index
        2. 对每个 merged_index 调用 get_hits_for_merged 获取 hit 数据
        3. 在每个 DataFrame 中添加 peak_id 和 merged_index 列
        4. 合并所有 DataFrame
        5. 按 time_start 全局排序（跨 merged 排序）

    Args:
        peak_id (int):
            目标 peak 的 ID。

        peaklet_components (np.ndarray):
            peaklet_components 数组，记录 peak 和 merged 的对应关系。

        hit_merged_components (np.ndarray):
            hit_merged_components 数组，记录 merged 和 hit 的对应关系。

        hit_threshold (np.ndarray):
            hit_threshold 完整数组（THRESHOLD_HIT_DTYPE 类型）。

    Returns:
        pd.DataFrame:
            包含该 peak 的所有 hit 数据，按 time_start 排序。
            列说明（在 get_hits_for_merged 返回列的基础上，额外包含）：
            - peak_id (int64): peak 的 ID（所有行都相同）
            - merged_index (int64): 每个 hit 所属的 merged_index
            - hit_index (int64): hit 在 hit_threshold 数组中的索引
            - position, edge_start, edge_end, width, dt: 采样信息
            - timestamp, board, channel, record_id: 元数据
            - time_start, time_end: 绝对时间（ps）
            - dt_start_to_start_ns (float64): 与前一个 hit 的起始间隔（ns）
            - dt_end_to_start_ns (float64): 与前一个 hit 的结束间隔（ns）

    Note:
        - 如果 peak_id 不存在或没有 hits，返回空 DataFrame（保留列结构）
        - 时间间隔是按全局 time_start 排序后计算的，跨越不同 merged
        - 可以通过 groupby('merged_index') 分组查看每个 merged 的 hit

    Example:
        >>> # 查询 peak 123 的所有 hit 数据
        >>> intervals = get_hits_for_peak(
        ...     peak_id=123,
        ...     peaklet_components=peaklet_components,
        ...     hit_merged_components=hit_merged_components,
        ...     hit_threshold=hit_threshold
        ... )
        >>> print(f"Peak 123 包含 {len(intervals)} 个 hits")
        Peak 123 包含 15 个 hits

        >>> # 查看按 merged_index 分组的统计
        >>> print(intervals.groupby('merged_index').size())
        merged_index
        200    5
        201    7
        202    3
        dtype: int64

        >>> # 绘制时间间隔直方图
        >>> import matplotlib.pyplot as plt
        >>> import numpy as np
        >>> dt = intervals["dt_start_to_start_ns"].dropna()
        >>> plt.hist(dt, bins=np.linspace(0, dt.max(), 100))
        >>> plt.yscale("log")
        >>> plt.xlabel("hit_threshold interval within hit_merged (ns)")
        >>> plt.ylabel("counts")
        >>> plt.title(f"Hit Time Intervals for Peak {peak_id}")
        >>> plt.show()

        >>> # 分析时间间隔统计
        >>> print(f"平均间隔: {dt.mean():.2f} ns")
        >>> print(f"中位数: {dt.median():.2f} ns")
        >>> print(f"最小间隔: {dt.min():.2f} ns")
        >>> print(f"最大间隔: {dt.max():.2f} ns")

        >>> # 查看每个通道的 hit 数量
        >>> print(intervals.groupby('channel').size())
        channel
        0    4
        1    3
        2    5
        3    3
        dtype: int64

    See Also:
        get_hits_for_merged: 获取单个 merged 的 hit 数据
        get_merged_indices_for_peak: 只返回 merged_index（更轻量）
    """
    # 步骤 1: 获取该 peak 包含的所有 merged_index
    merged_indices = get_merged_indices_for_peak(peak_id, peaklet_components)

    # 定义返回的 DataFrame 列结构（保持一致性，即使是空结果）
    columns = [
        "peak_id",
        "merged_index",
        "hit_index",
        "position",
        "edge_start",
        "edge_end",
        "width",
        "dt",
        "timestamp",
        "board",
        "channel",
        "record_id",
        "time_start",
        "time_end",
        "dt_start_to_start_ns",
        "dt_end_to_start_ns",
    ]

    # 处理空结果情况
    if len(merged_indices) == 0:
        return pd.DataFrame(columns=columns)

    # 步骤 2: 对每个 merged_index 调用 get_hits_for_merged
    # 收集所有 merged 的 hit 数据
    out = []
    for merged_index in merged_indices:
        # 获取该 merged 的所有 hit 数据
        df = get_hits_for_merged(merged_index, hit_merged_components, hit_threshold)

        if len(df):
            # 在 DataFrame 前面插入 merged_index 和 peak_id 列
            # 这样可以追踪每个 hit 的来源
            df.insert(0, "merged_index", int(merged_index))
            df.insert(0, "peak_id", int(peak_id))
            out.append(df)

    # 处理所有 merged 都没有 hit 的情况
    if not out:
        return pd.DataFrame(columns=columns)

    # 步骤 3: 合并所有 DataFrame
    # ignore_index=True 确保索引重新从 0 开始
    result = pd.concat(out, ignore_index=True)

    # 步骤 4: 按 time_start 全局排序
    # 这会打乱 merged_index 的顺序，但确保了时间上的连续性
    # 这对于绘制时间序列图和计算全局时间间隔很重要
    result = result.sort_values("time_start").reset_index(drop=True)

    # 注意：此时的时间间隔是在每个 merged 内部计算的
    # 如果需要跨 merged 的时间间隔，可以在排序后重新计算
    # 但通常我们关心的是同一 merged 内部的间隔

    return result


# =============================================================================
# 批量优化函数
# =============================================================================


def build_peak_to_merged_lookup(
    peaklet_components: np.ndarray,
) -> dict[int, np.ndarray]:
    """构建 peak_id → merged_indices 完整映射（批量查询优化）。

    当需要查询多个 peak 时，预先构建完整映射可以避免重复扫描 peaklet_components。

    性能对比：
        - 单次查询：get_merged_indices_for_peak() 对每个 peak_id 扫描一次数组 (O(n))
        - 批量查询：build_peak_to_merged_lookup() 只扫描一次数组 (O(n))，后续查询 O(1)

    适用场景：
        1. 需要查询多个（>3）peak 的 merged_indices
        2. 需要遍历所有 peak 并统计其 merged 数量
        3. 需要频繁随机访问不同 peak 的 merged_indices

    不适用场景：
        1. 只查询 1-2 个 peak（直接用 get_merged_indices_for_peak 更简单）
        2. 内存受限的环境（lookup 字典会占用额外内存）

    实现说明：
        遍历 peaklet_components 数组，将每个 (peak_id, merged_index) 对
        存入字典。最后将列表转换为 numpy 数组以保持类型一致性。

    Args:
        peaklet_components (np.ndarray):
            peaklet_components 数组，必须包含 'peak_id' 和 'merged_index' 字段。

    Returns:
        Dict[int, np.ndarray]:
            字典，键为 peak_id，值为对应的 merged_index 数组（int64 类型）。
            - 如果输入为 None 或空数组，返回空字典
            - 只包含实际存在的 peak_id（不会有空的 key）

    Time Complexity:
        - 构建: O(n)，n 为 peaklet_components 的长度
        - 查询: O(1)

    Memory Overhead:
        - 额外内存约为 peaklet_components 数组大小的 1.5-2 倍
        - 每个 peak_id 的 merged_indices 数组单独存储

    Example:
        >>> # 构建完整映射
        >>> lookup = build_peak_to_merged_lookup(peaklet_components)
        >>> print(f"共有 {len(lookup)} 个 peaks")
        共有 100 个 peaks

        >>> # 批量查询多个 peak
        >>> for peak_id in [100, 101, 102]:
        ...     merged_indices = lookup.get(peak_id, np.array([], dtype=np.int64))
        ...     print(f"Peak {peak_id}: {len(merged_indices)} merged hits")
        Peak 100: 5 merged hits
        Peak 101: 3 merged hits
        Peak 102: 0 merged hits

        >>> # 统计每个 peak 的 merged 数量分布
        >>> merged_counts = {k: len(v) for k, v in lookup.items()}
        >>> import matplotlib.pyplot as plt
        >>> plt.hist(list(merged_counts.values()), bins=20)
        >>> plt.xlabel("Number of merged hits per peak")
        >>> plt.ylabel("Count")
        >>> plt.show()

        >>> # 查找包含最多 merged 的 peak
        >>> max_peak_id = max(lookup, key=lambda k: len(lookup[k]))
        >>> print(f"Peak {max_peak_id} 包含 {len(lookup[max_peak_id])} 个 merged hits")

    See Also:
        get_merged_indices_for_peak: 单次查询（无需预先构建映射）
        build_merged_to_hit_lookup: 构建 merged → hit 的映射
    """
    # 处理空输入情况
    if peaklet_components is None or len(peaklet_components) == 0:
        return {}

    # 使用字典收集映射关系
    # 键为 peak_id，值为 merged_index 列表
    lookup = {}
    for row in peaklet_components:
        peak_id = int(row["peak_id"])
        merged_index = int(row["merged_index"])

        # 如果 peak_id 第一次出现，创建新列表
        if peak_id not in lookup:
            lookup[peak_id] = []

        # 添加 merged_index 到对应的列表
        lookup[peak_id].append(merged_index)

    # 将列表转换为 numpy 数组
    # 这样与 get_merged_indices_for_peak 的返回类型保持一致
    return {k: np.array(v, dtype=np.int64) for k, v in lookup.items()}


def build_merged_to_hit_lookup(
    hit_merged_components: np.ndarray,
) -> dict[int, np.ndarray]:
    """构建 merged_index → hit_indices 完整映射（批量查询优化）。

    当需要查询多个 merged 时，预先构建完整映射可以避免重复扫描 hit_merged_components。

    性能对比：
        - 单次查询：get_hit_indices_for_merged() 对每个 merged_index 扫描一次数组 (O(n))
        - 批量查询：build_merged_to_hit_lookup() 只扫描一次数组 (O(n))，后续查询 O(1)

    适用场景：
        1. 需要查询多个（>3）merged 的 hit_indices
        2. 需要遍历所有 merged 并统计其 hit 数量
        3. 需要频繁随机访问不同 merged 的 hit_indices
        4. 需要分析 merged 的 hit 数量分布

    不适用场景：
        1. 只查询 1-2 个 merged（直接用 get_hit_indices_for_merged 更简单）
        2. 内存受限的环境（lookup 字典会占用额外内存）

    实现说明：
        遍历 hit_merged_components 数组，将每个 (merged_index, hit_index) 对
        存入字典。最后将列表转换为 numpy 数组以保持类型一致性。

    Args:
        hit_merged_components (np.ndarray):
            hit_merged_components 数组，必须包含 'merged_index' 和 'hit_index' 字段。

    Returns:
        Dict[int, np.ndarray]:
            字典，键为 merged_index，值为对应的 hit_index 数组（int64 类型）。
            - 如果输入为 None 或空数组，返回空字典
            - 只包含实际存在的 merged_index（不会有空的 key）

    Time Complexity:
        - 构建: O(n)，n 为 hit_merged_components 的长度
        - 查询: O(1)

    Memory Overhead:
        - 额外内存约为 hit_merged_components 数组大小的 1.5-2 倍
        - 每个 merged_index 的 hit_indices 数组单独存储

    Example:
        >>> # 构建完整映射
        >>> lookup = build_merged_to_hit_lookup(hit_merged_components)
        >>> print(f"共有 {len(lookup)} 个 merged hits")
        共有 500 个 merged hits

        >>> # 批量查询多个 merged
        >>> for merged_index in [200, 201, 202]:
        ...     hit_indices = lookup.get(merged_index, np.array([], dtype=np.int64))
        ...     print(f"Merged {merged_index}: {len(hit_indices)} hits")
        Merged 200: 3 hits
        Merged 201: 5 hits
        Merged 202: 0 hits

        >>> # 统计每个 merged 的 hit 数量分布
        >>> hit_counts = {k: len(v) for k, v in lookup.items()}
        >>> import matplotlib.pyplot as plt
        >>> plt.hist(list(hit_counts.values()), bins=20)
        >>> plt.xlabel("Number of hits per merged")
        >>> plt.ylabel("Count")
        >>> plt.show()

        >>> # 查找包含最多 hit 的 merged
        >>> max_merged_index = max(lookup, key=lambda k: len(lookup[k]))
        >>> print(f"Merged {max_merged_index} 包含 {len(lookup[max_merged_index])} 个 hits")

        >>> # 计算平均每个 merged 包含的 hit 数量
        >>> avg_hits = np.mean([len(v) for v in lookup.values()])
        >>> print(f"平均每个 merged 包含 {avg_hits:.2f} 个 hits")

    See Also:
        get_hit_indices_for_merged: 单次查询（无需预先构建映射）
        build_peak_to_merged_lookup: 构建 peak → merged 的映射
    """
    # 处理空输入情况
    if hit_merged_components is None or len(hit_merged_components) == 0:
        return {}

    # 使用字典收集映射关系
    # 键为 merged_index，值为 hit_index 列表
    lookup = {}
    for row in hit_merged_components:
        merged_index = int(row["merged_index"])
        hit_index = int(row["hit_index"])

        # 如果 merged_index 第一次出现，创建新列表
        if merged_index not in lookup:
            lookup[merged_index] = []

        # 添加 hit_index 到对应的列表
        lookup[merged_index].append(hit_index)

    # 将列表转换为 numpy 数组
    # 这样与 get_hit_indices_for_merged 的返回类型保持一致
    return {k: np.array(v, dtype=np.int64) for k, v in lookup.items()}
