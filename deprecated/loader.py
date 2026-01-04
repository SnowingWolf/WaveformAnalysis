import bisect
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class RawFileLoader:
    """Efficient loader for DAQ waveform files with channel-aware grouping."""

    # **预编译正则**减少重复 cost
    _ch_re = re.compile(r"CH(\d+)")
    _idx_re = re.compile(r"_(\d+)\.CSV$", re.IGNORECASE)

    def __init__(self, n_channels: int = 6, char: str = "All_SelfTrigger"):
        self.base_dir = Path(f"./DAQ/{char}/RAW")
        self.n_channels = n_channels
        self.pattern = f"DataR_CH*@VX2730_53013_{char}*.CSV"

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

        for file in self.base_dir.glob(self.pattern):
            parsed = self._extract(file.name)
            if parsed is None:
                continue

            ch, idx = parsed
            if ch < self.n_channels:
                groups[ch].append((idx, str(file)))

        # Channels missing files get empty list
        return [[fp for _, fp in sorted(groups.get(ch, []))] for ch in range(self.n_channels)]


def get_raw_files(n_channels=6, char="All_SelfTrigger"):
    return RawFileLoader(n_channels, char).get_raw_files()


def get_waveforms(raw_filess: List[List[str]]):
    """将所有 CSV 加载并拼接成 numpy 数组（fast mode）。"""
    waveforms = []
    for files in raw_filess:
        if not files:
            waveforms.append(np.array([]))
            continue

        arrs = []
        for f in files:
            try:
                # 检查文件是否为空
                if os.path.getsize(f) == 0:
                    print(f"Warning: {f} is empty, skipping")
                    continue
                # Ensure we read data rows (skip metadata+header lines). Use header=None so first data line is parsed as data
                df = pd.read_csv(f, delimiter=";", skiprows=2, header=None)
                # drop completely empty rows
                df.dropna(how="all", inplace=True)
                if df.empty:
                    print(f"Warning: {f} has no data after parsing, skipping")
                    continue

                # Coerce timestamp and sample columns to numeric types where possible
                # TIMETAG is expected at column index 2
                try:
                    df.iloc[:, 2:] = df.iloc[:, 2:].apply(pd.to_numeric, errors="coerce")
                    # drop rows with no valid timestamp
                    df.dropna(subset=[2], inplace=True)
                except Exception:
                    # best-effort conversion, but if it fails, continue with original df
                    pass

                if df.empty:
                    print(f"Warning: {f} has no numeric data after parsing, skipping")
                    continue

                arr = df.to_numpy()
                arrs.append(arr)
            except pd.errors.EmptyDataError:
                print(f"Warning: {f} has no columns to parse, skipping")
                continue

        if not arrs:
            waveforms.append(np.array([]))
        else:
            waveforms.append(np.vstack(arrs))
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
