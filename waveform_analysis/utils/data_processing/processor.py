import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

"""
完成数据的预处理
1. waveform ==> df
2. df ==> df_events
3. channels mask & group mask 两种

模块结构：
- WaveformStruct: 波形结构化处理
- build_waveform_df: 构建基础 DataFrame
- group_multi_channel_hits: 按时间窗口聚类事件
- WaveformDataset: 统一的数据容器和处理流程（支持链式调用）
- ResultData: 从缓存加载数据
"""


from .wavestruct import PEAK_DTYPE, WaveformStruct


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
    # We'll calculate area, height, width later if needed, or just return the bounds

    # For area and height, we need to loop or use advanced indexing
    # Since hits can have different lengths, full vectorization of area is tricky
    # but we can do it per-hit or using some tricks.
    # For now, let's just store the bounds and basic info.

    for i in range(n_hits):
        ev_idx = event_indices[i]
        s_start = max(0, s_starts[i] - left_extension)
        s_end = min(waves.shape[1], s_ends[i] + right_extension)

        hit_wave = signal[ev_idx, s_start:s_end]
        hits[i]["area"] = np.sum(hit_wave)
        hits[i]["height"] = np.max(hit_wave)
        hits[i]["width"] = s_end - s_start
        hits[i]["time"] = s_start

    return hits


def build_waveform_df(
    st_waveforms,
    peaks,
    charges,
    event_len,
    n_channels=6,
    peak_max_min=None,
    peak_baseline=None,
):
    """把每个通道的 timestamp / charge / peak / channel 拼成一个 DataFrame。

    新增：
        - peak_max_min: 最大值减最小值的峰值（与历史 peak 含义一致，默认等于 peaks）
        - peak_baseline: 基于 baseline 的峰值（baseline - 窗口最小值），默认等于 peaks
    """
    all_timestamps = []
    all_charges = []
    all_peaks = []
    all_peaks_mm = []
    all_peaks_base = []
    all_channels = []

    # 回退到原 peak 数组以保持兼容
    peak_max_min = peak_max_min if peak_max_min is not None else peaks
    peak_baseline = peak_baseline if peak_baseline is not None else peaks

    for ch in range(n_channels):
        n = event_len[ch]
        ts = np.asarray(st_waveforms[ch]["timestamp"][:n])
        qs = np.asarray(charges[ch][:n])
        ps = np.asarray(peaks[ch][:n])
        ps_mm = np.asarray(peak_max_min[ch][:n])
        ps_base = np.asarray(peak_baseline[ch][:n])

        all_timestamps.append(ts)
        all_charges.append(qs)
        all_peaks.append(ps)
        all_peaks_mm.append(ps_mm)
        all_peaks_base.append(ps_base)
        all_channels.append(np.full_like(ts, ch, dtype=int))

    all_timestamps = np.concatenate(all_timestamps)
    all_charges = np.concatenate(all_charges)
    all_peaks = np.concatenate(all_peaks)
    all_peaks_mm = np.concatenate(all_peaks_mm)
    all_peaks_base = np.concatenate(all_peaks_base)
    all_channels = np.concatenate(all_channels)

    return pd.DataFrame({
        "timestamp": all_timestamps,
        "charge": all_charges,
        "peak": all_peaks,  # 保持历史列名
        "peak_max_min": all_peaks_mm,
        "peak_baseline": all_peaks_base,
        "channel": all_channels,
    })


