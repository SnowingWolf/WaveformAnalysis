import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from waveform_analysis.core.utils import exporter

# 初始化 exporter
export, __all__ = exporter()


@export
class WaveformStruct:
    def __init__(self, waveforms):
        self.waveforms = waveforms
        self.pair_length = None
        self.waveform_structureds = None

    def _structure_waveform(self, waves=None):
        # If no explicit waves passed, use the first channel
        if waves is None:
            if not self.waveforms:
                return np.zeros(
                    0, dtype=[("baseline", "f8"), ("timestamp", "i8"), ("pair_length", "i8"), ("wave", "O")]
                )
            waves = self.waveforms[0]

        # If waves is empty, return an empty structured array
        if len(waves) == 0:
            return np.zeros(0, dtype=[("baseline", "f8"), ("timestamp", "i8"), ("pair_length", "i8"), ("wave", "O")])

        waveform_structured = np.zeros(
            len(waves),
            dtype=[
                ("baseline", "f8"),
                ("timestamp", "i8"),
                ("pair_length", "i8"),
                ("wave", "O"),
            ],
        )

        # Safely compute baseline and timestamp
        try:
            baseline_vals = np.mean(waves[:, 7:47].astype(float), axis=1)
        except Exception:
            # Fallback: compute per-row mean for rows that have enough samples
            baselines = []
            for row in waves:
                try:
                    vals = np.asarray(row[7:], dtype=float)
                    if vals.size > 0:
                        baselines.append(np.mean(vals))
                    else:
                        baselines.append(np.nan)
                except Exception:
                    baselines.append(np.nan)
            baseline_vals = np.array(baselines, dtype=float)

        try:
            timestamps = waves[:, 2].astype(np.int64)
        except Exception:
            # Fallback: extract element 2 from each row
            timestamps = np.array([int(row[2]) for row in waves], dtype=np.int64)

        waveform_structured["baseline"] = baseline_vals
        waveform_structured["timestamp"] = timestamps
        waveform_structured["wave"] = [row[7:] for row in waves]
        return waveform_structured

    def structure_waveforms(self):
        self.waveform_structureds = [self._structure_waveform(waves) for waves in self.waveforms]
        return self.waveform_structureds

    def get_pair_length(self):
        pair_length = np.array([len(wave) for wave in self.waveforms])

        # 重塑为 (n_pairs, 2) 的形状进行处理
        n = len(pair_length)
        if n % 2 == 0:
            # 偶数个元素
            reshaped = pair_length.reshape(-1, 2)
            min_vals = np.min(reshaped, axis=1)
            paired_length = np.repeat(min_vals, 2)
        else:
            reshaped = pair_length[:-1].reshape(-1, 2)
            min_vals = np.min(reshaped, axis=1)
            paired_length = np.concatenate([np.repeat(min_vals, 2), [pair_length[-1]]])

        self.pair_length = paired_length
        return paired_length


