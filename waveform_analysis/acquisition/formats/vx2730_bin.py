"""
CAEN VX2730 CoMPASS 二进制 (.BIN) 适配器

本模块包含 CoMPASS 保存的 VX2730 二进制列表文件的配置和实现：
- VX2730_BIN_SPEC: 格式规范（列映射、时间戳单位等）
- VX2730BinReader: 二进制读取器，输出与 VX2730 CSV 相同列布局的二维数组
- VX2730_BIN_LAYOUT: 目录结构配置（大小写不敏感的 .BIN，支持单文件多通道）
- VX2730_BIN_ADAPTER: 完整适配器

格式（CoMPASS User Manual UM5960 §5.4，小端序）:
- 文件头: uint16 ``0xCAEx``，仅出现一次；x 的各位表示事件中包含的字段
  - bit0: Energy (ch, uint16)
  - bit1: Energy (keV/MeV, float64)
  - bit2: Energy short (ch, uint16)
  - bit3: 波形（wave code uint8 + 采样数 uint32 + uint16 × N）
- 每个事件: BOARD u16, CHANNEL u16, TIMETAG u64 (ps), [ENERGY u16],
  [ENERGY_CAL f64], [ENERGYSHORT u16], FLAGS u32, [WAVE_CODE u8, N u32, SAMPLES u16 × N]

读取器输出的二维 int64 数组列布局与 CSV 一致:
``BOARD;CHANNEL;TIMETAG;ENERGY;ENERGYSHORT;FLAGS;PROBE_CODE;SAMPLES[7:]``
（缺失字段填 0；刻度后能量不输出）。

Examples:
    >>> from waveform_analysis.utils.formats import get_adapter
    >>> adapter = get_adapter("vx2730_bin")
    >>> channel_files = adapter.scan_run("DAQ", "run_001")
    >>> data = adapter.load_channel("DAQ", "run_001", channel=0)
"""

from collections.abc import Iterator
from dataclasses import dataclass
import logging
from pathlib import Path
import re

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

from .adapter import DAQAdapter
from .base import ColumnMapping, FormatReader, FormatSpec, RawTimestampMode, TimestampUnit
from .directory import DirectoryLayout

export, __all__ = exporter()

logger = logging.getLogger(__name__)

_HEADER_MAGIC = 0xCAE
_HEADER_SIZE = 2
_HAS_ENERGY = 0x1
_HAS_ENERGY_CAL = 0x2
_HAS_ENERGY_SHORT = 0x4
_HAS_WAVEFORM = 0x8
# BOARD, CHANNEL, TIMETAG, ENERGY, ENERGYSHORT, FLAGS, PROBE_CODE
_N_META_COLUMNS = 7


# ============================================================================
# 二进制解析工具
# ============================================================================


def _read_header(path: Path) -> int | None:
    """读取并校验文件头；文件为空时返回 None。"""
    with path.open("rb") as handle:
        raw = handle.read(_HEADER_SIZE)
    if len(raw) == 0:
        return None
    if len(raw) < _HEADER_SIZE:
        raise ValueError(f"VX2730 BIN file too short for header: {path}")
    header = int.from_bytes(raw, byteorder="little")
    if header >> 4 != _HEADER_MAGIC:
        raise ValueError(f"Invalid VX2730 BIN header 0x{header:04X} in {path}; expected 0xCAEx")
    return header


def _event_dtype(header: int, n_samples: int) -> np.dtype:
    """根据文件头各位构造单个事件的 packed 结构化 dtype。"""
    fields: list[tuple] = [
        ("board", "<u2"),
        ("channel", "<u2"),
        ("timestamp", "<u8"),
    ]
    if header & _HAS_ENERGY:
        fields.append(("energy", "<u2"))
    if header & _HAS_ENERGY_CAL:
        fields.append(("energy_cal", "<f8"))
    if header & _HAS_ENERGY_SHORT:
        fields.append(("energy_short", "<u2"))
    fields.append(("flags", "<u4"))
    if header & _HAS_WAVEFORM:
        fields.append(("wave_code", "u1"))
        fields.append(("n_samples", "<u4"))
        fields.append(("samples", "<u2", (n_samples,)))
    return np.dtype(fields)


def _resolve_event_dtype(path: Path, header: int, file_size: int) -> np.dtype:
    """确定文件的事件 dtype，并校验文件大小与事件大小对齐。"""
    n_samples = 0
    if header & _HAS_WAVEFORM:
        prefix = _event_dtype(header & ~_HAS_WAVEFORM, 0)
        # wave_code (u1) 之后是 n_samples (u4)
        n_offset = _HEADER_SIZE + prefix.itemsize + 1
        if file_size < n_offset + 4:
            raise ValueError(f"Truncated VX2730 BIN event at byte offset {_HEADER_SIZE} in {path}")
        with path.open("rb") as handle:
            handle.seek(n_offset)
            n_samples = int.from_bytes(handle.read(4), byteorder="little")

    dtype = _event_dtype(header, n_samples)
    payload = file_size - _HEADER_SIZE
    remainder = payload % dtype.itemsize
    if remainder:
        n_complete = payload // dtype.itemsize
        raise ValueError(
            f"VX2730 BIN file {path} has {remainder} trailing bytes after "
            f"{n_complete} complete events (event size {dtype.itemsize} bytes); "
            "file is truncated or record length is not constant"
        )
    return dtype


