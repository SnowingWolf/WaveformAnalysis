"""
Processor 模块 - 波形信号处理与特征提取核心逻辑。

本模块负责将原始 DAQ 采集的 NumPy 数组转换为结构化数据，并执行物理特征提取。
核心功能包括：
1. **数据结构化**：定义 `RECORD_DTYPE` (波形+元数据) 与 `PEAK_DTYPE` (脉冲特征)。
2. **特征提取**：提供 `find_hits` (向量化寻峰)、基线扣除、电荷积分 (Charge) 与幅度 (Peak) 计算。
3. **链式处理**：通过 `WaveformStruct` 维护波形结构化逻辑，支持 `WaveformDataset` 的链式调用。
4. **事件聚类**：`group_multi_channel_hits` 基于时间窗口将多通道 Hit 聚类为物理事件。
5. **通道编码**：提供二进制掩码 (Bitmask) 与权重编码工具，用于多通道符合逻辑筛选。

主要类说明：
- `WaveformStruct`: 处理原始数组到结构化 `RECORD_DTYPE` 的转换，管理时间戳索引与配对长度。
- `WaveformProcessor`: 高层封装接口，支持批量处理数据块 (Chunks) 并构建 Pandas DataFrame。
"""

import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from waveform_analysis.core.utils import exporter
from waveform_analysis.core.executor_manager import get_executor

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
        ("timestamp", "i8"),  # int64 for ps-level timestamps
        ("event_length", "i8"),  # length of the event
        ("wave", "f4", (DEFAULT_WAVE_LENGTH,)),  # fixed length array for performance
    ],
    name="RECORD_DTYPE",
)

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
class WaveformStruct:
    def __init__(self, waveforms: List[np.ndarray]):
        """
        初始化 WaveformStruct。
        Args:
            waveforms: List of NumPy arrays, each array corresponds to a channel's raw waveforms.
        """
        self.waveforms = waveforms
        self.event_length = None
        self.waveform_structureds = None

    def _structure_waveform(self, waves: Optional[np.ndarray] = None) -> np.ndarray:
        # If no explicit waves passed, use the first channel
        if waves is None:
            if not self.waveforms:
                return np.zeros(0, dtype=RECORD_DTYPE)
            waves = self.waveforms[0]

        # If waves is empty, return an empty structured array
        if len(waves) == 0:
            return np.zeros(0, dtype=RECORD_DTYPE)

        waveform_structured = np.zeros(len(waves), dtype=RECORD_DTYPE)

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

        # Vectorized assignment for fixed-length wave
        wave_data = waves[:, 7:]
        n_samples = min(wave_data.shape[1], DEFAULT_WAVE_LENGTH)
        waveform_structured["wave"][:, :n_samples] = wave_data[:, :n_samples]

        return waveform_structured

    def structure_waveforms(self, show_progress: bool = False) -> List[np.ndarray]:
        if show_progress:
            try:
                from tqdm import tqdm

                pbar = tqdm(self.waveforms, desc="Structuring waveforms", leave=False)
            except ImportError:
                pbar = self.waveforms
        else:
            pbar = self.waveforms

        self.waveform_structureds = [self._structure_waveform(waves) for waves in pbar]
        return self.waveform_structureds

    def get_event_length(self) -> np.ndarray:
        """Compute per-event event lengths.

        Adjacent channels are considered an event pair when computing the minimal length.
        """
        raw_lengths = np.array([len(wave) for wave in self.waveforms])

        # 重塑为 (n_pairs, 2) 的形状进行处理
        n = len(raw_lengths)
        if n % 2 == 0:
            # 偶数个元素
            reshaped = raw_lengths.reshape(-1, 2)
            min_vals = np.min(reshaped, axis=1)
            self.event_length = np.repeat(min_vals, 2)
        else:
            # 奇数个元素，最后一个单独处理
            if n > 1:
                reshaped = raw_lengths[:-1].reshape(-1, 2)
                min_vals = np.min(reshaped, axis=1)
                self.event_length = np.concatenate([np.repeat(min_vals, 2), [raw_lengths[-1]]])
            else:
                self.event_length = raw_lengths

        return self.event_length


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

    def get_event_length(self, waveforms: List[np.ndarray]) -> np.ndarray:
        """
        获取各通道波形的配对长度。
        """
        structurer = WaveformStruct(waveforms)
        return structurer.get_event_length()

    def compute_basic_features(
        self,
        st_waveforms: List[np.ndarray],
        event_len: np.ndarray,
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

        peaks = []
        charges = []

        for i in range(len(st_waveforms)):
            st_ch = st_waveforms[i]
            n = event_len[i]
            if len(st_ch) == 0 or n == 0:
                peaks.append(np.zeros(0))
                charges.append(np.zeros(0))
                continue

            # Vectorized peak calculation
            # st_ch["wave"] is (N, DEFAULT_WAVE_LENGTH)
            waves_p = st_ch["wave"][:n, start_p:end_p]
            p_vals = np.max(waves_p, axis=1) - np.min(waves_p, axis=1)
            peaks.append(p_vals)

            # Vectorized charge calculation
            waves_c = st_ch["wave"][:n, start_c:end_c]
            baselines = st_ch["baseline"][:n]
            # baseline - wave, then sum over samples
            q_vals = np.sum(baselines[:, np.newaxis] - waves_c, axis=1)
            charges.append(q_vals)

        return peaks, charges

    def build_dataframe(
        self,
        st_waveforms: List[np.ndarray],
        peaks: List[np.ndarray],
        charges: List[np.ndarray],
        event_len: np.ndarray,
        extra_features: Optional[Dict[str, List[np.ndarray]]] = None,
    ) -> pd.DataFrame:
        """
        构建波形 DataFrame。
        """
        df = build_waveform_df(st_waveforms, peaks, charges, event_len, n_channels=self.n_channels)

        if extra_features:
            for name, feat_list in extra_features.items():
                all_feat = np.concatenate([feat[: event_len[i]] for i, feat in enumerate(feat_list)])
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
def build_waveform_df(
    st_waveforms: List[np.ndarray],
    peaks: List[np.ndarray],
    charges: List[np.ndarray],
    event_len: np.ndarray,
    n_channels: int = 6,
) -> pd.DataFrame:
    """把每个通道的 timestamp / charge / peak / channel 拼成一个 DataFrame."""
    all_timestamps = []
    all_charges = []
    all_peaks = []
    all_channels = []

    for ch in range(n_channels):
        n = event_len[ch]
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
        time_window_ns: 时间窗口（纳秒）
        use_numba: 是否使用numba加速（默认True，如果numba可用）
        n_processes: 多进程数量（None=单进程，>1=多进程，默认None）
    
    性能优化:
        - 使用numba JIT编译加速边界查找（如果可用）
        - 支持多进程并行处理事件簇（适用于超大数据集）
        - 优化DataFrame构建方式
        - 减少不必要的数组复制
    
    示例:
        # 使用numba加速（单进程）
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
                except Exception as e:
                    print(f"处理块时出错: {e}")
                    # 回退到单进程处理该块
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
            "channels": chs_sorted.copy(),  # 确保是独立的数组
            "charges": qs_sorted.copy(),
            "peaks": ps_sorted.copy(),
            "timestamps": ts_sorted.copy(),
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
