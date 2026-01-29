# -*- coding: utf-8 -*-
"""
CAEN V1725 DAW_DEMO binary adapter.

Parses multi-channel waveforms stored in a single .bin file.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Tuple, Union

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

from .adapter import DAQAdapter, register_adapter
from .base import ColumnMapping, FormatReader, FormatSpec, TimestampUnit
from .directory import DirectoryLayout

export, __all__ = exporter()

logger = logging.getLogger(__name__)


def _bytes_to_int(data: bytes, bit: Optional[int] = None, start: int = 0) -> int:
    full_num = int.from_bytes(bytes=data, byteorder="little") >> start
    if bit is None:
        return full_num
    return full_num & ((1 << bit) - 1)


def _one_loc(num: int) -> List[int]:
    index_list = []
    bit = 0
    while num != 0:
        if num & 1:
            index_list.append(bit)
        bit += 1
        num >>= 1
    return index_list


@export
@dataclass
class V1725Wave:
    channel: int
    timestamp: int
    trunc: bool
    baseline: int
    waveform: np.ndarray


@export
class V1725Reader(FormatReader):
    """V1725 binary reader."""

    def __init__(self, spec: Optional[FormatSpec] = None):
        super().__init__(spec or V1725_SPEC)

    def iter_waves(self, file_paths: List[Union[str, Path]]) -> Iterator[V1725Wave]:
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                logger.warning("File not found: %s", path)
                continue

            with path.open(mode="rb") as f:
                while True:
                    event_header = f.read(4 << 2)
                    if not event_header:
                        break
                    if len(event_header) < (4 << 2):
                        logger.warning("Short event_header in %s", path)
                        break

                    channels = _one_loc(event_header[4] + (event_header[11] << 8))

                    for ch in channels:
                        ch_header = f.read(3 << 2)
                        if len(ch_header) < (3 << 2):
                            logger.warning("Short ch_header in %s", path)
                            break

                        ch_size = _bytes_to_int(ch_header[:3], 22)
                        sig_size = (ch_size - 3) << 2

                        time_stamp = _bytes_to_int(ch_header[4:10])
                        trunc = bool((ch_header[3] >> 6) & 1)
                        baseline = _bytes_to_int(ch_header[10:12])

                        raw_sig = f.read(sig_size)
                        if len(raw_sig) < sig_size:
                            logger.warning("Short waveform in %s", path)
                            break

                        sig = np.frombuffer(raw_sig, dtype=np.int16)
                        yield V1725Wave(
                            channel=ch,
                            timestamp=time_stamp,
                            trunc=trunc,
                            baseline=baseline,
                            waveform=sig,
                        )

    def read_file(self, file_path: Union[str, Path], is_first_file: bool = True) -> np.ndarray:
        _ = is_first_file
        waves = list(self.iter_waves([file_path]))
        return self._waves_to_array(waves)

    def read_files(
        self,
        file_paths: List[Union[str, Path]],
        show_progress: bool = False
    ) -> np.ndarray:
        _ = show_progress
        waves = list(self.iter_waves(file_paths))
        return self._waves_to_array(waves)

    def read_files_generator(
        self,
        file_paths: List[Union[str, Path]],
        chunk_size: int = 10
    ) -> Iterator[np.ndarray]:
        _ = chunk_size
        for file_path in file_paths:
            yield self.read_file(file_path)

    def extract_columns(self, data: np.ndarray):
        if data.size == 0:
            return {
                "board": np.array([], dtype=int),
                "channel": np.array([], dtype=int),
                "timestamp": np.array([], dtype=np.int64),
                "samples": np.array([]).reshape(0, 0),
                "baseline": np.array([], dtype=float),
            }

        if data.dtype.names:
            samples = np.array(data["wave"], dtype=object)
            return {
                "board": np.zeros(len(data), dtype=int),
                "channel": data["channel"].astype(int, copy=False),
                "timestamp": data["timestamp"].astype(np.int64, copy=False),
                "samples": samples,
                "baseline": data["baseline"].astype(float, copy=False),
            }
        return super().extract_columns(data)

    def validate_data(self, data: np.ndarray) -> bool:
        _ = data
        return True

    def _waves_to_array(self, waves: List[V1725Wave]) -> np.ndarray:
        if not waves:
            return np.array([]).reshape(0, 0)

        dtype = np.dtype(
            [
                ("channel", "i2"),
                ("timestamp", "i8"),
                ("baseline", "f8"),  # 使用 float64 以匹配 RECORD_DTYPE
                ("trunc", "b1"),
                ("wave", "O"),
            ]
        )
        arr = np.empty(len(waves), dtype=dtype)
        for i, wave in enumerate(waves):
            arr[i]["channel"] = wave.channel
            arr[i]["timestamp"] = wave.timestamp
            arr[i]["baseline"] = float(wave.baseline)  # 转换为 float64
            arr[i]["trunc"] = wave.trunc
            arr[i]["wave"] = wave.waveform
        return arr


@export
class V1725Spec:
    """V1725 format spec factory."""

    @staticmethod
    def create() -> FormatSpec:
        return FormatSpec(
            name="v1725_bin",
            version="0.1",
            columns=ColumnMapping(),
            timestamp_unit=TimestampUnit.NANOSECONDS,
            file_pattern="*.bin",
            header_rows_first_file=0,
            header_rows_other_files=0,
            delimiter="",
            expected_samples=None,
            sampling_rate_hz=250e6,
            metadata={
                "manufacturer": "CAEN",
                "model": "V1725",
                "description": "CAEN V1725 DAW_DEMO binary",
            },
        )


V1725_SPEC = export(V1725Spec.create(), name="V1725_SPEC")

V1725_LAYOUT = export(
    DirectoryLayout(
        name="v1725",
        raw_subdir="RAW",
        run_path_template="{data_root}/{run_name}/{raw_subdir}",
        file_glob_pattern="*.bin",
        file_extension=".bin",
        channel_regex=r"CH(\\d+)",
        file_index_regex=r"_(\\d+)\\.bin$",
        run_info_pattern="{run_name}_info.txt",
        metadata={
            "manufacturer": "CAEN",
            "model": "V1725",
            "description": "V1725 binary layout (defaulting to RAW/)",
        },
    ),
    name="V1725_LAYOUT",
)


@export
class V1725Adapter(DAQAdapter):
    def scan_run(self, data_root: str, run_name: str):
        try:
            groups = super().scan_run(data_root, run_name)
        except FileNotFoundError:
            return {}

        if groups:
            return groups

        raw_path = self.get_raw_path(data_root, run_name)
        files = self.directory_layout.list_files(raw_path)
        if not files:
            return {}
        return {0: files}


V1725_ADAPTER = export(
    V1725Adapter(
        name="v1725",
        format_reader=V1725Reader(),
        directory_layout=V1725_LAYOUT,
    ),
    name="V1725_ADAPTER",
)

register_adapter(V1725_ADAPTER)
