# -*- coding: utf-8 -*-
"""
Loader 模块 - 原始数据加载与文件索引。

负责扫描 DAQ 目录、解析文件名中的时间戳、构建文件索引，
并提供高效的波形数据读取接口（支持单次读取和生成器流式读取）。
"""

import bisect
import os
import re
from collections import defaultdict
from concurrent.futures import as_completed
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

import numpy as np

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.utils.daq import adapt_daq_run

# 初始化 exporter
export, __all__ = exporter()


@export
class WaveformLoader:
    """
    高效的 DAQ 波形文件加载器，支持按通道分组。
    """

    # 预编译正则
    _ch_re = re.compile(r"CH(\d+)")
    _idx_re = re.compile(r"_(\d+)\.CSV$", re.IGNORECASE)

    def __init__(
        self,
        n_channels: int = 6,
        run_name: str = "All_SelfTrigger",
        data_root: str = "DAQ",
        **kwargs,
    ):
        """
        初始化波形加载器

        配置数据加载路径和通道数。

        Args:
            n_channels: 通道数量（默认6）
            run_name: 运行名称（默认 "All_SelfTrigger"）
            data_root: 数据根目录（默认 "DAQ"）
            **kwargs: 额外参数（如 char，用于向后兼容）

        初始化内容:
        - 数据目录路径: {data_root}/{run_name}/RAW
        - 文件匹配模式: *CH*.CSV
        - 通道数配置
        - 保留 char 属性以向后兼容
        """
        # 兼容旧的 char 参数
        if "char" in kwargs:
            run_name = kwargs.pop("char")

        self.base_dir = Path(data_root) / run_name / "RAW"
        self.n_channels = n_channels
        self.pattern = "*CH*.CSV"
        self.data_root = data_root
        self.run_name = run_name
        self.char = run_name  # 保持 char 属性以兼容旧代码

    def _extract(self, filename: str) -> Optional[Tuple[int, int]]:
        """解析文件名，返回 (channel, file_index)"""
        ch_match = self._ch_re.search(filename)
        if not ch_match:
            return None

        ch = int(ch_match.group(1))
        idx_match = self._idx_re.search(filename)
        file_idx = int(idx_match.group(1)) if idx_match else 0
        return ch, file_idx

    def get_raw_files(
        self, daq_run: Optional[Any] = None, daq_info: Optional[Dict] = None
    ) -> List[List[str]]:
        """
        获取每个通道的文件列表。支持直接从 DAQRun 对象、DAQ 报告 dict 或文件系统扫描。
        """
        # 1. 优先使用 DAQRun 对象
        if daq_run is not None:
            adapted = adapt_daq_run(daq_run)
            return adapted.get_channel_paths(self.n_channels)

        # 2. 其次使用 DAQ 报告信息
        if daq_info is not None:
            channel_details = daq_info.get("channel_details", {})
            run_path = daq_info.get("path", str(self.base_dir.parent.parent))

            # 确定通道数
            max_ch = max(
                [int(k) for k in channel_details.keys()] + [self.n_channels - 1]
            )
            raw_filess = [[] for _ in range(max_ch + 1)]

            for ch_str, chdata in channel_details.items():
                ch = int(ch_str)
                files = chdata.get("files", [])
                sorted_files = sorted(files, key=lambda x: x.get("index", 0))
                raw_filess[ch] = [
                    os.path.join(run_path, "RAW", f["filename"]) for f in sorted_files
                ]

            return raw_filess

        # 3. 最后回退到文件系统扫描
        groups = defaultdict(list)
        if not self.base_dir.exists():
            return [[] for _ in range(self.n_channels)]

        for file in self.base_dir.glob(self.pattern):
            parsed = self._extract(file.name)
            if parsed is None:
                continue

            ch, idx = parsed
            groups[ch].append((idx, str(file)))

        max_ch = max(list(groups.keys()) + [self.n_channels - 1])
        return [
            [fp for _, fp in sorted(groups.get(ch, []))] for ch in range(max_ch + 1)
        ]

    def load_waveforms(
        self,
        raw_filess: List[List[str]],
        show_progress: bool = False,
        chunksize: Optional[int] = None,
        n_jobs: int = 1,
        use_process_pool: bool = False,
        channel_workers: Optional[int] = None,
        channel_executor: str = "thread",
    ) -> List[np.ndarray]:
        """
        加载所有 CSV 文件并拼接成 numpy 数组。

        参数:
            raw_filess: 每个通道的文件列表。
            show_progress: 仅对第一个通道显示进度条。
            chunksize: 传递给 parse_and_stack_files 的分块大小。
            n_jobs: 通道内 CSV 解析的并行度（parse_and_stack_files 内部使用）。
            use_process_pool: 是否在单通道内使用进程池。
            channel_workers: **新增** 通道级并行度；>1 时为每个通道分配线程并行解析。
            channel_executor: 通道级并行的执行器类型，"thread" (默认) 或 "process"。
        """
        from waveform_analysis.utils.io import parse_and_stack_files

        if channel_workers is None or channel_workers <= 1:
            waveforms = []
            for i, files in enumerate(raw_filess):
                wf = parse_and_stack_files(
                    files,
                    show_progress=(show_progress and i == 0),
                    chunksize=chunksize,
                    n_jobs=n_jobs,
                    use_process_pool=use_process_pool,
                )
                waveforms.append(wf)
            return waveforms

        # 通道级并行：为每个通道分配一个任务，完成后按原顺序收集
        # 使用全局执行器管理器
        from waveform_analysis.core.execution.manager import get_executor

        waveforms = [None] * len(raw_filess)
        executor_name = f"channel_loading_{channel_executor}"

        with get_executor(
            executor_name,
            executor_type=channel_executor,
            max_workers=channel_workers,
            reuse=True,
        ) as ex:
            futures = {
                ex.submit(
                    parse_and_stack_files,
                    files,
                    show_progress=(show_progress and idx == 0),
                    chunksize=chunksize,
                    n_jobs=n_jobs,
                    use_process_pool=use_process_pool,
                ): idx
                for idx, files in enumerate(raw_filess)
            }

            for fut in as_completed(futures):
                idx = futures[fut]
                waveforms[idx] = fut.result()

        return waveforms  # type: ignore[return-value]

    def load_waveforms_generator(
        self,
        raw_filess: List[List[str]],
        chunksize: int = 1000,
    ) -> Generator[List[np.ndarray], None, None]:
        """
        流式加载波形，每次返回一个 chunk 的数据。
        """
        from waveform_analysis.utils.io import parse_files_generator

        gens = [
            parse_files_generator(files, chunksize=chunksize) for files in raw_filess
        ]
        return zip(*gens)


