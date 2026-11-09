"""
DAQ 完整适配器

结合格式读取器和目录布局，提供完整的 DAQ 数据访问接口。

DAQAdapter 封装了：
- FormatReader: 文件格式读取
- DirectoryLayout: 目录结构解析

Examples:
    >>> from waveform_analysis.utils.formats import get_adapter
    >>> adapter = get_adapter("vx2730")
    >>>
    >>> # 扫描目录
    >>> channel_files = adapter.scan_run("DAQ", "run_001")
    >>> print(f"找到 {len(channel_files)} 个文件组")
    >>>
    >>> # 加载单个通道
    >>> data = adapter.load_channel("DAQ", "run_001", channel=0, board=0)
    >>> print(f"加载 {len(data)} 条记录")
    >>>
    >>> # 提取并转换
    >>> extracted = adapter.extract_and_convert(data)
    >>> print(f"时间戳范围: {extracted['timestamp'].min()} - {extracted['timestamp'].max()}")
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

from .base import FormatReader, FormatSpec
from .directory import DirectoryLayout

export, __all__ = exporter()


@export
@dataclass
class DAQAdapter:
    """完整的 DAQ 适配器

    结合格式读取器和目录布局，提供统一的 DAQ 数据访问接口。

    Attributes:
        name: 适配器名称
        format_reader: 格式读取器实例
        directory_layout: 目录布局配置

    Examples:
        >>> from waveform_analysis.utils.formats import (
        ...     DAQAdapter, VX2730Reader, VX2730_LAYOUT
        ... )
        >>> adapter = DAQAdapter(
        ...     name="my_adapter",
        ...     format_reader=VX2730Reader(),
        ...     directory_layout=VX2730_LAYOUT,
        ... )
    """

    name: str
    format_reader: FormatReader
    directory_layout: DirectoryLayout

    @property
    def format_spec(self) -> FormatSpec:
        """获取格式规范"""
        return self.format_reader.spec

    @property
    def layout(self) -> DirectoryLayout:
        """获取目录布局（别名）"""
        return self.directory_layout

    @property
    def sampling_rate_hz(self) -> float | None:
        """获取采样率（Hz）"""
        return self.format_spec.sampling_rate_hz

    def get_raw_path(self, data_root: str, run_name: str) -> Path:
        """获取原始数据目录

        Args:
            data_root: 数据根目录
            run_name: 运行名称

        Returns:
            原始数据目录路径
        """
        return self.directory_layout.get_raw_path(data_root, run_name)

    def get_run_path(self, data_root: str, run_name: str) -> Path:
        """获取运行根目录

        Args:
            data_root: 数据根目录
            run_name: 运行名称

        Returns:
            运行根目录路径
        """
        return self.directory_layout.get_run_path(data_root, run_name)

    def scan_run(self, data_root: str, run_name: str) -> dict[int, list[Path]]:
        """扫描运行目录，返回按目录布局分组的文件

        Args:
            data_root: 数据根目录
            run_name: 运行名称

        Returns:
            文件组路径字典: {group_id: [path1, path2, ...]}。组键来自文件名，
            不保证是物理通道；真实 board/channel 以记录内容为准。

        Raises:
            FileNotFoundError: 如果目录不存在
        """
        raw_path = self.get_raw_path(data_root, run_name)

        if not raw_path.exists():
            raise FileNotFoundError(f"目录不存在: {raw_path}")

        groups = self.directory_layout.group_files_by_channel(raw_path)

        # 保留目录布局的文件组键，不将其解释为物理通道。
        return {ch: [f["path"] for f in files] for ch, files in groups.items()}

    def scan_run_detailed(self, data_root: str, run_name: str) -> dict[int, list[dict]]:
        """扫描运行目录，返回详细的文件信息

        Args:
            data_root: 数据根目录
            run_name: 运行名称

        Returns:
            按目录布局分组的详细文件信息（组键不是物理通道契约）:
            {
                group_id: [
                    {'path': Path, 'index': int, 'filename': str},
                    ...
                ],
                ...
            }

        Raises:
            FileNotFoundError: 如果目录不存在
        """
        raw_path = self.get_raw_path(data_root, run_name)

        if not raw_path.exists():
            raise FileNotFoundError(f"目录不存在: {raw_path}")

        return self.directory_layout.group_files_by_channel(raw_path)

    def _iter_run_chunks(
        self,
        data_root: str,
        run_name: str,
        chunk_size: int = 10,
        show_progress: bool = False,
    ) -> Iterator[tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """读取唯一候选文件，保留组内顺序和各组的首文件读取策略。"""
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        seen: set[Path] = set()
        for paths in self.scan_run(data_root, run_name).values():
            unique_paths = []
            for path in paths:
                if path not in seen:
                    seen.add(path)
                    unique_paths.append(path)
            if not unique_paths:
                continue
            for data in self.format_reader.read_files_generator(
                unique_paths, chunk_size, show_progress=show_progress
            ):
                if len(data) == 0:
                    continue
                if data.dtype.names:
                    boards, channels = data["board"], data["channel"]
                else:
                    columns = self.format_spec.columns
                    boards, channels = data[:, columns.board], data[:, columns.channel]
                yield data, boards, channels

    def load_channel(
        self,
        data_root: str,
        run_name: str,
        channel: int,
        show_progress: bool = False,
        *,
        board: int,
    ) -> np.ndarray:
        """按实际记录中的板卡和通道加载原始数据。

        ``board`` 必须显式传入。文件组键不参与通道选择，返回值保留读取器的
        dtype、二维或结构化布局及原生时间戳，不做单位转换。

        Raises:
            ValueError: 运行中没有该 (board, channel) 的记录，包括空运行。
            FileNotFoundError: 运行目录不存在。
        """
        chunks = []
        for data, boards, channels in self._iter_run_chunks(
            data_root, run_name, show_progress=show_progress
        ):
            selected = (boards == board) & (channels == channel)
            if np.any(selected):
                chunks.append(data[selected])
        if not chunks:
            raise ValueError(f"通道 ({board}, {channel}) 不存在：运行中没有该硬件通道的记录")
        return np.concatenate(chunks)

    def load_all_channels(
        self,
        data_root: str,
        run_name: str,
        *,
        show_progress: bool = False,
    ) -> dict[tuple[int, int], np.ndarray]:
        """一次读取所有文件组，按实际记录的 (board, channel) 返回原始数组。

        仅包含有记录的硬件通道，空运行返回空字典；不填充缺失通道。每个通道
        保持文件扫描和记录顺序，dtype、数组布局和时间戳单位由读取器决定。
        """
        chunks: dict[tuple[int, int], list[np.ndarray]] = {}
        for data, boards, channels in self._iter_run_chunks(
            data_root, run_name, show_progress=show_progress
        ):
            keys, inverse = np.unique(
                np.column_stack((boards, channels)), axis=0, return_inverse=True
            )
            for index, (board, channel) in enumerate(keys):
                key = (int(board), int(channel))
                chunks.setdefault(key, []).append(data[inverse == index])
        return {key: np.concatenate(parts) for key, parts in chunks.items()}

    def load_channel_generator(
        self,
        data_root: str,
        run_name: str,
        channel: int,
        chunk_size: int = 10,
        *,
        board: int,
    ) -> Iterator[np.ndarray]:
        """逐块筛选指定 (board, channel)，只生成非空的原始记录数组。

        ``board`` 必须显式传入。遍历所有候选文件后若没有匹配记录则抛出
        ValueError；目录不存在时抛出 FileNotFoundError。chunk_size 必须为正。
        """
        found = False
        for data, boards, channels in self._iter_run_chunks(data_root, run_name, chunk_size):
            selected = (boards == board) & (channels == channel)
            if np.any(selected):
                found = True
                yield data[selected]
        if not found:
            raise ValueError(f"通道 ({board}, {channel}) 不存在：运行中没有该硬件通道的记录")

    def extract_columns(self, data: np.ndarray) -> dict[str, np.ndarray]:
        """从数据中提取各列

        Args:
            data: 数据数组

        Returns:
            包含各列的字典
        """
        return self.format_reader.extract_columns(data)

    def normalize_timestamp_to_ps(
        self,
        timestamps: np.ndarray,
        dt_ns: int | None = None,
    ) -> np.ndarray:
        """将原生时间戳统一转换为标准 ps。"""
        return self.format_spec.normalize_timestamp_to_ps(timestamps, dt_ns=dt_ns)

    def extract_and_convert(self, data: np.ndarray) -> dict[str, np.ndarray]:
        """提取列并转换时间戳为皮秒

        为了向后兼容，时间戳转换为皮秒（而不是纳秒）。

        Args:
            data: 数据数组

        Returns:
            包含各列的字典，时间戳已转换为皮秒
        """
        extracted = self.format_reader.extract_columns(data)
        extracted["timestamp"] = self.normalize_timestamp_to_ps(extracted["timestamp"])
        return extracted

    def extract_and_convert_ns(self, data: np.ndarray) -> dict[str, np.ndarray]:
        """提取列并转换时间戳为纳秒

        Args:
            data: 数据数组

        Returns:
            包含各列的字典，时间戳已转换为纳秒
        """
        extracted = self.format_reader.extract_columns(data)
        extracted["timestamp"] = self.normalize_timestamp_to_ps(extracted["timestamp"]) // np.int64(
            1000
        )
        return extracted

    def validate_data(self, data: np.ndarray) -> bool:
        """验证数据是否符合格式规范

        Args:
            data: 数据数组

        Returns:
            验证是否通过
        """
        return self.format_reader.validate_data(data)

    def get_file_epoch(self, file_path: Path) -> int:
        """获取文件创建时间作为 epoch (纳秒)

        Args:
            file_path: 文件路径

        Returns:
            文件创建时间的 Unix 时间戳（纳秒）

        Examples:
            >>> adapter = get_adapter("vx2730")
            >>> epoch_ns = adapter.get_file_epoch(Path("data.csv"))
            >>> print(f"Epoch: {epoch_ns} ns")
        """
        stat = file_path.stat()
        # 优先使用 st_birthtime (macOS)，否则用 st_mtime
        ctime = getattr(stat, "st_birthtime", stat.st_mtime)
        return int(ctime * 1e9)  # 秒 → 纳秒


# 适配器注册表
_ADAPTER_REGISTRY: dict[str, DAQAdapter] = {}


@export
def register_adapter(adapter: DAQAdapter) -> None:
    """注册 DAQ 适配器

    Args:
        adapter: DAQ 适配器实例

    Examples:
        >>> adapter = DAQAdapter(name="my_adapter", ...)
        >>> register_adapter(adapter)
    """
    _ADAPTER_REGISTRY[adapter.name] = adapter


@export
def get_adapter(name: str) -> DAQAdapter:
    """获取 DAQ 适配器

    Args:
        name: 适配器名称

    Returns:
        DAQ 适配器实例

    Raises:
        ValueError: 如果适配器未注册

    Examples:
        >>> adapter = get_adapter("vx2730")
        >>> data = adapter.load_channel("DAQ", "run_001", channel=0, board=0)
    """
    if name not in _ADAPTER_REGISTRY:
        available = list(_ADAPTER_REGISTRY.keys())
        raise ValueError(f"未知适配器 '{name}'。可用适配器: {available}")
    return _ADAPTER_REGISTRY[name]


@export
def list_adapters() -> list[str]:
    """列出所有已注册的适配器

    Returns:
        适配器名称列表
    """
    return list(_ADAPTER_REGISTRY.keys())


@export
def is_adapter_registered(name: str) -> bool:
    """检查适配器是否已注册

    Args:
        name: 适配器名称

    Returns:
        是否已注册
    """
    return name in _ADAPTER_REGISTRY


@export
def unregister_adapter(name: str) -> bool:
    """注销一个适配器

    Args:
        name: 适配器名称

    Returns:
        是否成功注销
    """
    if name in _ADAPTER_REGISTRY:
        del _ADAPTER_REGISTRY[name]
        return True
    return False
