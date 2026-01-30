"""
DAQ 运行数据管理 - 单个运行的数据结构和统计信息

本模块提供 DAQRun 类，用于管理和分析单个 DAQ 运行的原始数据文件。

主要功能:
- 扫描运行目录中的 RAW 文件并按通道分组
- 计算文件大小、事件数、采集时间等统计信息
- 提供运行级和通道级的元数据访问
- 支持多通道数据的结构化管理
- 格式化输出采集时间（支持 ps/ns/us/ms/s 单位）
- 支持通过 DAQ 适配器配置目录结构

数据结构:
- channel_files: 按通道组织的文件列表（包含路径、大小、索引）
- channel_stats: 每个通道的统计信息（事件数、总大小、时间范围）
- run_path: 运行根目录路径
- description: 从 description.txt 读取的运行描述

Examples:
    使用默认设置（VX2730）:
    >>> from waveform_analysis.utils.daq import DAQRun
    >>> run = DAQRun('50V_OV_circulation', './DAQ/50V_OV_circulation')
    >>> run.scan()  # 扫描所有文件
    >>> print(f"通道数: {len(run.channels)}")

    使用自定义适配器:
    >>> from waveform_analysis.utils.formats import get_adapter
    >>> adapter = get_adapter("vx2730")
    >>> run = DAQRun('run_001', './DAQ/run_001', daq_adapter=adapter)
"""

from __future__ import annotations

from datetime import datetime
import logging
import os
from pathlib import Path
import re
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from waveform_analysis.utils.formats import DAQAdapter, DirectoryLayout

logger = logging.getLogger(__name__)


