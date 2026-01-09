# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class DAQRun:
    """单个 DAQ 运行的数据和分析类"""

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

    def __init__(self, run_name: str, run_path: str | Path):
        self.run_name = run_name
        self.char = run_name
        self.run_path = str(run_path)
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
            with open(info_file, "r", encoding="utf-8") as f:
                return f.readline().strip()
        return "无描述"

    def _scan_channel_files(self) -> None:
        if not os.path.isdir(self.raw_dir):
            return

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
                self.channel_files.setdefault(ch, []).append({
                    "filename": fname,
                    "index": idx,
                    "path": fpath,
                    "size_bytes": size_bytes,
                    "mtime": mtime,
                    "timetag_min": None,
                    "timetag_max": None,
                })

                self.channels.add(ch)
                self.total_bytes += size_bytes
                self.file_count += 1

    def _parse_csv_file(self, fpath: str) -> Tuple[Optional[int], Optional[int]]:
        try:
            start_tag = None
            end_tag = None

            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                header = f.readline()
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
            "channels": sorted(list(self.channels)),
            "channel_str": ", ".join(map(str, sorted(list(self.channels)))) if self.channels else "-",
            "path": self.run_path,
        }
