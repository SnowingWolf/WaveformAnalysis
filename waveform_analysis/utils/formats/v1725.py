"""
CAEN V1725 DAW_DEMO binary adapter.

Parses multi-channel waveforms stored in a single .bin file.
"""

from collections.abc import Iterator
from dataclasses import dataclass
import logging
from pathlib import Path
import re

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

from .adapter import DAQAdapter, register_adapter
from .base import ColumnMapping, FormatReader, FormatSpec, RawTimestampMode, TimestampUnit
from .directory import DirectoryLayout

export, __all__ = exporter()

logger = logging.getLogger(__name__)


def _bytes_to_int(data: bytes, bit: int | None = None, start: int = 0) -> int:
    full_num = int.from_bytes(bytes=data, byteorder="little") >> start
    if bit is None:
        return full_num
    return full_num & ((1 << bit) - 1)


def _one_loc(num: int) -> list[int]:
    """提取通道掩码中的活跃通道索引。"""
    index_list = []
    bit = 0
    while num != 0:
        if num & 1:
            index_list.append(bit)
        bit += 1
        num >>= 1
    return index_list


def _parse_channel_mask_vectorized(mask_low: int, mask_high: int) -> list[int]:
    """
    向量化解析通道掩码。

    Args:
        mask_low: 低 8 位掩码
        mask_high: 高 8 位掩码

    Returns:
        活跃通道索引列表
    """
    mask = mask_low | (mask_high << 8)
    return _one_loc(mask)


def _parse_channel_headers_vectorized(headers_data: np.ndarray) -> tuple:
    """
    向量化解析多个通道头。

    Args:
        headers_data: (N, 12) uint8 数组，包含 N 个通道头

    Returns:
        (ch_sizes, timestamps, truncs, baselines) 元组
    """
    if len(headers_data) == 0:
        return (
            np.array([], dtype=np.uint32),
            np.array([], dtype=np.uint64),
            np.array([], dtype=bool),
            np.array([], dtype=np.uint16),
        )

    # 提取 ch_size（前 3 字节，22 位）
    ch_sizes = (
        headers_data[:, 0].astype(np.uint32)
        | (headers_data[:, 1].astype(np.uint32) << 8)
        | ((headers_data[:, 2].astype(np.uint32) & 0x3F) << 16)
    )

    # 提取 timestamp（字节 4-9，48 位）
    timestamps = (
        headers_data[:, 4].astype(np.uint64)
        | (headers_data[:, 5].astype(np.uint64) << 8)
        | (headers_data[:, 6].astype(np.uint64) << 16)
        | (headers_data[:, 7].astype(np.uint64) << 24)
        | (headers_data[:, 8].astype(np.uint64) << 32)
        | (headers_data[:, 9].astype(np.uint64) << 40)
    )

    # 提取 trunc 标志（字节 3，位 6）
    truncs = ((headers_data[:, 3] >> 6) & 1).astype(bool)

    # 提取 baseline（字节 10-11）
    baselines = headers_data[:, 10].astype(np.uint16) | (headers_data[:, 11].astype(np.uint16) << 8)

    return ch_sizes, timestamps, truncs, baselines


def _one_loc_fast(num: int) -> np.ndarray:
    """快速提取通道掩码中的活动通道（向量化版本）。"""
    if num == 0:
        return np.array([], dtype=np.int32)
    # 使用 NumPy 位操作
    bits = np.arange(16, dtype=np.int32)
    mask = (num >> bits) & 1
    return bits[mask.astype(bool)]


@export
@dataclass
class V1725Wave:
    board: int
    channel: int
    timestamp: int
    trunc: bool
    baseline: int
    waveform: np.ndarray


