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

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import logging
import os
from pathlib import Path
import re
from typing import TYPE_CHECKING

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
    def _get_file_created_time(stat_result: os.stat_result) -> datetime:
        """从现有 stat 结果提取创建时间；若文件系统不支持则回退到 mtime。"""
        created_ts = getattr(stat_result, "st_birthtime", stat_result.st_mtime)
        return datetime.fromtimestamp(created_ts)

    @staticmethod
    def format_time_ps(ps_val: int | None) -> str:
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
        daq_adapter: str | DAQAdapter | None = None,
        directory_layout: DirectoryLayout | None = None,
        max_waves_for_channels: int = 50,
    ):
        """初始化 DAQRun

        Args:
            run_name: 运行名称
            run_path: 运行根目录路径
            daq_adapter: DAQ 适配器名称或实例（可选）
            directory_layout: 目录布局配置（可选，优先于 daq_adapter）
            max_waves_for_channels: 扫描文件时读取的波形数来判断通道（默认 50）
        """
        self.run_name = run_name
        self.run_path = str(run_path)
        self.max_waves_for_channels = max_waves_for_channels

        # 初始化适配器和布局
        self.daq_adapter: DAQAdapter | None = None
        self.layout: DirectoryLayout | None = None

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
        self.boards = set()  # 添加板卡集合

        self.channel_files: dict[int, list[dict]] = {}
        self.channel_stats: dict[int, dict] = {}
        self._run_acquisition_window: tuple[datetime | None, datetime | None] | None = None

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
                stat = fpath.stat()
                size_bytes = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime)
                created_time = self._get_file_created_time(stat)

                self.channel_files.setdefault(ch, []).append(
                    {
                        "filename": file_info["filename"],
                        "index": file_info["index"],
                        "path": str(fpath),
                        "size_bytes": size_bytes,
                        "created_time": created_time,
                        "mtime": mtime,
                        "timetag_min": None,
                        "timetag_max": None,
                    }
                )

                self.channels.add(ch)
                self.total_bytes += size_bytes
                self.file_count += 1

        # 对于 V1725 等单文件多通道格式，需要读取文件内部的实际通道和板卡信息
        self._scan_internal_channels_and_boards()

    def _scan_internal_channels_and_boards(self) -> None:
        """扫描文件内部的实际通道和板卡信息（用于 V1725 等格式）"""
        # 只对 V1725 适配器执行此操作
        if self.daq_adapter is None or self.daq_adapter.name != "v1725":
            return

        # 对于 V1725，channel_files 的键实际上是板卡号
        # 从每个板卡选择第一个文件进行扫描
        files_to_scan = []
        for files in self.channel_files.values():
            if files:
                # 每个板卡取第一个文件
                files_to_scan.append(Path(files[0]["path"]))

        if not files_to_scan:
            return

        # 读取选定的文件头来确定实际的通道和板卡，避免扫描阶段物化波形数据。
        try:
            from waveform_analysis.utils.formats.v1725 import V1725Reader

            boards_found = set()
            channels_found = set()

            for file_path in files_to_scan:
                board = V1725Reader._extract_board_from_path(file_path)
                channels = self._peek_v1725_channels(
                    file_path, max_waves=self.max_waves_for_channels
                )
                if channels:
                    boards_found.add(board)
                    channels_found.update(channels)

            # 更新板卡和通道信息
            if boards_found:
                self.boards = boards_found
            if channels_found:
                self.channels = channels_found

        except Exception as e:
            logger.debug(f"无法扫描文件内部通道/板卡信息: {e}")

    @staticmethod
    def _peek_v1725_channels(file_path: Path, max_waves: int = 50) -> set[int]:
        channels_found: set[int] = set()
        waves_seen = 0

        with file_path.open("rb") as f:
            while waves_seen < max_waves:
                event_header = f.read(16)
                if not event_header:
                    break
                if len(event_header) < 16:
                    break

                channel_mask = event_header[4] | (event_header[11] << 8)
                channel = 0
                while channel_mask and waves_seen < max_waves:
                    if channel_mask & 1:
                        ch_header = f.read(12)
                        if len(ch_header) < 12:
                            return channels_found

                        ch_size = int.from_bytes(ch_header[:3], "little") & ((1 << 22) - 1)
                        sig_size = (ch_size - 3) << 2
                        if sig_size < 0:
                            return channels_found

                        channels_found.add(channel)
                        waves_seen += 1
                        f.seek(sig_size, os.SEEK_CUR)

                    channel += 1
                    channel_mask >>= 1

        return channels_found

    def _scan_default(self) -> None:
        """使用默认配置扫描文件（向后兼容）"""
        with os.scandir(self.raw_dir) as entries:
            file_entries = sorted(
                (
                    entry
                    for entry in entries
                    if entry.is_file() and entry.name.endswith(self.ALLOWED_EXTS)
                ),
                key=lambda entry: entry.name,
            )

        for entry in file_entries:
            stat = entry.stat()
            size_bytes = stat.st_size
            mtime = datetime.fromtimestamp(stat.st_mtime)
            created_time = self._get_file_created_time(stat)

            ch_match = self.CH_PATTERN.search(entry.name)
            ch = int(ch_match.group(1)) if ch_match else None
            idx_match = self.IDX_PATTERN.search(entry.name)
            idx = int(idx_match.group(1)) if idx_match else 0

            if ch is not None:
                self.channel_files.setdefault(ch, []).append(
                    {
                        "filename": entry.name,
                        "index": idx,
                        "path": entry.path,
                        "size_bytes": size_bytes,
                        "created_time": created_time,
                        "mtime": mtime,
                        "timetag_min": None,
                        "timetag_max": None,
                    }
                )

                self.channels.add(ch)
                self.total_bytes += size_bytes
                self.file_count += 1

    def _parse_csv_file(self, fpath: str) -> tuple[int | None, int | None]:
        try:
            start_tag = None
            end_tag = None

            with open(fpath, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    first_line = line.strip()
                    if not first_line:
                        continue
                    first_parts = first_line.split(";")
                    if len(first_parts) < 3:
                        continue
                    try:
                        start_tag = int(first_parts[2])
                        break
                    except ValueError:
                        continue

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
                            try:
                                end_tag = int(last_parts[2])
                                break
                            except ValueError:
                                continue

            if start_tag is not None and end_tag is not None:
                return start_tag, end_tag

        except Exception:
            # 保持静默，解析失败将返回 (None, None)
            logger.debug("解析 CSV 文件失败: %s", fpath, exc_info=True)

        return None, None

    def _parse_v1725_file(self, fpath: str) -> tuple[int | None, int | None]:
        sampling_rate_hz = (
            self.daq_adapter.sampling_rate_hz if self.daq_adapter is not None else None
        )
        tick_ps = int(round(self.ps_per_s / sampling_rate_hz)) if sampling_rate_hz else 1

        min_tick = None
        max_tick = None

        try:
            with open(fpath, "rb") as f:
                while True:
                    event_header = f.read(16)
                    if not event_header:
                        break
                    if len(event_header) < 16:
                        break

                    channel_mask = event_header[4] | (event_header[11] << 8)
                    while channel_mask:
                        ch_header = f.read(12)
                        if len(ch_header) < 12:
                            return self._scale_v1725_ticks(min_tick, max_tick, tick_ps)

                        ch_size = int.from_bytes(ch_header[:3], "little") & ((1 << 22) - 1)
                        sig_size = (ch_size - 3) << 2
                        if sig_size < 0:
                            return self._scale_v1725_ticks(min_tick, max_tick, tick_ps)

                        timestamp = int.from_bytes(ch_header[4:10], "little")
                        min_tick = timestamp if min_tick is None else min(min_tick, timestamp)
                        max_tick = timestamp if max_tick is None else max(max_tick, timestamp)

                        f.seek(sig_size, os.SEEK_CUR)
                        channel_mask &= channel_mask - 1

        except Exception:
            logger.debug("解析 V1725 文件失败: %s", fpath, exc_info=True)

        return self._scale_v1725_ticks(min_tick, max_tick, tick_ps)

    @staticmethod
    def _scale_v1725_ticks(
        min_tick: int | None, max_tick: int | None, tick_ps: int
    ) -> tuple[int | None, int | None]:
        if min_tick is None or max_tick is None:
            return None, None
        return min_tick * tick_ps, max_tick * tick_ps

    def _iter_file_infos(self):
        for files in self.channel_files.values():
            yield from files

    def _reset_acquisition_cache(self) -> None:
        self.channel_stats = {}
        self._run_acquisition_window = None
        for file_info in self._iter_file_infos():
            file_info["timetag_min"] = None
            file_info["timetag_max"] = None

    def _populate_file_timetags(self) -> None:
        file_infos = list(self._iter_file_infos())
        if not file_infos:
            return

        parse_file = (
            self._parse_v1725_file
            if self.daq_adapter is not None and self.daq_adapter.name == "v1725"
            else self._parse_csv_file
        )

        max_workers = min(8, os.cpu_count() or 1, len(file_infos))
        if max_workers <= 1:
            for file_info in file_infos:
                min_t, max_t = parse_file(file_info["path"])
                file_info["timetag_min"] = min_t
                file_info["timetag_max"] = max_t
            return

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file_info = {
                executor.submit(parse_file, file_info["path"]): file_info
                for file_info in file_infos
            }
            for future in as_completed(future_to_file_info):
                file_info = future_to_file_info[future]
                min_t, max_t = future.result()
                file_info["timetag_min"] = min_t
                file_info["timetag_max"] = max_t

    def compute_acquisition_times(self, force_reparse: bool = False) -> dict[int, dict]:
        if self.channel_stats and not force_reparse:
            return self.channel_stats

        self._reset_acquisition_cache()
        self._populate_file_timetags()

        run_earliest_created_time = None
        run_latest_end_tag_ps = None

        for ch in sorted(self.channel_files.keys()):
            files = self.channel_files[ch]

            min_tag_ps = None
            max_tag_ps = None
            earliest_created_time = None
            earliest_mtime = None
            latest_mtime = None
            total_size_bytes = 0

            for file_info in files:
                min_t = file_info.get("timetag_min")
                max_t = file_info.get("timetag_max")
                total_size_bytes += file_info["size_bytes"]
                if min_t is not None:
                    if min_tag_ps is None or min_t < min_tag_ps:
                        min_tag_ps = min_t
                    if max_tag_ps is None or max_t > max_tag_ps:
                        max_tag_ps = max_t

                created_time = file_info.get("created_time")
                if created_time is not None:
                    if earliest_created_time is None or created_time < earliest_created_time:
                        earliest_created_time = created_time

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
            latest_end_time = None
            if earliest_created_time is not None and max_tag_ps is not None:
                latest_end_time = earliest_created_time + timedelta(
                    seconds=max_tag_ps / self.ps_per_s
                )

            self.channel_stats[ch] = {
                "file_count": len(files),
                "total_size_bytes": total_size_bytes,
                "start_time_ps": min_tag_ps,
                "end_time_ps": max_tag_ps,
                "start_time_us": start_us,
                "end_time_us": end_us,
                "duration_s": duration_s,
                "earliest_created_time": earliest_created_time,
                "latest_end_time": latest_end_time,
                "earliest_mtime": earliest_mtime,
                "latest_mtime": latest_mtime,
            }

            if earliest_created_time is not None and (
                run_earliest_created_time is None
                or earliest_created_time < run_earliest_created_time
            ):
                run_earliest_created_time = earliest_created_time
            if max_tag_ps is not None and (
                run_latest_end_tag_ps is None or max_tag_ps > run_latest_end_tag_ps
            ):
                run_latest_end_tag_ps = max_tag_ps

        acquisition_end = None
        if run_earliest_created_time is not None and run_latest_end_tag_ps is not None:
            acquisition_end = run_earliest_created_time + timedelta(
                seconds=run_latest_end_tag_ps / self.ps_per_s
            )
        self._run_acquisition_window = (run_earliest_created_time, acquisition_end)

        return self.channel_stats

    def get_channel_summary(self) -> dict[int, dict]:
        if not self.channel_stats:
            self.compute_acquisition_times()
        return self.channel_stats

    def get_run_acquisition_window(self) -> tuple[datetime | None, datetime | None]:
        """返回整个 run 的采集开始/结束时间。

        开始时间取所有文件中最早的创建时间；
        结束时间取“最早创建时间 + 所有文件中最大的结束 timetag”。
        """
        self.compute_acquisition_times()
        if self._run_acquisition_window is None:
            return None, None
        return self._run_acquisition_window

    def get_file_time_window(self) -> tuple[datetime | None, datetime | None]:
        """返回基于文件系统时间的轻量 run 时间窗口。"""
        file_infos = list(self._iter_file_infos())
        if not file_infos:
            return None, None

        start_time = None
        end_time = None
        for file_info in file_infos:
            created_time = file_info.get("created_time")
            if created_time is not None and (start_time is None or created_time < start_time):
                start_time = created_time

            mtime = file_info.get("mtime")
            if mtime is not None and (end_time is None or mtime > end_time):
                end_time = mtime

        return start_time, end_time

    def get_channel_file_details(self, channel: int) -> list[dict] | None:
        return sorted(self.channel_files.get(channel, []), key=lambda x: x["index"])

    def to_dict(self) -> dict:
        return {
            "run_name": self.run_name,
            "description": self.description,
            "file_count": self.file_count,
            "total_size_mb": self.total_bytes / (1024**2) if self.total_bytes > 0 else 0,
            "total_bytes": self.total_bytes,
            "board_count": len(self.boards),
            "boards": sorted(self.boards),
            "board_str": (", ".join(map(str, sorted(self.boards))) if self.boards else "-"),
            "channel_count": len(self.channels),
            "channels": sorted(self.channels),
            "channel_str": (", ".join(map(str, sorted(self.channels))) if self.channels else "-"),
            "path": self.run_path,
        }
