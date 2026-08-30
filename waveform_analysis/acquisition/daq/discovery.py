"""Filesystem discovery for DAQ runs and channel files."""

from datetime import datetime
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def scan_all_runs(
    self,
    start_time: str | None = None,
    end_time: str | None = None,
    max_waves_for_channels: int | None = None,
):
    from .daq_run import DAQRun

    if not os.path.exists(self.daq_root):
        logger.error("找不到目录 %s", self.daq_root)
        return self
    waves_to_scan = (
        self.max_waves_for_channels if max_waves_for_channels is None else max_waves_for_channels
    )
    start = self._parse_time_filter(start_time) if start_time else None
    end = self._parse_time_filter(end_time) if end_time else None
    self.runs = {}
    self.total_bytes = 0
    with os.scandir(self.daq_root) as entries:
        run_entries = sorted(
            (entry for entry in entries if entry.is_dir()), key=lambda entry: entry.name
        )
    for entry in run_entries:
        run = DAQRun(
            entry.name,
            entry.path,
            daq_adapter=self.daq_adapter,
            directory_layout=self.directory_layout,
            max_waves_for_channels=waves_to_scan,
        )
        if start or end:
            run_start, run_end = run.get_file_time_window()
            if (
                start
                and (run_end is None or run_end < start)
                or end
                and (run_start is None or run_start > end)
            ):
                continue
        self.runs[entry.name] = run
        self.total_bytes += run.total_bytes
    self._build_dataframe()
    return self


def scan_channel_files(self) -> None:
    if not os.path.isdir(self.raw_dir):
        return
    self._scan_with_layout() if self.layout is not None else self._scan_default()


def scan_default(self) -> None:
    with os.scandir(self.raw_dir) as entries:
        files = sorted(
            (
                entry
                for entry in entries
                if entry.is_file() and entry.name.endswith(self.ALLOWED_EXTS)
            ),
            key=lambda entry: entry.name,
        )
    for entry in files:
        stat = entry.stat()
        channel_match = self.CH_PATTERN.search(entry.name)
        if channel_match is None:
            continue
        index_match = self.IDX_PATTERN.search(entry.name)
        channel = int(channel_match.group(1))
        self.channel_files.setdefault(channel, []).append(
            {
                "filename": entry.name,
                "index": int(index_match.group(1)) if index_match else 0,
                "path": entry.path,
                "size_bytes": stat.st_size,
                "created_time": self._get_file_created_time(stat),
                "mtime": datetime.fromtimestamp(stat.st_mtime),
                "timetag_min": None,
                "timetag_max": None,
            }
        )
        self.channels.add(channel)
        self.total_bytes += stat.st_size
        self.file_count += 1


def scan_with_layout(self) -> None:
    for channel, files in self.layout.group_files_by_channel(Path(self.raw_dir)).items():
        for file_info in files:
            path = file_info["path"]
            stat = path.stat()
            self.channel_files.setdefault(channel, []).append(
                {
                    "filename": file_info["filename"],
                    "index": file_info["index"],
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "created_time": self._get_file_created_time(stat),
                    "mtime": datetime.fromtimestamp(stat.st_mtime),
                    "timetag_min": None,
                    "timetag_max": None,
                }
            )
            self.channels.add(channel)
            self.total_bytes += stat.st_size
            self.file_count += 1
    self._scan_internal_channels_and_boards()


__all__ = ["scan_all_runs", "scan_channel_files", "scan_default", "scan_with_layout"]