def group_multi_channel_hits(df, time_window_ns, show_progress: bool = False):
    """
    在 df 中按 timestamp 聚类，找“同一事件的多通道触发”，并在簇内部
    按 channel 从小到大对 (channels, charges, peaks, timestamps) 同步排序。
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

    # 聚类：使用向量化预筛选 + 优化循环
    # 找出所有可能成为簇起始点的索引（与前一个点差距大于 window）
    # 注意：这与“相对于簇首点”逻辑略有不同，但在稀疏数据下一致。
    # 为了保持逻辑完全一致，我们使用一个优化的循环。

    cluster_starts = [0]
    if n > 0:
        t0 = ts_all[0]
        for i in range(1, n):
            if ts_all[i] - t0 > time_window_ps:
                cluster_starts.append(i)
                t0 = ts_all[i]
    cluster_starts.append(n)

    # 整理成 records，并在簇内部按 channel 排序
    records = []

    # Optional progress bar for record processing
    if show_progress:
        try:
            from tqdm import tqdm

            pbar_clusters = tqdm(range(len(cluster_starts) - 1), desc="Processing clusters", leave=False)
        except ImportError:
            pbar_clusters = range(len(cluster_starts) - 1)
    else:
        pbar_clusters = range(len(cluster_starts) - 1)

    for i in pbar_clusters:
        start_idx = cluster_starts[i]
        end_idx = cluster_starts[i + 1]

        ts = ts_all[start_idx:end_idx]
        chs = ch_all[start_idx:end_idx]
        qs = q_all[start_idx:end_idx]
        ps = p_all[start_idx:end_idx]

        # 按 channel 从小到大排序
        sort_idx = np.argsort(chs.astype(int))
        chs_sorted = chs[sort_idx]
        qs_sorted = qs[sort_idx]
        ps_sorted = ps[sort_idx]
        ts_sorted = ts[sort_idx]

        records.append({
            "event_id": i,
            "t_min": ts_sorted[0],  # 已排序
            "t_max": ts_sorted[-1] if len(ts_sorted) > 1 else ts_sorted[0],
            "dt/ns": (ts_sorted.max() - ts_sorted.min()) / 1e3,  # 转换为 ns
            "n_hits": len(ts_sorted),
            "channels": chs_sorted,
            "charges": qs_sorted,
            "peaks": ps_sorted,
            "timestamps": ts_sorted,
        })

    return pd.DataFrame(records)


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


def encode_groups_binary(channels):
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


def encode_channels_binary(channels):
    """
    将 channel 列表转换为二进制位掩码。
    例如 [0,3,5] → 1<<0 | 1<<3 | 1<<5 = 41
    """
    if not channels:
        return 0

    mask = 0
    for ch in channels:
        mask |= 1 << int(ch)

    return mask


def mask_to_channels(mask):
    """
    将 bitmask 转回 channel 列表。
    例如 41 (0b101001) → [0,3,5]
    """
    if mask is None or mask == 0:
        return []

    channels = []
    bit_pos = 0
    while mask > 0:
        if mask & 1:
            channels.append(bit_pos)
        mask >>= 1
        bit_pos += 1
    return channels


def channels_to_mask(channels):
    """
    将 channels 列表转换为 bitmask。
    例如 [0,3,5] → 41 (二进制 0b101001)
    """
    if not channels:
        return 0

    mask = 0
    for ch in channels:
        mask |= 1 << int(ch)
    return mask


def get_paired_data(df_events, group_mask, char):
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


def energy_rec(data):
    x, y = data
    energy = np.sqrt(np.prod([x, y], axis=0)) * 2
    return energy


def lr_log_ratio(data):
    x, y = data
    log_ratio = np.log(x) - np.log(y)
    return log_ratio


class ResultData:
    def __init__(self, cache_dir) -> None:
        self.cache_dir = cache_dir
        df_file = os.path.join(cache_dir, "df.feather")
        event_file = os.path.join(cache_dir, "df_events.feather")

        self.df = pd.read_feather(df_file)
        self.df_events = pd.read_feather(event_file)


def hist_count_ratio(data_a, data_b, bins):
    counts_a, bin_edges = np.histogram(data_a, bins=bins)
    counts_b, _ = np.histogram(data_b, bins=bins)
    ratio = np.divide(
        counts_a,
        counts_b,
        out=np.zeros_like(counts_a, dtype=float),
        where=counts_b > 0,
    )
    return bin_edges, counts_a, counts_b, ratio