@export
def get_raw_files(
    n_channels: int = 6,
    run_name: str = "All_SelfTrigger",
    daq_run: Optional[Any] = None,
    data_root: str = "DAQ",
) -> List[List[str]]:
    """
    获取每个通道的文件列表。支持直接从 DAQRun 对象或文件系统扫描。
    """
    loader = WaveformLoader(n_channels, run_name, data_root)
    return loader.get_raw_files(daq_run)


@export
def get_waveforms(
    raw_filess: Optional[List[List[str]]] = None,
    daq_run: Optional[Any] = None,
    n_channels: int = 6,
    show_progress: bool = True,
    chunksize: Optional[int] = None,
    n_jobs: int = 1,
    use_process_pool: bool = False,
    channel_workers: Optional[int] = None,  # 可选参数,
    channel_executor: str = "thread",
    data_root: str = "DAQ",
    run_name: str = "All_SelfTrigger",
) -> List[np.ndarray]:
    """
    加载波形数据的便捷函数。

    Args:
        raw_filess (Optional[List[List[str]]], optional): 每个通道的文件路径列表。默认为 None。
        daq_run (Optional[Any], optional): DAQRun 对象，用于自动获取文件路径。默认为 None。
        n_channels (int, optional): 通道数量。默认为 6。
        show_progress (bool, optional): 是否显示加载进度条。默认为 True。
        chunksize (Optional[int], optional): 解析 CSV 时的分块大小。默认为 None。
        n_jobs (int, optional): 单个通道内解析文件的并行任务数。默认为 1。
        use_process_pool (bool, optional): 是否在解析 CSV 时使用进程池。默认为 False。
        channel_workers (Optional[int], optional): 通道级并行的并发数。默认为 None。
        channel_executor (str, optional): 通道级并行的执行器类型 ("thread" 或 "process")。默认为 "thread"。
        data_root (str, optional): 数据根目录。默认为 "DAQ"。
        run_name (str, optional): 运行名称。默认为 "All_SelfTrigger"。

    Returns:
        List[np.ndarray]: 包含每个通道波形数据的 numpy 数组列表。
    """

    loader: WaveformLoader = WaveformLoader(n_channels, run_name, data_root)
    if raw_filess is None:
        raw_filess = loader.get_raw_files(daq_run)

    return loader.load_waveforms(
        raw_filess,
        show_progress=show_progress,
        chunksize=chunksize,
        n_jobs=n_jobs,
        use_process_pool=use_process_pool,
        channel_workers=channel_workers,
        channel_executor=channel_executor,
    )


@export
def get_waveforms_generator(
    raw_filess: Optional[List[List[str]]] = None,
    daq_run: Optional[Any] = None,
    n_channels: int = 6,
    chunksize: int = 1000,
    show_progress: bool = False,
    data_root: str = "DAQ",
    run_name: str = "All_SelfTrigger",
):
    """
    返回一个生成器，按 chunk 产生同步的波形数据。
    """
    loader = WaveformLoader(n_channels, run_name, data_root)
    if raw_filess is None:
        raw_filess = loader.get_raw_files(daq_run)

    return loader.load_waveforms_generator(raw_filess, chunksize=chunksize)


@export
def build_filetime_index(raw_filess: List[List[str]]) -> List[List[Tuple[float, str]]]:
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


@export
def get_files_by_filetime(
    indexed_table: List[List[Tuple[float, str]]], t_query_mtime: float
) -> Dict[int, str]:
    """
    使用二分查找（bisect），找到最接近的时间文件。
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


@export
def get_files_before(
    raw_filess: List[List[str]], files_by_time: Dict[int, str]
) -> List[List[str]]:
    """获取指定文件之前的所有文件。"""
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
