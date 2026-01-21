# -*- coding: utf-8 -*-
"""DAQAnalyzer: aggregate runs and notebook/terminal display helpers."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

try:
    from IPython import get_ipython
    from IPython.display import display as _display

    def _in_notebook() -> bool:
        # Detect IPython kernel presence without hard failure.
        try:
            return get_ipython() is not None
        except Exception:
            return False

except Exception:
    def _display(x):
        print(x)

    def _in_notebook() -> bool:
        # Fallback when IPython is unavailable.
        return False

logger = logging.getLogger(__name__)

from .daq_run import DAQRun
class DAQAnalyzer:
    """DAQ 数据分析器：管理所有运行的统一分析（显示/保存等）。"""

    def __init__(self, daq_root: Union[str, Path] = "DAQ") -> None:
        """
        初始化 DAQ 数据分析器

        Args:
            daq_root: DAQ 数据根目录（默认 "DAQ"）

        初始化内容:
        - 设置 DAQ 根目录
        - 初始化运行字典和统计信息
        """
        self.daq_root = str(daq_root)
        self.runs: Dict[str, DAQRun] = {}
        self.df_runs: Optional[pd.DataFrame] = None
        self.total_bytes = 0

    @staticmethod
    def format_size(bytes_val: int) -> str:
        # Human-readable byte size formatter with binary units.
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_val < 1024:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.2f} PB"

    # ---- terminal color helpers ----
    @staticmethod
    def _ansi_wrap(text: str, color: str) -> str:
        codes = {
            "red": "31",
            "green": "32",
            "yellow": "33",
            "blue": "34",
            "magenta": "35",
            "cyan": "36",
            "bold": "1",
        }
        code = codes.get(color, "0")
        return f"\x1b[{code}m{text}\x1b[0m"

    def _color_size(self, size_bytes: int) -> str:
        mb = 1024 * 1024
        if size_bytes is None:
            return "N/A"
        if size_bytes > 10 * mb:
            return self._ansi_wrap(self.format_size(size_bytes), "red")
        if size_bytes > 1 * mb:
            return self._ansi_wrap(self.format_size(size_bytes), "yellow")
        return self._ansi_wrap(self.format_size(size_bytes), "green")

    def _color_duration(self, duration_s: Optional[float]) -> str:
        if duration_s is None:
            return "N/A"
        if duration_s > 1.0:
            return self._ansi_wrap(f"{duration_s:.3f} s", "red")
        if duration_s > 0.1:
            return self._ansi_wrap(f"{duration_s:.3f} s", "yellow")
        return self._ansi_wrap(f"{duration_s:.3f} s", "green")

    # ---- HTML helpers for notebook display ----
    @staticmethod
    def _html_wrap(text: str, color: str, bold: bool = True) -> str:
        weight = "font-weight:bold;" if bold else ""
        return f"<span style='color:{color};{weight}'>{text}</span>"

    def _html_color_size(self, size_bytes: int) -> str:
        mb = 1024 * 1024
        if size_bytes is None:
            return "N/A"
        if size_bytes > 10 * mb:
            return self._html_wrap(self.format_size(size_bytes), "#c92a2a")
        if size_bytes > 1 * mb:
            return self._html_wrap(self.format_size(size_bytes), "#c67f00")
        return self._html_wrap(self.format_size(size_bytes), "#1b7a1b")

    def _html_color_duration(self, duration_s: Optional[float]) -> str:
        if duration_s is None:
            return "N/A"
        if duration_s > 1.0:
            return self._html_wrap(f"{duration_s:.3f} s", "#c92a2a")
        if duration_s > 0.1:
            return self._html_wrap(f"{duration_s:.3f} s", "#c67f00")
        return self._html_wrap(f"{duration_s:.3f} s", "#1b7a1b")

    def scan_all_runs(self) -> DAQAnalyzer:
        # Scan DAQ root and load each run directory as a DAQRun.
        # 局部导入 os 以提高在 autoreload/部分导入失败时的鲁棒性

        if not os.path.exists(self.daq_root):
            logger.error("找不到目录 %s", self.daq_root)
            return self

        self.runs = {}
        self.total_bytes = 0

        for run_name in sorted(os.listdir(self.daq_root)):
            run_path = os.path.join(self.daq_root, run_name)
            if not os.path.isdir(run_path):
                continue

            # Aggregate per-run metadata for overview stats.
            run = DAQRun(run_name, run_path)
            self.runs[run_name] = run
            self.total_bytes += run.total_bytes

        self._build_dataframe()
        return self

    def _build_dataframe(self) -> None:
        # Build the overview DataFrame from per-run dicts.
        run_dicts = [run.to_dict() for run in self.runs.values()]
        self.df_runs = pd.DataFrame(run_dicts)

    def get_run(self, run_name: str) -> Optional[DAQRun]:
        return self.runs.get(run_name)

    def get_all_runs(self) -> List[DAQRun]:
        return list(self.runs.values())

    def _build_channel_rows(self, stats: Dict[int, Dict]) -> List[Dict]:
        # Normalize channel stats into row dicts for DataFrame display.
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
        return rows

    def _display_file_details_for_channel(self, run: DAQRun, ch: int) -> None:
        # Show per-file details for a given channel if requested.
        files = run.get_channel_file_details(ch)
        if not files:
            return

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

    def display_overview(self) -> DAQAnalyzer:
        if self.df_runs is None or self.df_runs.empty:
            print("No runs scanned. Call scan_all_runs() first.")
            return self

        # Prepare columns for both notebook and terminal views.
        df = self.df_runs.copy()
        df["size_mb"] = df["total_bytes"].apply(lambda v: float(int(v) if v is not None else 0) / (1024**2))
        df["size_readable"] = df["total_bytes"].apply(lambda v: self.format_size(int(v) if v is not None else 0))
        display_cols = ["run_name", "file_count", "channel_count", "size_mb", "size_readable", "path"]

        if _in_notebook():
            try:
                from IPython.display import display as _ipydisplay

                # Rich notebook styling with gradients.
                styled_df = (
                    df[["run_name", "file_count", "size_mb", "size_readable", "channel_count", "channel_str", "path"]]
                    .rename(
                        columns={
                            "run_name": "运行名称",
                            "file_count": "文件数",
                            "size_mb": "大小(MB)",
                            "size_readable": "大小",
                            "channel_count": "通道数",
                            "channel_str": "通道列表",
                            "path": "路径",
                        }
                    )
                    .style.background_gradient(subset=["文件数", "通道数"], cmap="Blues")
                    .background_gradient(subset=["大小(MB)"], cmap="Reds")
                    .format({"大小(MB)": "{:.2f}", "大小": "{}"})
                    .set_properties(**{"text-align": "left"})
                    .set_table_styles([
                        {
                            "selector": "th",
                            "props": [
                                ("background-color", "#4CAF50"),
                                ("color", "white"),
                                ("font-weight", "bold"),
                                ("text-align", "center"),
                            ],
                        }
                    ])
                    .hide(axis="index")
                )

                _ipydisplay(styled_df)
            except Exception:
                _display(df[display_cols])
        else:
            # Compact terminal output with ANSI colors.
            rows = []
            for _, r in df[display_cols].iterrows():
                try:
                    orig = self.df_runs.loc[self.df_runs["run_name"] == r["run_name"]]
                    total_bytes = int(orig["total_bytes"].iloc[0]) if not orig.empty else 0
                except Exception:
                    total_bytes = 0

                line = (
                    f"{r['run_name']:20}  files={int(r['file_count']):4d}  "
                    f"channels={int(r['channel_count']):2d}  "
                    f"size={self._color_size(total_bytes)}  path={r['path']}"
                )
                rows.append(line)
            print("\n".join(rows))

        return self

    def display_run_channel_details(self, run_name: str, show_files: bool = False) -> "DAQAnalyzer":
        run = self.get_run(run_name)
        if run is None:
            print(f"错误: 找不到运行 {run_name}")
            return self

        # Ensure acquisition times are computed before summarizing.
        run.compute_acquisition_times()
        stats = run.get_channel_summary()

        print(f"\n{'=' * 80}")
        print(f"运行: {run_name}")
        print(f"{'=' * 80}")

        rows = self._build_channel_rows(stats)
        df = pd.DataFrame(rows).set_index("channel")

        if _in_notebook():
            try:
                from IPython.display import HTML as _HTML

                # Use pandas Styler to apply background gradients similar to display_overview.
                df_display = df.copy()

                # Ensure numeric columns exist for styling.
                df_display["total_size_bytes"] = df_display["total_size_bytes"].fillna(0).astype(float)
                # Duration in seconds may be None; keep numeric for conditional formatting.
                df_display["duration_s"] = df_display["duration_s"].where(df_display["duration_s"].notna(), None)

                try:
                    styled = (
                        df_display[["files", "total_size_bytes", "duration_s", "start_time", "end_time"]]
                        .rename(
                            columns={
                                "files": "文件数",
                                "total_size_bytes": "大小(字节)",
                                "duration_s": "持续(s)",
                                "start_time": "开始",
                                "end_time": "结束",
                            }
                        )
                        .style.background_gradient(subset=["文件数"], cmap="Blues")
                        .background_gradient(subset=["大小(字节)"], cmap="Reds")
                        .format({
                            "大小(字节)": lambda v: self.format_size(int(v) if v is not None else 0),
                            "持续(s)": lambda v: (f"{v:.3f} s" if (v is not None) else "N/A"),
                        })
                        .set_properties(**{"text-align": "left"})
                        .set_table_styles([
                            {
                                "selector": "th",
                                "props": [
                                    ("background-color", "#4CAF50"),
                                    ("color", "white"),
                                    ("font-weight", "bold"),
                                    ("text-align", "center"),
                                ],
                            }
                        ])
                        .hide(axis="index")
                    )

                    _ipydisplay(styled)
                except Exception:
                    # Fallback to basic HTML table if styler fails.
                    df_display["size_html"] = [
                        self._html_color_size(stats.get(int(i.replace("CH", "")), {}).get("total_size_bytes", 0))
                        for i in df_display.index
                    ]
                    df_display["dur_html"] = [
                        self._html_color_duration(stats.get(int(i.replace("CH", "")), {}).get("duration_s"))
                        for i in df_display.index
                    ]
                    html = df_display.to_html(
                        escape=False, columns=["files", "size_html", "dur_html", "start_time", "end_time"]
                    )
                    _display(_HTML(html))
            except Exception:
                _display(df)
        else:
            # Plain terminal table with colored size/duration fields.
            df_display = df.copy()
            df_display["total_size"] = df_display["total_size_bytes"].apply(
                lambda v: self.format_size(int(v) if v is not None else 0)
            )
            df_display["duration"] = df_display["duration_s"].apply(lambda v: f"{v:.3f} s" if v is not None else "N/A")
            cols = ["files", "total_size", "duration", "start_time", "end_time"]

            out_lines = []
            for idx, row in df_display.iterrows():
                size_str = (
                    self._color_size(stats.get(int(idx.replace("CH", "")), {}).get("total_size_bytes", 0))
                    if idx.startswith("CH")
                    else (self._color_size(0))
                )
                duration_val = row.get("duration_s")
                dur_str = self._color_duration(duration_val)

                out_lines.append(
                    f"{idx:6} files={int(row['files']):3d}  size={size_str}  dur={dur_str}  start={row['start_time']}  end={row['end_time']}"
                )

            print("\n".join(out_lines))

        if show_files:
            # Optionally show file list details per channel.
            for ch in sorted(stats.keys()):
                self._display_file_details_for_channel(run, ch)

        return self

    def save_to_json(
        self, output_path: Union[str, Path] = "daq_analysis.json", include_file_details: bool = True
    ) -> Optional[str]:
        if self.df_runs is None or self.df_runs.empty:
            logger.error("尚未扫描运行数据，请先调用 scan_all_runs()")
            return None

        # Ensure each run has computed time statistics before export.
        for run in self.runs.values():
            run.compute_acquisition_times()

        # Build export payload with metadata and per-run details.
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

            # Per-run block with optional per-file details.
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
                            # Preserve raw values and readable formats.
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


__all__ = ["DAQAnalyzer"]
    
