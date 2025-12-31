"""DAQ 工具：包含 DAQRun 和 DAQAnalyzer

将原来的独立脚本移入包内并做轻量重构（使用 Path、logging、类型提示）以便于测试和引用。
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

try:
    from IPython import get_ipython
    from IPython.display import display as _display

    def _in_notebook() -> bool:
        try:
            return get_ipython() is not None
        except Exception:
            return False

except Exception:

    def _display(x):
        print(x)

    def _in_notebook() -> bool:
        return False


logger = logging.getLogger(__name__)


class DAQRun:
    """单个 DAQ 运行的数据和分析类"""

    ALLOWED_EXTS = (".CSV", ".csv")
    CH_PATTERN = re.compile(r"CH(\d+)")
    IDX_PATTERN = re.compile(r"_(\d+)\.CSV$", re.IGNORECASE)

    def __init__(self, run_name: str, run_path: str | Path):
        self.run_name = run_name
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


class DAQAnalyzer:
    """DAQ 数据分析器：管理所有运行的统一分析"""

    def __init__(self, daq_root: str | Path = "DAQ") -> None:
        self.daq_root = str(daq_root)
        self.runs: Dict[str, DAQRun] = {}
        self.df_runs: Optional[pd.DataFrame] = None
        self.total_bytes = 0

    @staticmethod
    def format_size(bytes_val: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_val < 1024:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.2f} PB"

    def scan_all_runs(self) -> "DAQAnalyzer":
        if not os.path.exists(self.daq_root):
            logger.error("找不到目录 %s", self.daq_root)
            return self

        self.runs = {}
        self.total_bytes = 0

        for run_name in sorted(os.listdir(self.daq_root)):
            run_path = os.path.join(self.daq_root, run_name)
            if not os.path.isdir(run_path):
                continue

            run = DAQRun(run_name, run_path)
            self.runs[run_name] = run
            self.total_bytes += run.total_bytes

        self._build_dataframe()
        return self

    def _build_dataframe(self) -> None:
        run_dicts = [run.to_dict() for run in self.runs.values()]
        self.df_runs = pd.DataFrame(run_dicts)

    def get_run(self, run_name: str) -> Optional[DAQRun]:
        return self.runs.get(run_name)

    def get_all_runs(self) -> List[DAQRun]:
        return list(self.runs.values())

    def display_overview(self) -> "DAQAnalyzer":
        """显示所有扫描到的 runs 的概览表格（兼容旧 API 名称 display_overview）。"""
        if self.df_runs is None or self.df_runs.empty:
            print("No runs scanned. Call scan_all_runs() first.")
            return self

        df = self.df_runs.copy()
        # 增加可读大小列
        df["total_size_readable"] = df["total_bytes"].apply(lambda v: self.format_size(int(v) if v is not None else 0))
        display_cols = ["run_name", "file_count", "channel_count", "total_size_readable", "path"]

        if _in_notebook():
            try:
                sty = df[display_cols].style.format({"file_count": "{:.0f}"}).set_caption("DAQ Scan Overview")
                _display(sty)
            except Exception:
                _display(df[display_cols])
        else:
            print(df[display_cols].to_string(index=False))

        return self

    def display_run_channel_details(self, run_name: str, show_files: bool = False) -> "DAQAnalyzer":
        """以表格方式展示指定运行的通道统计信息。可选地显示每个通道的文件明细。"""
        run = self.get_run(run_name)
        if run is None:
            print(f"错误: 找不到运行 {run_name}")
            return self

        run.compute_acquisition_times()
        stats = run.get_channel_summary()

        print(f"\n{'=' * 80}")
        print(f"运行: {run_name}")
        print(f"{'=' * 80}")

        rows = []
        for ch in sorted(stats.keys()):
            s = stats[ch]
            duration_s = s.get("duration_s")
            rows.append({
                "channel": f"CH{ch}",
                "files": s.get("file_count"),
                "total_size_bytes": s.get("total_size_bytes", 0),
                "start_time": DAQRun.format_time_ps(s.get("start_time_ps")),
                "end_time": DAQRun.format_time_ps(s.get("end_time_ps")),
                "duration_s": duration_s if duration_s is not None else None,
                "duration": f"{duration_s:.3f} s" if duration_s is not None else "N/A",
                "earliest_file": s.get("earliest_mtime"),
                "latest_file": s.get("latest_mtime"),
            })

        df = pd.DataFrame(rows).set_index("channel")

        # Notebook: use Styler for nicer display (conditional formatting + bar for duration)
        if _in_notebook():
            try:
                sty = (
                    df.style.format({
                        "total_size_bytes": lambda v: self.format_size(int(v) if v is not None else 0),
                        "duration_s": lambda v: f"{v:.3f} s" if v is not None else "N/A",
                    })
                    .background_gradient(subset=["total_size_bytes"], cmap="Reds")
                    .bar(subset=["duration_s"], color="#5fba7d")
                    .set_caption(f"DAQ Run: {run_name} - 通道采集时间统计")
                )
                _display(sty)
            except Exception:
                # 退回到基本展示
                _display(df)
        else:
            # 终端环境：显示文本表格（调整列格式）
            df_display = df.copy()
            df_display["total_size"] = df_display["total_size_bytes"].apply(
                lambda v: self.format_size(int(v) if v is not None else 0)
            )
            df_display["duration"] = df_display["duration_s"].apply(lambda v: f"{v:.3f} s" if v is not None else "N/A")
            cols = ["files", "total_size", "duration", "start_time", "end_time"]
            print(df_display[cols].to_string())

        if show_files:
            for ch in sorted(stats.keys()):
                files = run.get_channel_file_details(ch)
                if not files:
                    continue

                print(f"\n-- 文件明细 CH{ch} --")
                frows = []
                for fi in sorted(files, key=lambda x: x.get("index", 0)):
                    frows.append({
                        "filename": fi.get("filename"),
                        "index": fi.get("index"),
                        "size": self.format_size(fi.get("size_bytes", 0)),
                        "timetag_min": DAQRun.format_time_ps(fi.get("timetag_min")),
                        "timetag_max": DAQRun.format_time_ps(fi.get("timetag_max")),
                        "modified": fi.get("mtime"),
                    })

                try:
                    fdf = pd.DataFrame(frows).set_index("index")
                    _display(fdf)
                except Exception:
                    for fr in frows:
                        print(fr)

        return self

    def save_to_json(
        self, output_path: str | Path = "daq_analysis.json", include_file_details: bool = True
    ) -> Optional[str]:
        if self.df_runs is None or self.df_runs.empty:
            logger.error("尚未扫描运行数据，请先调用 scan_all_runs()")
            return None

        for run in self.runs.values():
            run.compute_acquisition_times()

        output_data = {
            "metadata": {
                "scan_time": datetime.now().isoformat(),
                "daq_root": self.daq_root,
                "total_runs": len(self.runs),
                "total_files": sum(run.file_count for run in self.runs.values()),
                "total_size_bytes": self.total_bytes,
                "total_size_readable": self.format_size(self.total_bytes),
            },
            "runs": [],
        }

        for run_name in sorted(self.runs.keys()):
            run = self.runs[run_name]
            stats = run.get_channel_summary()

            run_data = {
                "run_name": run.run_name,
                "description": run.description,
                "file_count": run.file_count,
                "total_size_bytes": run.total_bytes,
                "total_size_readable": self.format_size(run.total_bytes),
                "path": run.run_path,
                "channels": sorted(run.channels),
                "channel_details": {},
            }

            for ch in sorted(stats.keys()):
                s = stats[ch]
                channel_data = {
                    "channel": ch,
                    "file_count": s["file_count"],
                    "total_size_bytes": s["total_size_bytes"],
                    "total_size_readable": self.format_size(s["total_size_bytes"]),
                    "start_time_ps": s["start_time_ps"],
                    "end_time_ps": s["end_time_ps"],
                    "duration_seconds": s["duration_s"],
                    "earliest_file_time": s["earliest_mtime"].isoformat() if s["earliest_mtime"] else None,
                    "latest_file_time": s["latest_mtime"].isoformat() if s["latest_mtime"] else None,
                }

                if include_file_details:
                    files = run.get_channel_file_details(ch)
                    channel_data["files"] = []
                    if files:
                        for file_info in files:
                            file_data = {
                                "filename": file_info["filename"],
                                "index": file_info["index"],
                                "size_bytes": file_info["size_bytes"],
                                "size_readable": self.format_size(file_info["size_bytes"]),
                                "modified_time": file_info["mtime"].isoformat(),
                                "timetag_min_ps": file_info.get("timetag_min"),
                                "timetag_max_ps": file_info.get("timetag_max"),
                                "timetag_min_readable": DAQRun.format_time_ps(file_info.get("timetag_min")),
                                "timetag_max_readable": DAQRun.format_time_ps(file_info.get("timetag_max")),
                            }
                            channel_data["files"].append(file_data)

                run_data["channel_details"][str(ch)] = channel_data

            output_data["runs"].append(run_data)

        try:
            outp = str(output_path)
            with open(outp, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            logger.info("数据已保存到: %s", outp)
            return outp
        except Exception as e:
            logger.error("保存文件失败: %s", e)
            return None


__all__ = ["DAQRun", "DAQAnalyzer"]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DAQ Analysis - CLI for quick scanning")
    parser.add_argument("--root", type=str, default="DAQ", help="DAQ root directory")
    parser.add_argument("--out", type=str, default="daq_analysis.json", help="输出 JSON 文件路径")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    analyzer = DAQAnalyzer(args.root)
    analyzer.scan_all_runs()
    analyzer.save_to_json(args.out)