@export
class WaveformProcessor:
    """
    负责波形处理、特征提取和 DataFrame 构建。
    """

    def __init__(self, n_channels: int = 2):
        self.n_channels = n_channels
        self.peaks_range = (40, 90)
        self.charge_range = (60, 400)
        self.feature_fns: Dict[str, Tuple[Callable[..., List[np.ndarray]], Dict[str, Any]]] = {}

    def structure_waveforms(self, waveforms: List[np.ndarray]) -> List[np.ndarray]:
        """
        将原始波形数组转换为结构化数组。
        """
        structurer = WaveformStruct(waveforms)
        return structurer.structure_waveforms()

    def get_pair_length(self, waveforms: List[np.ndarray]) -> np.ndarray:
        """
        获取各通道波形的配对长度。
        """
        structurer = WaveformStruct(waveforms)
        return structurer.get_pair_length()

    def compute_basic_features(
        self,
        st_waveforms: List[np.ndarray],
        pair_len: np.ndarray,
        peaks_range: Optional[Tuple[int, int]] = None,
        charge_range: Optional[Tuple[int, int]] = None,
    ) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        计算基础特征：peaks 和 charges。
        """
        if peaks_range is not None:
            self.peaks_range = peaks_range
        if charge_range is not None:
            self.charge_range = charge_range

        start_p, end_p = self.peaks_range
        start_c, end_c = self.charge_range

        peaks = [
            np.array([
                np.max(wave["wave"][start_p:end_p]) - np.min(wave["wave"][start_p:end_p]) for wave in st_waveforms[i]
            ])[: pair_len[i]]
            for i in range(len(st_waveforms))
        ]

        charges = [
            np.array([np.sum(wave["baseline"] - wave["wave"][start_c:end_c]) for wave in st_waveforms[i]])[
                : pair_len[i]
            ]
            for i in range(len(st_waveforms))
        ]

        return peaks, charges

    def build_dataframe(
        self,
        st_waveforms: List[np.ndarray],
        peaks: List[np.ndarray],
        charges: List[np.ndarray],
        pair_len: np.ndarray,
        extra_features: Optional[Dict[str, List[np.ndarray]]] = None,
    ) -> pd.DataFrame:
        """
        构建波形 DataFrame。
        """
        df = build_waveform_df(st_waveforms, peaks, charges, pair_len, n_channels=self.n_channels)

        if extra_features:
            for name, feat_list in extra_features.items():
                all_feat = np.concatenate([feat[: pair_len[i]] for i, feat in enumerate(feat_list)])
                df[name] = all_feat

        return df.sort_values("timestamp")

    def process_chunk(
        self, chunk: np.ndarray, peaks_range: Tuple[int, int], charge_range: Tuple[int, int]
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
            "event_length": np.full(len(ts), waves.shape[1]),
        }


@export
def build_waveform_df(st_waveforms, peaks, charges, pair_len, n_channels=6):
    """把每个通道的 timestamp / charge / peak / channel 拼成一个 DataFrame."""
    all_timestamps = []
    all_charges = []
    all_peaks = []
    all_channels = []

    for ch in range(n_channels):
        n = pair_len[ch]
        # 如果 timestamp 是 1D（每个事件一个值），这行是 OK 的；
        # 如果是 2D（事件 × 采样点），可以改成 .mean(axis=1) 或 [:, 0]
        ts = np.asarray(st_waveforms[ch]["timestamp"][:n])
        qs = np.asarray(charges[ch][:n])
        ps = np.asarray(peaks[ch][:n])

        all_timestamps.append(ts)
        all_charges.append(qs)
        all_peaks.append(ps)
        all_channels.append(np.full_like(ts, ch, dtype=int))

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
def group_multi_channel_hits(df, time_window_ns):
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

    # 聚类：clusters 保存的是“索引列表”
    clusters = []
    current_idx = [0]

    for i in range(1, n):
        t0 = ts_all[current_idx[0]]
        if ts_all[i] - t0 > time_window_ps:
            clusters.append(current_idx)
            current_idx = [i]
        else:
            current_idx.append(i)

    if current_idx:
        clusters.append(current_idx)

    # 整理成 records，并在簇内部按 channel 排序
    records = []
    for event_id, idx_list in enumerate(clusters):
        idx_arr = np.asarray(idx_list, dtype=int)

        ts = ts_all[idx_arr]
        chs = ch_all[idx_arr]
        qs = q_all[idx_arr]
        ps = p_all[idx_arr]

        # 按 channel 从小到大排序
        sort_idx = np.argsort(chs.astype(int))
        chs_sorted = chs[sort_idx]
        qs_sorted = qs[sort_idx]
        ps_sorted = ps[sort_idx]
        ts_sorted = ts[sort_idx]

        records.append({
            "event_id": event_id,
            "t_min": ts_sorted.min(),
            "t_max": ts_sorted.max(),
            "dt/ns": ts_sorted.max() - ts_sorted.min(),
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


@export
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


@export
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


@export
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


@export
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


@export
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


@export
def energy_rec(data):
    x, y = data
    energy = np.sqrt(np.prod([x, y], axis=0)) * 2
    return energy


@export
def lr_log_ratio(data):
    x, y = data
    log_ratio = np.log(x) - np.log(y)
    return log_ratio


@export
class ResultData:
    def __init__(self, cache_dir) -> None:
        self.cache_dir = cache_dir
        df_file = os.path.join(cache_dir, "df.feather")
        event_file = os.path.join(cache_dir, "df_events.feather")

        self.df = pd.read_feather(df_file)
        self.df_events = pd.read_feather(event_file)


@export
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