def _events_to_raw_array(events: np.ndarray, header: int) -> np.ndarray:
    """将结构化事件切片转换为与 CSV 列布局一致的二维 int64 数组。"""
    n_events = len(events)
    names = events.dtype.names
    n_samples = events.dtype["samples"].shape[0] if "samples" in names else 0

    if header & _HAS_WAVEFORM and n_events:
        counts = events["n_samples"]
        if np.any(counts != n_samples):
            bad = int(counts[np.flatnonzero(counts != n_samples)[0]])
            raise ValueError(
                f"Inconsistent VX2730 BIN waveform length: expected {n_samples}, found {bad}"
            )

    out = np.zeros((n_events, _N_META_COLUMNS + n_samples), dtype=np.int64)
    out[:, 0] = events["board"]
    out[:, 1] = events["channel"]
    out[:, 2] = events["timestamp"].astype(np.int64)
    if "energy" in names:
        out[:, 3] = events["energy"]
    if "energy_short" in names:
        out[:, 4] = events["energy_short"]
    out[:, 5] = events["flags"]
    if "wave_code" in names:
        out[:, 6] = events["wave_code"]
    if n_samples:
        out[:, _N_META_COLUMNS:] = events["samples"]
    return out


# ============================================================================
# VX2730 BIN 格式规范
# ============================================================================


@export
class VX2730BinSpec:
    """VX2730 BIN 格式规范的工厂类"""

    @staticmethod
    def create() -> FormatSpec:
        """创建 VX2730 BIN 格式规范"""
        return FormatSpec(
            name="vx2730_bin",
            version="1.0",
            columns=ColumnMapping(
                board=0,
                channel=1,
                timestamp=2,
                samples_start=_N_META_COLUMNS,
                samples_end=None,
                baseline_start=_N_META_COLUMNS,
                baseline_end=_N_META_COLUMNS + 40,  # 前 40 个采样点用于基线计算
            ),
            timestamp_unit=TimestampUnit.PICOSECONDS,
            raw_timestamp_mode=RawTimestampMode.UNIT,
            file_pattern="*.BIN",
            header_rows_first_file=0,
            header_rows_other_files=0,
            delimiter="",
            sampling_rate_hz=500e6,
            metadata={
                "manufacturer": "CAEN",
                "model": "VX2730",
                "description": "CAEN VX2730 CoMPASS 二进制列表格式",
            },
        )


VX2730_BIN_SPEC = export(VX2730BinSpec.create(), name="VX2730_BIN_SPEC")


# ============================================================================
# VX2730 BIN 目录布局
# ============================================================================


def _natural_sort_key(name: str) -> list:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


@export
@dataclass
class VX2730BinLayout(DirectoryLayout):
    """CoMPASS BIN 目录布局

    - 后缀 ``.bin`` 大小写不敏感（CoMPASS 输出 ``.BIN``）
    - 文件名含 ``CH<n>`` 时按通道分组；否则视为单文件多通道，归入分组 0，
      真实 board/channel 由事件内容给出
    - 组内按文件名自然排序（``run.BIN`` < ``run_1.BIN`` < ``run_2.BIN`` < ``run_10.BIN``）
    """

    def list_files(self, raw_path: Path) -> list[Path]:
        if not raw_path.exists():
            return []
        suffix = self.file_extension.lower()
        files = [p for p in raw_path.iterdir() if p.is_file() and p.suffix.lower() == suffix]
        return sorted(files, key=lambda p: _natural_sort_key(p.name))

    def group_files_by_channel(self, raw_path: Path) -> dict[int, list[dict]]:
        groups: dict[int, list[Path]] = {}
        for path in self.list_files(raw_path):
            ch = self.extract_channel(path.name)
            groups.setdefault(0 if ch is None else ch, []).append(path)
        return {
            ch: [
                {"path": path, "index": idx, "filename": path.name}
                for idx, path in enumerate(paths)
            ]
            for ch, paths in groups.items()
        }


VX2730_BIN_LAYOUT = export(
    VX2730BinLayout(
        name="vx2730_bin",
        raw_subdir="RAW",
        run_path_template="{data_root}/{run_name}/{raw_subdir}",
        file_glob_pattern="*.BIN",
        file_extension=".bin",
        channel_regex=r"CH(\d+)",
        file_index_regex=r"_(\d+)\.BIN$",
        run_info_pattern="{run_name}_info.txt",
        metadata={
            "manufacturer": "CAEN",
            "model": "VX2730",
            "description": "CoMPASS VX2730 二进制目录布局（RAW/*.BIN）",
        },
    ),
    name="VX2730_BIN_LAYOUT",
)


