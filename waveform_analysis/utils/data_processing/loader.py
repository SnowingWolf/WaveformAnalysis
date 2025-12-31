import bisect
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from waveform_analysis.utils.daq import adapt_daq_run


class RawFileLoader:
    """Efficient loader for DAQ waveform files with channel-aware grouping."""

    # **预编译正则**减少重复 cost
    _ch_re = re.compile(r"CH(\d+)")
    _idx_re = re.compile(r"_(\d+)\.CSV$", re.IGNORECASE)

    def __init__(self, n_channels: int = 6, char: str = "All_SelfTrigger", data_root: str = "DAQ"):
        self.base_dir = Path(data_root) / char / "RAW"
        self.n_channels = n_channels
        self.pattern = "*CH*.CSV"

    def _extract(self, filename: str) -> Optional[tuple[int, int]]:
        """一次解析文件名→返回 `(channel, file_index)`"""
        ch_match = self._ch_re.search(filename)
        if not ch_match:
            return None

        ch = int(ch_match.group(1))
        idx_match = self._idx_re.search(filename)
        file_idx = int(idx_match.group(1)) if idx_match else 0
        return ch, file_idx

    def get_raw_files(self) -> List[List[str]]:
        groups = defaultdict(list)
        print(f"DEBUG: Scanning {self.base_dir} with pattern {self.pattern}")
        for file in self.base_dir.glob(self.pattern):
            parsed = self._extract(file.name)
            if parsed is None:
                continue

            ch, idx = parsed
            if ch < self.n_channels:
                groups[ch].append((idx, str(file)))

        print(f"DEBUG: Found groups: {list(groups.keys())}")
        # Channels missing files get empty list
        return [[fp for _, fp in sorted(groups.get(ch, []))] for ch in range(self.n_channels)]


def get_raw_files(n_channels=6, char="All_SelfTrigger", daq_run=None, data_root="DAQ"):
    """返回每个通道的文件列表。

    参数:
        n_channels: 通道数
        char: 运行标识（用于按原始路径匹配）
        daq_run: 可选的 `DAQRun` 对象（来自 `waveform_analysis.utils.daq`），
                 若提供则用其文件列表替代基于文件系统的扫描。
        data_root: 数据根目录
    """
    if daq_run is not None:
        # 使用统一适配器以提供稳定的 get_channel_paths 接口
        adapted = adapt_daq_run(daq_run)
        return adapted.get_channel_paths(n_channels)

    return RawFileLoader(n_channels, char, data_root).get_raw_files()


def _build_raw_from_daq_run(daq_run, n_channels: int):
    """内部助手：从不同形式的 daq_run 结果构建 per-channel 文件列表。

    支持形式：
      - 对象，具有 `get_channel_paths(n_channels)` 方法（优先）
      - 对象，具有 `channel_files` 属性，格式为 {ch: [ {"path":..., "index":...}, ... ]}
      - 直接传入 dict {ch: [path, ...]} 或 {ch: [ {"path":...}, ... ]}
    """
    raw = [[] for _ in range(n_channels)]

    # 1) 优先使用对象方法 get_channel_paths
    if hasattr(daq_run, "get_channel_paths"):
        try:
            ch_paths = daq_run.get_channel_paths(n_channels)
            for ch in range(n_channels):
                files = ch_paths[ch] if ch < len(ch_paths) else []
                raw[ch] = [str(p) for p in files]
            return raw
        except Exception:
            # 如果方法不能按预期工作，回退到下面的逻辑
            pass

    # 2) 支持 channel_files 属性（旧格式）
    if hasattr(daq_run, "channel_files"):
        cf = getattr(daq_run, "channel_files")
        for ch in range(n_channels):
            entries = cf.get(ch, []) if isinstance(cf, dict) else []
            files = []
            for e in entries:
                if isinstance(e, dict):
                    files.append(str(e.get("path")))
                else:
                    files.append(str(e))
            raw[ch] = files
        return raw

    # 3) 如果传入的是 dict-like mapping ch->list
    if isinstance(daq_run, dict):
        for ch in range(n_channels):
            entries = daq_run.get(ch, [])
            files = []
            for e in entries:
                if isinstance(e, dict):
                    files.append(str(e.get("path")))
                else:
                    files.append(str(e))
            raw[ch] = files
        return raw

    # 4) 无法识别，返回空列表
    return raw