class DAQRun:
    """单个 DAQ 运行的数据和分析类

    Attributes:
        run_name: 运行名称
        run_path: 运行根目录路径
        raw_dir: 原始数据目录路径
        channel_files: 按通道组织的文件列表
        channel_stats: 每个通道的统计信息
        daq_adapter: DAQ 适配器（可选）
        layout: 目录布局配置
    """

    # 默认配置（向后兼容）
    ALLOWED_EXTS = (".CSV", ".csv")
    CH_PATTERN = re.compile(r"CH(\d+)")
    IDX_PATTERN = re.compile(r"_(\d+)\.CSV$", re.IGNORECASE)

    @staticmethod
    def format_time_ps(ps_val: Optional[int]) -> str:
        if ps_val is None:
            return "N/A"

        if ps_val < 1e3:
            return f"{ps_val:.0f} ps"
        elif ps_val < 1e6:
            return f"{ps_val / 1e3:.2f} ns"
        elif ps_val < 1e9:
            return f"{ps_val / 1e6:.2f} us"
        elif ps_val < 1e12:
            return f"{ps_val / 1e9:.2f} ms"
        else:
            return f"{ps_val / 1e12:.2f} s"

    def __init__(
        self,
        run_name: str,
        run_path: str | Path,
        daq_adapter: Optional[Union[str, DAQAdapter]] = None,
        directory_layout: Optional[DirectoryLayout] = None,
    ):
        """初始化 DAQRun

        Args:
            run_name: 运行名称
            run_path: 运行根目录路径
            daq_adapter: DAQ 适配器名称或实例（可选）
            directory_layout: 目录布局配置（可选，优先于 daq_adapter）
        """
        self.run_name = run_name
        self.char = run_name
        self.run_path = str(run_path)

        # 初始化适配器和布局
        self.daq_adapter: Optional[DAQAdapter] = None
        self.layout: Optional[DirectoryLayout] = None

        if directory_layout is not None:
            self.layout = directory_layout
        elif daq_adapter is not None:
            if isinstance(daq_adapter, str):
                from waveform_analysis.utils.formats import get_adapter

                self.daq_adapter = get_adapter(daq_adapter)
            else:
                self.daq_adapter = daq_adapter
            self.layout = self.daq_adapter.directory_layout

        # 确定原始数据目录
        if self.layout is not None:
            # 使用布局配置确定路径
            # 注意：run_path 已经包含了 data_root/run_name，所以直接添加 raw_subdir
            if self.layout.raw_subdir:
                self.raw_dir = os.path.join(self.run_path, self.layout.raw_subdir)
            else:
                self.raw_dir = self.run_path
        else:
            # 向后兼容：使用默认的 RAW 子目录
            self.raw_dir = os.path.join(self.run_path, "RAW")

        self.description = self._load_description()
        self.total_bytes = 0
        self.file_count = 0
        self.channels = set()

        self.channel_files: Dict[int, List[Dict]] = {}
        self.channel_stats: Dict[int, Dict] = {}

        # 时间单位常量
        self.ps_per_ns = 1000
        self.ps_per_us = 1e6
        self.ps_per_s = 1e12

        self._scan_channel_files()

    def _load_description(self) -> str:
        info_file = os.path.join(self.run_path, f"{self.run_name}_info.txt")
        if os.path.exists(info_file):
            with open(info_file, encoding="utf-8") as f:
                return f.readline().strip()
        return "无描述"

    def _scan_channel_files(self) -> None:
        """扫描原始数据目录中的文件"""
        if not os.path.isdir(self.raw_dir):
            return

        # 使用布局配置扫描（如果可用）
        if self.layout is not None:
            self._scan_with_layout()
        else:
            self._scan_default()

    def _scan_with_layout(self) -> None:
        """使用目录布局配置扫描文件"""
        raw_path = Path(self.raw_dir)
        groups = self.layout.group_files_by_channel(raw_path)

        for ch, files in groups.items():
            for file_info in files:
                fpath = file_info["path"]
                size_bytes = fpath.stat().st_size
                mtime = datetime.fromtimestamp(fpath.stat().st_mtime)

                self.channel_files.setdefault(ch, []).append(
                    {
                        "filename": file_info["filename"],
                        "index": file_info["index"],
                        "path": str(fpath),
                        "size_bytes": size_bytes,
                        "mtime": mtime,
                        "timetag_min": None,
                        "timetag_max": None,
                    }
                )

                self.channels.add(ch)
                self.total_bytes += size_bytes
                self.file_count += 1

    def _scan_default(self) -> None:
        """使用默认配置扫描文件（向后兼容）"""
        for fname in sorted(os.listdir(self.raw_dir)):
            if not fname.endswith(self.ALLOWED_EXTS):
                continue

            fpath = os.path.join(self.raw_dir, fname)
            size_bytes = os.path.getsize(fpath)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))

            ch_match = self.CH_PATTERN.search(fname)
            ch = int(ch_match.group(1)) if ch_match else None
            idx_match = self.IDX_PATTERN.search(fname)
            idx = int(idx_match.group(1)) if idx_match else 0

            if ch is not None:
                self.channel_files.setdefault(ch, []).append(
                    {
                        "filename": fname,
                        "index": idx,
                        "path": fpath,
                        "size_bytes": size_bytes,
                        "mtime": mtime,
                        "timetag_min": None,
                        "timetag_max": None,
                    }
                )

                self.channels.add(ch)
                self.total_bytes += size_bytes
                self.file_count += 1

    def _parse_csv_file(self, fpath: str) -> Tuple[Optional[int], Optional[int]]:
        try:
            start_tag = None
            end_tag = None

            with open(fpath, encoding="utf-8", errors="ignore") as f:
                f.readline()
                first_line = f.readline().strip()
                if first_line:
                    first_parts = first_line.split(";")
                    if len(first_parts) >= 3:
                        start_tag = int(first_parts[2])

                f.seek(0, 2)
                file_size = f.tell()
                buffer_size = min(4096, file_size)
                pos = max(0, file_size - buffer_size)
                f.seek(pos)
                chunk = f.read()
                lines = chunk.split("\n")

                for i in range(len(lines) - 1, -1, -1):
                    last_line = lines[i].strip()
                    if last_line:
                        last_parts = last_line.split(";")
                        if len(last_parts) >= 3:
                            end_tag = int(last_parts[2])
                        break

            if start_tag is not None and end_tag is not None:
                return start_tag, end_tag

        except Exception:
            # 保持静默，解析失败将返回 (None, None)
            logger.debug("解析 CSV 文件失败: %s", fpath, exc_info=True)

        return None, None

    def compute_acquisition_times(self, force_reparse: bool = False) -> Dict[int, Dict]:
        if self.channel_stats and not force_reparse:
            return self.channel_stats

        for ch in sorted(self.channel_files.keys()):
            files = sorted(self.channel_files[ch], key=lambda x: x["index"])

            min_tag_ps = None
            max_tag_ps = None
            earliest_mtime = None
            latest_mtime = None

            for file_info in files:
                min_t, max_t = self._parse_csv_file(file_info["path"])
                if min_t is not None:
                    file_info["timetag_min"] = min_t
                    file_info["timetag_max"] = max_t

                    if min_tag_ps is None or min_t < min_tag_ps:
                        min_tag_ps = min_t
                    if max_tag_ps is None or max_t > max_tag_ps:
                        max_tag_ps = max_t

                mtime = file_info["mtime"]
                if earliest_mtime is None or mtime < earliest_mtime:
                    earliest_mtime = mtime
                if latest_mtime is None or mtime > latest_mtime:
                    latest_mtime = mtime

            start_us = min_tag_ps / self.ps_per_us if min_tag_ps is not None else None
            end_us = max_tag_ps / self.ps_per_us if max_tag_ps is not None else None
            duration_s = (
                (max_tag_ps - min_tag_ps) / self.ps_per_s
                if (min_tag_ps is not None and max_tag_ps is not None)
                else None
            )

            self.channel_stats[ch] = {
                "file_count": len(files),
                "total_size_bytes": sum(f["size_bytes"] for f in files),
                "start_time_ps": min_tag_ps,
                "end_time_ps": max_tag_ps,
                "start_time_us": start_us,
                "end_time_us": end_us,
                "duration_s": duration_s,
                "earliest_mtime": earliest_mtime,
                "latest_mtime": latest_mtime,
            }

        return self.channel_stats

    def get_channel_summary(self) -> Dict[int, Dict]:
        if not self.channel_stats:
            self.compute_acquisition_times()
        return self.channel_stats

    def get_channel_file_details(self, channel: int) -> Optional[List[Dict]]:
        return sorted(self.channel_files.get(channel, []), key=lambda x: x["index"])

    def to_dict(self) -> Dict:
        return {
            "run_name": self.run_name,
            "description": self.description,
            "file_count": self.file_count,
            "total_size_mb": self.total_bytes / (1024**2) if self.total_bytes > 0 else 0,
            "total_bytes": self.total_bytes,
            "channel_count": len(self.channels),
            "channels": sorted(self.channels),
            "channel_str": (", ".join(map(str, sorted(self.channels))) if self.channels else "-"),
            "path": self.run_path,
        }