# ============================================================================
# VX2730 BIN 格式读取器
# ============================================================================


@export
class VX2730BinReader(FormatReader):
    """VX2730 CoMPASS BIN 格式读取器

    使用 memmap 分块读取，输出与 VX2730 CSV 相同列布局的二维 int64 数组，
    因此可直接复用通用 records 构建链路。

    Args:
        spec: 格式规范（默认使用 VX2730_BIN_SPEC）
        events_per_chunk: 生成器模式下每块事件数（控制内存占用）

    Examples:
        >>> reader = VX2730BinReader()
        >>> for arr in reader.read_files_generator(["SDataR_run.BIN"]):
        ...     print(arr.shape)
    """

    def __init__(self, spec: FormatSpec | None = None, events_per_chunk: int = 20_000):
        super().__init__(spec or VX2730_BIN_SPEC)
        if events_per_chunk <= 0:
            raise ValueError("events_per_chunk must be positive")
        self.events_per_chunk = int(events_per_chunk)

    def _iter_raw_chunks(self, file_path: str | Path) -> Iterator[np.ndarray]:
        path = Path(file_path)
        if not path.exists():
            logger.warning("文件不存在: %s", path)
            return
        header = _read_header(path)
        if header is None:
            logger.debug("跳过空文件: %s", path)
            return
        file_size = path.stat().st_size
        if file_size == _HEADER_SIZE:
            return

        dtype = _resolve_event_dtype(path, header, file_size)
        n_events = (file_size - _HEADER_SIZE) // dtype.itemsize
        events = np.memmap(path, dtype=dtype, mode="r", offset=_HEADER_SIZE, shape=(n_events,))
        try:
            for start in range(0, n_events, self.events_per_chunk):
                yield _events_to_raw_array(events[start : start + self.events_per_chunk], header)
        finally:
            del events

    def read_file(self, file_path: str | Path, is_first_file: bool = True) -> np.ndarray:
        _ = is_first_file
        chunks = list(self._iter_raw_chunks(file_path))
        if not chunks:
            return np.array([]).reshape(0, 0)
        return chunks[0] if len(chunks) == 1 else np.vstack(chunks)

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
        chunks = [chunk for fp in file_paths for chunk in self._iter_raw_chunks(fp)]
        if not chunks:
            return np.array([]).reshape(0, 0)
        widths = {chunk.shape[1] for chunk in chunks}
        if len(widths) != 1:
            raise ValueError(f"VX2730 BIN files have different waveform lengths: {sorted(widths)}")
        return chunks[0] if len(chunks) == 1 else np.vstack(chunks)

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
        """逐文件、逐块（``events_per_chunk`` 个事件）产出二维数组。

        ``chunk_size`` 等 CSV 相关参数仅为接口兼容而接收。
        """
        _ = (chunk_size, chunksize, n_jobs, use_process_pool, parse_engine, show_progress)
        for file_path in file_paths:
            for chunk in self._iter_raw_chunks(file_path):
                if chunk.size:
                    yield chunk

    def count_total_rows(self, file_paths: list[str | Path]) -> int:
        """根据文件大小计算事件总数（不读取波形）。"""
        total = 0
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                continue
            header = _read_header(path)
            file_size = path.stat().st_size
            if header is None or file_size == _HEADER_SIZE:
                continue
            dtype = _resolve_event_dtype(path, header, file_size)
            total += (file_size - _HEADER_SIZE) // dtype.itemsize
        return total

    def read_files_streaming(
        self,
        file_paths: list[str | Path],
        output_dtype: np.dtype,
        output_path: Path,
        structurizer,
        show_progress: bool = False,
        *,
        chunksize: int | None = None,
        n_jobs: int | None = None,
        use_process_pool: bool = False,
        parse_engine: str | None = "auto",
    ) -> np.memmap:
        """流式读取：逐块结构化写入 memmap（按事件块而非按文件）。"""
        _ = (chunksize, n_jobs, use_process_pool, parse_engine)
        if not file_paths:
            return np.memmap(output_path, dtype=output_dtype, mode="w+", shape=(0,))
        total_rows = self.count_total_rows(file_paths)
        if total_rows == 0:
            return np.memmap(output_path, dtype=output_dtype, mode="w+", shape=(0,))
        output = np.memmap(output_path, dtype=output_dtype, mode="w+", shape=(total_rows,))
        offset = 0
        for chunk in self.read_files_generator(file_paths, show_progress=show_progress):
            offset += int(structurizer(chunk, output, offset))
        output.flush()
        if offset < total_rows:
            return np.memmap(output_path, dtype=output_dtype, mode="r+", shape=(offset,))
        return output


# ============================================================================
# VX2730 BIN 完整适配器
# ============================================================================

VX2730_BIN_ADAPTER = export(
    DAQAdapter(
        name="vx2730_bin",
        format_reader=VX2730BinReader(VX2730_BIN_SPEC),
        directory_layout=VX2730_BIN_LAYOUT,
    ),
    name="VX2730_BIN_ADAPTER",
)
