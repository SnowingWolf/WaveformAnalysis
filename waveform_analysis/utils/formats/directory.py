# -*- coding: utf-8 -*-
"""
目录结构配置

定义 DAQ 数据的目录结构和文件组织方式。

不同的 DAQ 系统可能有不同的目录布局：
- VX2730: DAQ/{run_name}/RAW/*.CSV
- 扁平结构: DAQ/{run_name}/*.csv

通过 DirectoryLayout 可以灵活配置这些差异。

Examples:
    >>> from waveform_analysis.utils.formats import DirectoryLayout, VX2730_LAYOUT
    >>> layout = VX2730_LAYOUT
    >>> raw_path = layout.get_raw_path("DAQ", "run_001")
    >>> print(raw_path)  # DAQ/run_001/RAW
    >>> groups = layout.group_files_by_channel(raw_path)
"""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, List, Optional

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
@dataclass
class DirectoryLayout:
    """DAQ 目录结构配置

    定义 DAQ 数据的目录布局，包括：
    - 原始数据子目录名（如 "RAW"）
    - 运行路径模板
    - 文件匹配模式
    - 通道识别正则表达式
    - 文件索引识别正则表达式

    Attributes:
        name: 布局名称
        raw_subdir: 原始数据子目录名（空字符串表示无子目录）
        run_path_template: 运行路径模板，支持 {data_root}, {run_name}, {raw_subdir} 占位符
        file_glob_pattern: 文件 glob 模式
        file_extension: 文件扩展名
        channel_regex: 从文件名提取通道号的正则表达式
        file_index_regex: 从文件名提取文件索引的正则表达式
        run_info_pattern: 运行信息文件模式（可选）
        metadata: 额外元数据

    Examples:
        >>> layout = DirectoryLayout(
        ...     name="my_layout",
        ...     raw_subdir="data",
        ...     file_glob_pattern="*.dat",
        ...     channel_regex=r"channel(\\d+)",
        ... )
        >>> raw_path = layout.get_raw_path("DAQ", "run_001")
    """
    name: str                                    # 布局名称

    # 目录结构
    raw_subdir: str = "RAW"                      # 原始数据子目录名（空表示无子目录）
    run_path_template: str = "{data_root}/{run_name}/{raw_subdir}"  # 运行路径模板

    # 文件匹配
    file_glob_pattern: str = "*CH*.CSV"          # 文件 glob 模式
    file_extension: str = ".CSV"                 # 文件扩展名

    # 通道识别正则
    channel_regex: str = r"CH(\d+)"              # 从文件名提取通道号
    file_index_regex: str = r"_(\d+)\.CSV$"      # 从文件名提取文件索引

    # 可选：运行信息文件
    run_info_pattern: Optional[str] = "{run_name}_info.txt"

    # 元数据
    metadata: Dict = field(default_factory=dict)

    # 编译后的正则表达式（延迟初始化）
    _channel_re: Optional[re.Pattern] = field(default=None, repr=False, compare=False)
    _file_index_re: Optional[re.Pattern] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        """初始化后编译正则表达式"""
        self._channel_re = re.compile(self.channel_regex)
        self._file_index_re = re.compile(self.file_index_regex, re.IGNORECASE)

    def get_raw_path(self, data_root: str, run_name: str) -> Path:
        """获取原始数据目录路径

        Args:
            data_root: 数据根目录
            run_name: 运行名称

        Returns:
            原始数据目录的 Path 对象
        """
        # 使用模板生成路径
        path_str = self.run_path_template.format(
            data_root=data_root,
            run_name=run_name,
            raw_subdir=self.raw_subdir,
        )

        # 清理连续斜杠（当 raw_subdir 为空时可能出现 //）
        path_str = re.sub(r'/+', '/', path_str)
        path_str = path_str.rstrip('/')

        return Path(path_str)

    def get_run_path(self, data_root: str, run_name: str) -> Path:
        """获取运行根目录路径

        Args:
            data_root: 数据根目录
            run_name: 运行名称

        Returns:
            运行根目录的 Path 对象
        """
        return Path(data_root) / run_name

    def get_run_info_path(self, data_root: str, run_name: str) -> Optional[Path]:
        """获取运行信息文件路径

        Args:
            data_root: 数据根目录
            run_name: 运行名称

        Returns:
            运行信息文件的 Path 对象，如果未配置则返回 None
        """
        if not self.run_info_pattern:
            return None

        run_path = self.get_run_path(data_root, run_name)
        info_filename = self.run_info_pattern.format(run_name=run_name)
        return run_path / info_filename

    def extract_channel(self, filename: str) -> Optional[int]:
        """从文件名提取通道号

        Args:
            filename: 文件名

        Returns:
            通道号，如果无法提取则返回 None
        """
        if self._channel_re is None:
            self._channel_re = re.compile(self.channel_regex)

        match = self._channel_re.search(filename)
        return int(match.group(1)) if match else None

    def extract_file_index(self, filename: str) -> int:
        """从文件名提取文件索引

        Args:
            filename: 文件名

        Returns:
            文件索引，如果无法提取则返回 0
        """
        if self._file_index_re is None:
            self._file_index_re = re.compile(self.file_index_regex, re.IGNORECASE)

        match = self._file_index_re.search(filename)
        return int(match.group(1)) if match else 0

    def list_files(self, raw_path: Path) -> List[Path]:
        """列出目录中匹配的文件

        Args:
            raw_path: 原始数据目录

        Returns:
            匹配的文件路径列表（已排序）
        """
        if not raw_path.exists():
            return []

        return sorted(raw_path.glob(self.file_glob_pattern))

    def group_files_by_channel(self, raw_path: Path) -> Dict[int, List[Dict]]:
        """按通道分组文件

        Args:
            raw_path: 原始数据目录

        Returns:
            按通道分组的文件信息字典:
            {
                channel_id: [
                    {'path': Path, 'index': int, 'filename': str},
                    ...
                ],
                ...
            }
        """
        files = self.list_files(raw_path)
        groups: Dict[int, List[Dict]] = {}

        for f in files:
            ch = self.extract_channel(f.name)
            if ch is not None:
                if ch not in groups:
                    groups[ch] = []

                idx = self.extract_file_index(f.name)
                groups[ch].append({
                    'path': f,
                    'index': idx,
                    'filename': f.name,
                })

        # 按文件索引排序
        for ch in groups:
            groups[ch].sort(key=lambda x: x['index'])

        return groups


# 预定义布局：扁平目录（无 RAW 子目录）
# 注意：VX2730_LAYOUT 已移至 vx2730.py 中，与其他 VX2730 配置放在一起
FLAT_LAYOUT = export(
    DirectoryLayout(
        name="flat",
        raw_subdir="",                              # 无子目录
        run_path_template="{data_root}/{run_name}",
        file_glob_pattern="*.csv",
        file_extension=".csv",
        channel_regex=r"ch(\d+)",                   # 小写
        file_index_regex=r"_(\d+)\.csv$",
        run_info_pattern=None,
        metadata={
            "description": "扁平目录结构，数据文件直接在运行目录下",
        },
    ),
    name="FLAT_LAYOUT",
)