@export
class V1725Reader(FormatReader):
    """V1725 binary reader with optimized batch processing."""

    def __init__(self, spec: FormatSpec | None = None, use_optimized: bool = True):
        super().__init__(spec or V1725_SPEC)
        self.use_optimized = use_optimized
        self._buffer_size = 256 * 1024  # 256KB buffer for batch reading

    def _read_events_batch(self, f, board_id: int, max_events: int = 100) -> list[V1725Wave] | None:
        """
        批量读取事件数据，使用向量化解析减少 Python 循环开销。

        Args:
            f: 文件对象
            board_id: 板卡 ID
            max_events: 最多读取的事件数

        Returns:
            V1725Wave 对象列表，如果到达文件末尾则返回 None
        """
        # 读取大块数据
        buffer = f.read(self._buffer_size)
        if not buffer:
            return None

        # 转换为 NumPy 数组以便高效处理
        data = np.frombuffer(buffer, dtype=np.uint8)

        waves = []
        offset = 0
        events_read = 0

        # 收集所有通道头以便批量解析
        channel_headers_list = []
        channel_info_list = []  # 存储 (channel_idx, wave_start, wave_size)

        while events_read < max_events and offset + 16 <= len(data):
            # 解析事件头（16 字节）
            event_header = data[offset : offset + 16]

            # 提取通道掩码
            channels = _parse_channel_mask_vectorized(int(event_header[4]), int(event_header[11]))

            offset += 16

            # 收集该事件的所有通道头
            event_channel_headers = []
            event_channel_info = []

            for ch in channels:
                if offset + 12 > len(data):
                    # 缓冲区不足，回退并退出
                    f.seek(f.tell() - (len(data) - offset))
                    # 处理已收集的通道头
                    if channel_headers_list:
                        waves.extend(
                            self._process_channel_batch(
                                channel_headers_list, channel_info_list, data, board_id
                            )
                        )
                    return waves if waves else None

                # 收集通道头
                ch_header = data[offset : offset + 12]
                event_channel_headers.append(ch_header)

                # 快速提取通道大小以确定波形数据位置
                ch_size = (
                    int(ch_header[0])
                    | (int(ch_header[1]) << 8)
                    | ((int(ch_header[2]) & 0x3F) << 16)
                )
                sig_size = (ch_size - 3) << 2

                if offset + 12 + sig_size > len(data):
                    # 波形数据不完整，回退并退出
                    f.seek(f.tell() - (len(data) - offset))
                    if channel_headers_list:
                        waves.extend(
                            self._process_channel_batch(
                                channel_headers_list, channel_info_list, data, board_id
                            )
                        )
                    return waves if waves else None

                # 记录通道信息
                event_channel_info.append((ch, offset + 12, sig_size))

                offset += 12 + sig_size

            # 添加到批量处理列表
            channel_headers_list.extend(event_channel_headers)
            channel_info_list.extend(event_channel_info)

            events_read += 1

        # 批量处理所有收集的通道头
        if channel_headers_list:
            waves.extend(
                self._process_channel_batch(channel_headers_list, channel_info_list, data, board_id)
            )

        # 回退未处理的数据
        if offset < len(data):
            f.seek(f.tell() - (len(data) - offset))

        return waves if waves else None

    def _process_channel_batch(
        self, channel_headers: list, channel_info: list, data: np.ndarray, board_id: int
    ) -> list[V1725Wave]:
        """
        批量处理通道头和波形数据。

        Args:
            channel_headers: 通道头列表
            channel_info: 通道信息列表 (channel_idx, wave_start, wave_size)
            data: 原始数据缓冲区
            board_id: 板卡 ID

        Returns:
            V1725Wave 对象列表
        """
        # 将通道头转换为 NumPy 数组
        headers_array = np.array(channel_headers, dtype=np.uint8)

        # 向量化解析通道头
        ch_sizes, timestamps, truncs, baselines = _parse_channel_headers_vectorized(headers_array)

        # 构建 V1725Wave 对象
        waves = []
        for i, (ch, wave_start, wave_size) in enumerate(channel_info):
            # 提取波形数据
            wave_data = data[wave_start : wave_start + wave_size]
            sig = np.frombuffer(wave_data.tobytes(), dtype=np.int16)

            waves.append(
                V1725Wave(
                    board=board_id,
                    channel=ch,
                    timestamp=int(timestamps[i]),
                    trunc=bool(truncs[i]),
                    baseline=int(baselines[i]),
                    waveform=sig,
                )
            )

        return waves

    @staticmethod
    def _extract_board_from_path(path: Path) -> int:
        # 从文件名末尾往前匹配，避免匹配到运行名称中的 _b
        # 匹配 _raw_bN_segM.bin 或 _bN_segM.bin 格式
        match = re.search(r"_b(\d+)_seg\d+\.bin$", path.name, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))

        # 回退：匹配传统格式 CHN_M.bin（默认板卡 0）
        if re.match(r"CH\d+_\d+\.bin$", path.name, flags=re.IGNORECASE):
            return 0

        # 最后回退：返回 0
        return 0

    def _iter_waves_legacy(self, file_paths: list[str | Path]) -> Iterator[V1725Wave]:
        """原始的逐事件读取实现（用于回退）。"""
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                logger.warning("File not found: %s", path)
                continue
            board_id = self._extract_board_from_path(path)

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
                            board=board_id,
                            channel=ch,
                            timestamp=time_stamp,
                            trunc=trunc,
                            baseline=baseline,
                            waveform=sig,
                        )

    def _iter_waves_optimized(self, file_paths: list[str | Path]) -> Iterator[V1725Wave]:
        """优化的批量读取实现。"""
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                logger.warning("File not found: %s", path)
                continue
            board_id = self._extract_board_from_path(path)

            with path.open(mode="rb") as f:
                while True:
                    batch = self._read_events_batch(f, board_id, max_events=100)
                    if batch is None:
                        break
                    yield from batch

    def iter_waves(self, file_paths: list[str | Path]) -> Iterator[V1725Wave]:
        """
        迭代读取 V1725 波形数据。

        自动选择优化路径或回退到原始实现。

        Args:
            file_paths: 文件路径列表

        Yields:
            V1725Wave 对象
        """
        if self.use_optimized:
            try:
                yield from self._iter_waves_optimized(file_paths)
            except Exception as e:
                logger.warning(
                    "Optimized V1725 reader failed (%s), falling back to legacy implementation", e
                )
                yield from self._iter_waves_legacy(file_paths)
        else:
            yield from self._iter_waves_legacy(file_paths)

    def read_file(self, file_path: str | Path, is_first_file: bool = True) -> np.ndarray:
        _ = is_first_file
        waves = list(self.iter_waves([file_path]))
        return self._waves_to_array(waves)

    def read_files(
        self,
        file_paths: list[str | Path],
        show_progress: bool = False,
        *,
        chunksize: int | None = None,
        n_jobs: int | None = None,
        use_process_pool: bool = False,
        parse_engine: str | None = "auto",
    ) -> np.ndarray:
        _ = (show_progress, chunksize, n_jobs, use_process_pool, parse_engine)
        waves = list(self.iter_waves(file_paths))
        return self._waves_to_array(waves)

    def read_files_generator(
        self,
        file_paths: list[str | Path],
        chunk_size: int = 10,
        *,
        chunksize: int | None = None,
        n_jobs: int | None = None,
        use_process_pool: bool = False,
        parse_engine: str | None = "auto",
        show_progress: bool = False,
    ) -> Iterator[np.ndarray]:
        _ = (chunk_size, chunksize, n_jobs, use_process_pool, parse_engine, show_progress)
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
                "board": (
                    data["board"].astype(int, copy=False)
                    if "board" in data.dtype.names
                    else np.zeros(len(data), dtype=int)
                ),
                "channel": data["channel"].astype(int, copy=False),
                "timestamp": data["timestamp"].astype(np.int64, copy=False),
                "samples": samples,
                "baseline": data["baseline"].astype(float, copy=False),
            }
        return super().extract_columns(data)

    def validate_data(self, data: np.ndarray) -> bool:
        _ = data
        return True

    def _waves_to_array(self, waves: list[V1725Wave]) -> np.ndarray:
        if not waves:
            return np.array([]).reshape(0, 0)

        dtype = np.dtype(
            [
                ("board", "i2"),
                ("channel", "i2"),
                ("timestamp", "i8"),
                ("baseline", "f8"),  # 使用 float64 以匹配 RECORD_DTYPE
                ("trunc", "b1"),
                ("wave", "O"),
            ]
        )
        arr = np.empty(len(waves), dtype=dtype)
        for i, wave in enumerate(waves):
            arr[i]["board"] = wave.board
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
            raw_timestamp_mode=RawTimestampMode.SAMPLE_INDEX,
            file_pattern="*.bin",
            header_rows_first_file=0,
            header_rows_other_files=0,
            delimiter="",
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
        # Support both legacy CH naming and DAW_DEMO bX/segX naming:
        # - CH0_0.bin
        # - test_raw_b0_seg0.bin
        channel_regex=r"(?:CH|_b)(\d+)",
        file_index_regex=r"(?:_seg|_)(\d+)\.bin$",
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