def get_waveforms_generator(
    raw_filess: Optional[List[List[str]]] = None,
    daq_run=None,
    n_channels: int = 6,
    chunksize: int = 1000,
    show_progress: bool = False,
):
    """
    Yields synchronized chunks of waveforms for all channels.
    Returns a generator of tuples/lists, where each element is a list of numpy arrays (one per channel).
    """
    from .io import parse_files_generator

    if raw_filess is None and daq_run is not None:
        adapted = adapt_daq_run(daq_run)
        raw_filess = adapted.get_channel_paths(n_channels)

    if raw_filess is None:
        raw_filess = [[] for _ in range(n_channels)]

    # Create generators for each channel
    # Only show progress for the first channel to avoid clutter
    gens = [
        parse_files_generator(files, chunksize=chunksize, show_progress=(show_progress and i == 0))
        for i, files in enumerate(raw_filess)
    ]
    print(f"DEBUG: get_waveforms_generator created {len(gens)} generators")

    # Zip them to yield synchronized chunks
    res = zip(*gens)
    print(f"DEBUG: get_waveforms_generator returning zip object")
    return res


def get_waveforms(
    raw_filess: Optional[List[List[str]]] = None,
    daq_run=None,
    n_channels: int = 6,
    show_progress: bool = False,
):
    """将所有 CSV 加载并拼接成 numpy 数组（fast mode）。

    参数:
        raw_filess: 可选的每通道文件路径列表
        daq_run: 可选的 DAQRun 结果（对象或 dict），优先用于构建文件列表
        n_channels: 通道数（当通过 daq_run 构建列表时需要）
        show_progress: 是否显示进度条

    说明: 现在 loader 支持直接接受 `daq_run` 的结果，避免在外部重复实现文件名收集逻辑。
    """
    from .io import parse_and_stack_files

    if raw_filess is None and daq_run is not None:
        adapted = adapt_daq_run(daq_run)
        raw_filess = adapted.get_channel_paths(n_channels)

    if raw_filess is None:
        raw_filess = [[] for _ in range(n_channels)]

    waveforms = []

    # Optional progress bar for channels
    if show_progress:
        try:
            from tqdm import tqdm

            pbar = tqdm(raw_filess, desc="Loading channels")
        except ImportError:
            pbar = raw_filess
    else:
        pbar = raw_filess

    for files in pbar:
        # Pass show_progress to parse_and_stack_files for nested bars if desired
        waveforms.append(parse_and_stack_files(files, show_progress=show_progress))
    return waveforms


def build_filetime_index(raw_filess):
    """建立基于文件 mtime 的快速查找表。"""
    indexed = []
    for ch_files in raw_filess:
        if not ch_files:
            indexed.append([])
            continue

        times = [(os.path.getmtime(f), f) for f in ch_files]
        times.sort()
        indexed.append(times)

    return indexed


def get_files_by_filetime(indexed_table, t_query_mtime):
    """
    使用二分查找（bisect），找到最接近的时间文件，比原实现更快。
    """
    result = {}

    for ch, entries in enumerate(indexed_table):
        if not entries:
            continue

        timestamps = [t for t, _ in entries]
        pos = bisect.bisect_left(timestamps, t_query_mtime)

        # 找到最接近值（检查 pos 和 pos-1）
        cand = []
        if pos < len(timestamps):
            cand.append((abs(timestamps[pos] - t_query_mtime), pos))
        if pos > 0:
            cand.append((abs(timestamps[pos - 1] - t_query_mtime), pos - 1))

        _, best = min(cand)
        result[ch] = entries[best][1]

    return result


# 示例：在 Notebook 中使用

import os
import time as _time


def get_files_before(raw_filess, files_by_time):
    sel_raw_filess = []
    for channel_idx, channel_files in enumerate(raw_filess):
        target_fp = files_by_time.get(channel_idx)
        if not target_fp:
            sel_raw_filess.append([])
            continue
        if target_fp in channel_files:
            matched_pos = channel_files.index(target_fp)
            sel_raw_filess.append(channel_files[: matched_pos + 1])
        else:
            sel_raw_filess.append([target_fp])
    return sel_raw_filess


if __name__ == "__main__":
    # 示例：在终端中运行此文件测试
    print("\n=== Test 2: Co60_R50 ===")
    raw_files_co60 = get_raw_files(n_channels=6, char="Co60_R50")
    print(f"Loaded {len(raw_files_co60)} channels")
    for ch, files in enumerate(raw_files_co60):
        if files:
            print(f"  CH{ch}: {len(files)} files")
            print(f"    First: {os.path.basename(files[0])}")

    raw_filess = raw_files_co60
    ref_fp = raw_filess[0][0]

    filetime_ranges = build_filetime_index(raw_filess)
    t_ref = os.path.getmtime(ref_fp)
    print("ref file:", ref_fp)
    print("mtime:", _time.ctime(t_ref))

    # 3) 找到在每个通道“时间最接近 t_ref”的文件
    files_by_time = get_files_by_filetime(filetime_ranges, t_ref)
    print("coarse matched files (by mtime):")
    for ch, fp in files_by_time.items():
        print(f"  CH{ch}: {fp}")

    sel_raw_filess = get_files_before(raw_filess, files_by_time)

    print(sel_raw_filess)
