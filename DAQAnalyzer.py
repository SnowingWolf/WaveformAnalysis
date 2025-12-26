import json
import os
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from IPython.display import display
except ImportError:

    def display(x):
        print(x)


class DAQRun:
    """单个 DAQ 运行的数据和分析类"""

    # 仅处理 CSV 数据文件，避免误读 .root/.dat
    ALLOWED_EXTS = (".CSV", ".csv")
    CH_PATTERN = re.compile(r"CH(\d+)")
    IDX_PATTERN = re.compile(r"_(\d+)\.CSV$", re.IGNORECASE)

    def __init__(self, run_name, run_path):
        self.run_name = run_name
        self.run_path = run_path
        self.raw_dir = os.path.join(run_path, "RAW")

        # 基本信息
        self.description = self._load_description()
        self.total_bytes = 0
        self.file_count = 0
        self.channels = set()

        # 时间戳信息 (ps 为单位)
        self.channel_files = {}  # {channel: [list of file info]}
        self.channel_stats = {}  # {channel: {stats}}
        self.ps_per_ns = 1000  # 1 ns = 1000 ps
        self.ps_per_us = 1e6  # 1 us = 1e6 ps
        self.ps_per_s = 1e12  # 1 s = 1e12 ps

        self._scan_channel_files()
        self._compute_channel_stats()

    def _load_description(self):
        """读取描述信息"""
        info_file = os.path.join(self.run_path, f"{self.run_name}_info.txt")
        if os.path.exists(info_file):
            with open(info_file, "r", encoding="utf-8") as f:
                return f.readline().strip()
        return "无描述"

    def _scan_channel_files(self):
        """扫描 RAW 目录下的所有文件，按通道组织"""
        if not os.path.isdir(self.raw_dir):
            return

        for fname in sorted(os.listdir(self.raw_dir)):
            if not fname.endswith(self.ALLOWED_EXTS):
                continue

            fpath = os.path.join(self.raw_dir, fname)
            size_bytes = os.path.getsize(fpath)
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath))

            # 提取通道和索引
            ch_match = self.CH_PATTERN.search(fname)
            ch = int(ch_match.group(1)) if ch_match else None
            idx_match = self.IDX_PATTERN.search(fname)
            idx = int(idx_match.group(1)) if idx_match else 0

            if ch is not None:
                if ch not in self.channel_files:
                    self.channel_files[ch] = []

                self.channel_files[ch].append({
                    "filename": fname,
                    "index": idx,
                    "path": fpath,
                    "size_bytes": size_bytes,
                    "mtime": mtime,
                    "timetag_min": None,
                    "timetag_max": None,
                    "timetag_min_ns": None,
                    "timetag_max_ns": None,
                })

                self.channels.add(ch)
                self.total_bytes += size_bytes
                self.file_count += 1

    def _compute_channel_stats(self):
        """初始化统计数据（延迟计算）"""
        pass

    def _parse_csv_file(self, fpath):
        """解析 CSV 文件的时间戳列（第3列 TIMETAG）
        只读取第一行和最后一行以获取开始和结束时间戳
        返回 (min_timetag_ps, max_timetag_ps)
        """
        try:
            start_tag = None
            end_tag = None

            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                # 读取第一行（header）
                header = f.readline()

                # 读取第二行（第一条数据）
                first_line = f.readline().strip()
                if first_line:
                    first_parts = first_line.split(";")
                    if len(first_parts) >= 3:
                        start_tag = int(first_parts[2])

                # 读取文件的最后一行
                # 从末尾开始，每次往前读 4KB 块
                f.seek(0, 2)  # 移到文件末尾
                file_size = f.tell()

                # 设置缓冲区大小（避免一次性读取大文件）
                buffer_size = min(4096, file_size)
                pos = max(0, file_size - buffer_size)
                f.seek(pos)

                # 读取末尾的块，找到最后一行
                chunk = f.read()
                lines = chunk.split("\n")

                # 从后往前找非空行
                for i in range(len(lines) - 1, -1, -1):
                    last_line = lines[i].strip()
                    if last_line:
                        last_parts = last_line.split(";")
                        if len(last_parts) >= 3:
                            end_tag = int(last_parts[2])
                        break

            if start_tag is not None and end_tag is not None:
                return start_tag, end_tag

        except Exception as e:
            # 静默处理，不打印警告以提高性能
            pass

        return None, None

    def compute_acquisition_times(self, force_reparse=False):
        """计算每个通道的采集时间（开始和结束）

        返回：
            dict: {channel: {
                'file_count': int,
                'total_size_bytes': int,
                'start_time_ps': int,
                'end_time_ps': int,
                'start_time_us': float,
                'end_time_us': float,
                'duration_s': float,
                'earliest_mtime': datetime,
                'latest_mtime': datetime,
            }}
        """
        if self.channel_stats and not force_reparse:
            return self.channel_stats

        for ch in sorted(self.channel_files.keys()):
            files = self.channel_files[ch]
            files_sorted = sorted(files, key=lambda x: x["index"])

            min_tag_ps = None
            max_tag_ps = None
            earliest_mtime = None
            latest_mtime = None

            # 遍历每个文件，获取时间戳范围
            for file_info in files_sorted:
                min_t, max_t = self._parse_csv_file(file_info["path"])
                if min_t is not None:
                    file_info["timetag_min"] = min_t
                    file_info["timetag_max"] = max_t
                    file_info["timetag_min_ns"] = min_t // self.ps_per_ns
                    file_info["timetag_max_ns"] = max_t // self.ps_per_ns

                    if min_tag_ps is None or min_t < min_tag_ps:
                        min_tag_ps = min_t
                    if max_tag_ps is None or max_t > max_tag_ps:
                        max_tag_ps = max_t

                # 记录文件修改时间范围
                mtime = file_info["mtime"]
                if earliest_mtime is None or mtime < earliest_mtime:
                    earliest_mtime = mtime
                if latest_mtime is None or mtime > latest_mtime:
                    latest_mtime = mtime

            # 转换为其他单位
            start_us = min_tag_ps / self.ps_per_us if min_tag_ps is not None else None
            end_us = max_tag_ps / self.ps_per_us if max_tag_ps is not None else None

            if min_tag_ps is not None and max_tag_ps is not None:
                duration_s = (max_tag_ps - min_tag_ps) / self.ps_per_s
            else:
                duration_s = None

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

    def get_channel_summary(self):
        """获取所有通道的汇总统计"""
        if not self.channel_stats:
            self.compute_acquisition_times()
        return self.channel_stats

    def get_channel_file_details(self, channel):
        """获取指定通道的所有文件详情"""
        if channel not in self.channel_files:
            return None
        return sorted(self.channel_files[channel], key=lambda x: x["index"])

    def to_dict(self):
        """转换为字典格式（用于创建 DataFrame）"""
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
    def format_time_ps(ps_val):
        """格式化 ps 为易读的时间"""
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

    def __init__(self, daq_root="DAQ"):
        self.daq_root = daq_root
        self.runs = {}  # {run_name: DAQRun}
        self.df_runs = None
        self.total_bytes = 0

    @staticmethod
    def format_size(bytes_val):
        """将字节转换为易读格式"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_val < 1024:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.2f} PB"

    def scan_all_runs(self):
        """扫描所有运行"""
        if not os.path.exists(self.daq_root):
            print(f"错误: 找不到目录 {self.daq_root}")
            return self

        self.runs = {}
        self.total_bytes = 0

        for run_name in sorted(os.listdir(self.daq_root)):
            run_path = os.path.join(self.daq_root, run_name)

            if not os.path.isdir(run_path):
                continue

            # 创建 DAQRun 对象
            run = DAQRun(run_name, run_path)
            self.runs[run_name] = run
            self.total_bytes += run.total_bytes

        # 生成 DataFrame
        self._build_dataframe()
        return self

    def _build_dataframe(self):
        """从所有运行生成 DataFrame"""
        run_dicts = [run.to_dict() for run in self.runs.values()]
        self.df_runs = pd.DataFrame(run_dicts)

    def get_run(self, run_name):
        """获取指定运行的 DAQRun 对象"""
        return self.runs.get(run_name)

    def get_all_runs(self):
        """获取所有运行"""
        return list(self.runs.values())

    def display_overview(self):
        """显示所有运行的概览表"""
        if self.df_runs is None or self.df_runs.empty:
            print("未发现任何有效的运行数据。")
            return self

        print(f"📊 数据汇总: 共找到 {len(self.df_runs)} 个运行项目 | 总占用空间: {self.format_size(self.total_bytes)}")
        print("\n")

        styled_df = (
            self.df_runs[["run_name", "description", "file_count", "total_size_mb", "channel_count", "channel_str"]]
            .rename(
                columns={
                    "run_name": "运行名称",
                    "description": "描述",
                    "file_count": "文件数",
                    "total_size_mb": "大小(MB)",
                    "channel_count": "通道数",
                    "channel_str": "通道列表",
                }
            )
            .style.background_gradient(subset=["文件数", "通道数"], cmap="Blues")
            .background_gradient(subset=["大小(MB)"], cmap="Reds")
            .format({"大小(MB)": "{:.2f}"})
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
        display(styled_df)
        return self

    def display_summary(self):
        """显示详细统计信息"""
        if self.df_runs is None or self.df_runs.empty:
            print("未发现任何有效的运行数据。")
            return self

        print("=" * 80)
        print("详细统计信息")
        print("=" * 80)

        print(f"\n总运行项目数: {len(self.df_runs)}")
        print(f"总文件数: {self.df_runs['file_count'].sum()}")
        print(f"总占用空间: {self.format_size(self.df_runs['total_bytes'].sum())}")
        print(f"平均文件数/项目: {self.df_runs['file_count'].mean():.1f}")
        print(f"平均空间/项目: {self.format_size(self.df_runs['total_bytes'].mean())}")

        if self.df_runs["file_count"].max() > 0:
            print(
                f"\n最大文件数项目: {self.df_runs.loc[self.df_runs['file_count'].idxmax(), 'run_name']} ({self.df_runs['file_count'].max()} 个文件)"
            )
            print(
                f"最大空间项目: {self.df_runs.loc[self.df_runs['total_bytes'].idxmax(), 'run_name']} ({self.format_size(self.df_runs['total_bytes'].max())})"
            )

        # 通道使用情况
        all_channels = set()
        for ch_list in self.df_runs["channel_str"]:
            if ch_list != "-":
                channels = [int(x.strip()) for x in ch_list.split(",")]
                all_channels.update(channels)

        if all_channels:
            print(f"\n使用的通道: {sorted(all_channels)}")
            print(f"通道总数: {len(all_channels)}")

        # 空项目检查
        empty_runs = self.df_runs[self.df_runs["file_count"] == 0]
        if not empty_runs.empty:
            print(f"\n⚠️  无数据的项目 ({len(empty_runs)} 个):")
            for name in empty_runs["run_name"]:
                print(f"  - {name}")

        print("=" * 80)
        return self

    def display_run_channel_details(self, run_name, show_files: bool = False):
        """显示指定运行的通道采集时间和文件详情（表格形式）。

        Args:
            run_name (str): 运行名
            show_files (bool): 是否显示每个通道的文件明细表（默认 False）
        """
        run = self.get_run(run_name)
        if run is None:
            print(f"错误: 找不到运行 {run_name}")
            return self

        # 计算采集时间
        run.compute_acquisition_times()
        stats = run.get_channel_summary()

        print(f"\n{'=' * 80}")
        print(f"运行: {run_name}")
        print(f"{'=' * 80}")

        # 汇总表格
        rows = []
        for ch in sorted(stats.keys()):
            s = stats[ch]
            start_readable = DAQRun.format_time_ps(s.get("start_time_ps"))
            end_readable = DAQRun.format_time_ps(s.get("end_time_ps"))
            duration = f"{s['duration_s']:.3f} s" if s.get("duration_s") is not None else "N/A"

            rows.append({
                "channel": f"CH{ch}",
                "files": s.get("file_count"),
                "total_size": self.format_size(s.get("total_size_bytes", 0)),
                "start_time": start_readable,
                "end_time": end_readable,
                "duration": duration,
                "earliest_file": s.get("earliest_mtime"),
                "latest_file": s.get("latest_mtime"),
            })

        try:
            df = pd.DataFrame(rows).set_index("channel")
            display(df)
        except Exception:
            # 退回到打印模式（极低概率触发）
            print("\n【通道采集时间统计】")
            for r in rows:
                print(
                    f"  {r['channel']}: files={r['files']}, size={r['total_size']}, start={r['start_time']}, end={r['end_time']}, duration={r['duration']}"
                )

        # 可选：显示每个通道的文件明细
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
                    display(fdf)
                except Exception:
                    for fr in frows:
                        print(fr)

        return self

    def save_to_json(self, output_path="daq_analysis.json", include_file_details=True):
        """保存扫描结果到 JSON 文件

        Args:
            output_path (str): 输出文件路径，默认为 'daq_analysis.json'
            include_file_details (bool): 是否包含每个文件的详细信息

        Returns:
            str: 输出文件路径
        """
        if self.df_runs is None or self.df_runs.empty:
            print("错误: 尚未扫描运行数据，请先调用 scan_all_runs()")
            return None

        # 确保所有运行都已计算采集时间
        for run in self.runs.values():
            run.compute_acquisition_times()

        # 构建输出数据
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

        # 添加每个运行的数据
        for run_name in sorted(self.runs.keys()):
            run = self.runs[run_name]
            stats = run.get_channel_summary()

            # 基本运行信息
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

            # 添加每个通道的详情
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

                # 添加文件详情（可选）
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
                                "timetag_min_ps": file_info["timetag_min"],
                                "timetag_max_ps": file_info["timetag_max"],
                                "timetag_min_readable": DAQRun.format_time_ps(file_info["timetag_min"]),
                                "timetag_max_readable": DAQRun.format_time_ps(file_info["timetag_max"]),
                            }
                            channel_data["files"].append(file_data)

                run_data["channel_details"][str(ch)] = channel_data

            output_data["runs"].append(run_data)

        # 保存到文件
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            print(f"✓ 数据已保存到: {output_path}")
            print(f"  文件大小: {self.format_size(os.path.getsize(output_path))}")
            return output_path
        except Exception as e:
            print(f"✗ 保存文件失败: {e}")
            return None


# 使用示例
if __name__ == "__main__":
    print("=" * 80)
    print("DAQ 分析器 - 使用示例")
    print("=" * 80)
    print("\n基本用法：")
    print("  # 创建分析器并扫描所有运行")
    print("  analyzer = DAQAnalyzer()")
    print("  analyzer.scan_all_runs()")
    print("")
    print("  # 显示概览和统计")
    print("  analyzer.display_overview()")
    print("  analyzer.display_summary()")
    print("")
    print("  # 显示指定运行的通道时间信息")
    print("  analyzer.display_run_channel_details('50V_OV_circulation_20thr')")
    print("")
    print("  # 获取指定运行的 DAQRun 对象进行深度分析")
    print("  run = analyzer.get_run('50V_OV_circulation_20thr')")
    print("  stats = run.compute_acquisition_times()")
    print("=" * 80)
