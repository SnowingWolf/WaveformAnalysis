# -*- coding: utf-8 -*-
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
    >>> print(f"找到 {len(channel_files)} 个通道")
    >>>
    >>> # 加载单个通道
    >>> data = adapter.load_channel("DAQ", "run_001", channel=0)
    >>> print(f"加载 {len(data)} 条记录")
    >>>
    >>> # 提取并转换
    >>> extracted = adapter.extract_and_convert(data)
    >>> print(f"时间戳范围: {extracted['timestamp'].min()} - {extracted['timestamp'].max()}")
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional

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
    def sampling_rate_hz(self) -> Optional[float]:
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

    def scan_run(self, data_root: str, run_name: str) -> Dict[int, List[Path]]:
        """扫描运行目录，返回按通道分组的文件

        Args:
            data_root: 数据根目录
            run_name: 运行名称

        Returns:
            按通道分组的文件路径字典: {channel_id: [path1, path2, ...]}

        Raises:
            FileNotFoundError: 如果目录不存在
        """
        raw_path = self.get_raw_path(data_root, run_name)

        if not raw_path.exists():
            raise FileNotFoundError(f"目录不存在: {raw_path}")

        groups = self.directory_layout.group_files_by_channel(raw_path)

        # 转换为简单的 channel -> [paths] 格式
        return {ch: [f['path'] for f in files] for ch, files in groups.items()}

    def scan_run_detailed(
        self,
        data_root: str,
        run_name: str
    ) -> Dict[int, List[Dict]]:
        """扫描运行目录，返回详细的文件信息

        Args:
            data_root: 数据根目录
            run_name: 运行名称

        Returns:
            按通道分组的详细文件信息:
            {
                channel_id: [
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

    def load_channel(
        self,
        data_root: str,
        run_name: str,
        channel: int,
        show_progress: bool = False
    ) -> np.ndarray:
        """加载单个通道的数据

        Args:
            data_root: 数据根目录
            run_name: 运行名称
            channel: 通道编号
            show_progress: 是否显示进度条

        Returns:
            该通道的数据数组

        Raises:
            ValueError: 如果通道不存在
            FileNotFoundError: 如果目录不存在
        """
        channel_files = self.scan_run(data_root, run_name)

        if channel not in channel_files:
            available = sorted(channel_files.keys())
            raise ValueError(
                f"通道 {channel} 不存在。可用通道: {available}"
            )

        file_paths = channel_files[channel]
        return self.format_reader.read_files(file_paths, show_progress=show_progress)

    def load_all_channels(
        self,
        data_root: str,
        run_name: str,
        n_channels: Optional[int] = None,
        show_progress: bool = False
    ) -> List[np.ndarray]:
        """加载所有通道的数据

        Args:
            data_root: 数据根目录
            run_name: 运行名称
            n_channels: 预期的通道数（可选）
            show_progress: 是否显示进度条

        Returns:
            每个通道数据的列表
        """
        channel_files = self.scan_run(data_root, run_name)

        if not channel_files:
            return []

        # 确定通道范围
        max_channel = max(channel_files.keys())
        if n_channels is not None:
            max_channel = max(max_channel, n_channels - 1)

        result = []
        for ch in range(max_channel + 1):
            if ch in channel_files:
                data = self.format_reader.read_files(
                    channel_files[ch],
                    show_progress=(show_progress and ch == 0)
                )
                result.append(data)
            else:
                # 通道不存在，返回空数组
                result.append(np.array([]).reshape(0, 0))

        return result

    def load_channel_generator(
        self,
        data_root: str,
        run_name: str,
        channel: int,
        chunk_size: int = 10
    ) -> Iterator[np.ndarray]:
        """生成器模式加载通道数据

        Args:
            data_root: 数据根目录
            run_name: 运行名称
            channel: 通道编号
            chunk_size: 每次返回的文件数量

        Yields:
            每个 chunk 的数据数组

        Raises:
            ValueError: 如果通道不存在
        """
        channel_files = self.scan_run(data_root, run_name)

        if channel not in channel_files:
            available = sorted(channel_files.keys())
            raise ValueError(
                f"通道 {channel} 不存在。可用通道: {available}"
            )

        file_paths = channel_files[channel]
        yield from self.format_reader.read_files_generator(file_paths, chunk_size)

    def extract_columns(self, data: np.ndarray) -> Dict[str, np.ndarray]:
        """从数据中提取各列

        Args:
            data: 数据数组

        Returns:
            包含各列的字典
        """
        return self.format_reader.extract_columns(data)

    def extract_and_convert(self, data: np.ndarray) -> Dict[str, np.ndarray]:
        """提取列并转换时间戳为皮秒

        为了向后兼容，时间戳转换为皮秒（而不是纳秒）。

        Args:
            data: 数据数组

        Returns:
            包含各列的字典，时间戳已转换为皮秒
        """
        extracted = self.format_reader.extract_columns(data)
        extracted['timestamp'] = self.format_reader.convert_timestamp_to_ps(
            extracted['timestamp']
        )
        return extracted

    def extract_and_convert_ns(self, data: np.ndarray) -> Dict[str, np.ndarray]:
        """提取列并转换时间戳为纳秒

        Args:
            data: 数据数组

        Returns:
            包含各列的字典，时间戳已转换为纳秒
        """
        extracted = self.format_reader.extract_columns(data)
        extracted['timestamp'] = self.format_reader.convert_timestamp_to_ns(
            extracted['timestamp']
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
        ctime = getattr(stat, 'st_birthtime', stat.st_mtime)
        return int(ctime * 1e9)  # 秒 → 纳秒


# 适配器注册表
_ADAPTER_REGISTRY: Dict[str, DAQAdapter] = {}


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
        >>> data = adapter.load_channel("DAQ", "run_001", channel=0)
    """
    if name not in _ADAPTER_REGISTRY:
        available = list(_ADAPTER_REGISTRY.keys())
        raise ValueError(f"未知适配器 '{name}'。可用适配器: {available}")
    return _ADAPTER_REGISTRY[name]


@export
def list_adapters() -> List[str]:
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
