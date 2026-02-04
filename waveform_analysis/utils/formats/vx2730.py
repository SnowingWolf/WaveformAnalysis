"""
CAEN VX2730 数字化仪完整适配器

本模块包含 VX2730 的所有配置和实现：
- VX2730_SPEC: 格式规范（列映射、时间戳单位、分隔符等）
- VX2730Reader: CSV 格式读取器
- VX2730_LAYOUT: 目录结构配置
- VX2730_ADAPTER: 完整适配器

格式特点:
- 分隔符: 分号 (;)
- 首文件有 2 行头部，其他文件无头部
- 时间戳单位: 皮秒 (ps)
- 采样率: 500 MHz
- 列布局: BOARD;CHANNEL;TIMETAG;...;SAMPLES[7:]
- 目录结构: DAQ/{run_name}/RAW/*.CSV

Examples:
    >>> from waveform_analysis.utils.formats import get_adapter
    >>> adapter = get_adapter("vx2730")
    >>>
    >>> # 扫描目录
    >>> channel_files = adapter.scan_run("DAQ", "run_001")
    >>>
    >>> # 加载通道数据
    >>> data = adapter.load_channel("DAQ", "run_001", channel=0)
    >>>
    >>> # 提取并转换时间戳
    >>> extracted = adapter.extract_and_convert(data)
"""

import logging
from pathlib import Path
from typing import Iterator, List, Optional, Union

import numpy as np
import pandas as pd

from waveform_analysis.core.foundation.utils import exporter

from .adapter import DAQAdapter, register_adapter
from .base import ColumnMapping, FormatReader, FormatSpec, TimestampUnit
from .directory import DirectoryLayout

export, __all__ = exporter()

logger = logging.getLogger(__name__)


# ============================================================================
# VX2730 格式规范
# ============================================================================


@export
class VX2730Spec:
    """VX2730 格式规范的工厂类"""

    @staticmethod
    def create() -> FormatSpec:
        """创建 VX2730 格式规范"""
        return FormatSpec(
            name="vx2730_csv",
            version="1.0",
            columns=ColumnMapping(
                board=0,
                channel=1,
                timestamp=2,
                samples_start=7,
                samples_end=None,  # 到行末
                baseline_start=7,
                baseline_end=47,  # 前 40 个采样点用于基线计算
            ),
            timestamp_unit=TimestampUnit.PICOSECONDS,
            file_pattern="*CH*.CSV",
            header_rows_first_file=2,
            header_rows_other_files=0,
            delimiter=";",
            sampling_rate_hz=500e6,
            metadata={
                "manufacturer": "CAEN",
                "model": "VX2730",
                "description": "CAEN VX2730 数字化仪 CSV 格式",
            },
        )


# 预定义的 VX2730 格式规范实例
VX2730_SPEC = export(VX2730Spec.create(), name="VX2730_SPEC")

# ============================================================================
# VX2730 目录布局
# ============================================================================

VX2730_LAYOUT = export(
    DirectoryLayout(
        name="vx2730",
        raw_subdir="RAW",
        run_path_template="{data_root}/{run_name}/{raw_subdir}",
        file_glob_pattern="*CH*.CSV",
        file_extension=".CSV",
        channel_regex=r"CH(\d+)",
        file_index_regex=r"_(\d+)\.CSV$",
        run_info_pattern="{run_name}_info.txt",
        metadata={
            "manufacturer": "CAEN",
            "model": "VX2730",
            "description": "CAEN VX2730 标准目录布局",
        },
    ),
    name="VX2730_LAYOUT",
)


# ============================================================================
# VX2730 格式读取器
# ============================================================================


@export
class VX2730Reader(FormatReader):
    """VX2730 CSV 格式读取器

    实现 CAEN VX2730 数字化仪 CSV 格式的读取逻辑。

    Attributes:
        spec: VX2730 格式规范

    Examples:
        >>> reader = VX2730Reader()
        >>> data = reader.read_files(['CH0_0.CSV', 'CH0_1.CSV'])
        >>> print(f"读取了 {len(data)} 条记录")
    """

    def __init__(self, spec: Optional[FormatSpec] = None):
        """初始化 VX2730 读取器

        Args:
            spec: 格式规范（默认使用 VX2730_SPEC）
        """
        super().__init__(spec or VX2730_SPEC)

    def read_file(self, file_path: Union[str, Path], is_first_file: bool = True) -> np.ndarray:
        """读取单个 VX2730 CSV 文件

        Args:
            file_path: 文件路径
            is_first_file: 是否为首个文件

        Returns:
            二维数组，每行一条记录
        """
        file_path = Path(file_path)

        # 检查文件
        if not file_path.exists():
            logger.warning(f"文件不存在: {file_path}")
            return np.array([]).reshape(0, 0)

        if file_path.stat().st_size == 0:
            logger.debug(f"跳过空文件: {file_path}")
            return np.array([]).reshape(0, 0)

        # 确定跳过的行数
        skiprows = (
            self.spec.header_rows_first_file if is_first_file else self.spec.header_rows_other_files
        )

        try:
            # 尝试使用 pandas 读取（更健壮）
            df = pd.read_csv(
                file_path,
                delimiter=self.spec.delimiter,
                skiprows=skiprows,
                header=None,
                on_bad_lines="warn",
            )

            if df.empty:
                return np.array([]).reshape(0, 0)

            # 处理数值列
            df.dropna(how="all", inplace=True)

            # 确保时间戳列和采样列是数值类型
            try:
                df.iloc[:, self.spec.columns.timestamp] = pd.to_numeric(
                    df.iloc[:, self.spec.columns.timestamp], errors="coerce"
                )
                df.iloc[:, self.spec.columns.samples_start :] = df.iloc[
                    :, self.spec.columns.samples_start :
                ].apply(pd.to_numeric, errors="coerce")
                df.dropna(subset=[self.spec.columns.timestamp], inplace=True)
            except Exception as e:
                logger.warning(f"数值转换失败 {file_path}: {e}")

            return df.to_numpy()

        except Exception as e:
            logger.warning(f"pandas 读取失败 {file_path}: {e}")

            # 回退到 numpy 读取
            try:
                data = np.loadtxt(
                    file_path,
                    delimiter=self.spec.delimiter,
                    skiprows=skiprows,
                    dtype=float,
                    ndmin=2,
                )
                return data
            except Exception as e2:
                logger.error(f"numpy 读取也失败 {file_path}: {e2}")
                return np.array([]).reshape(0, 0)

    def read_files(
        self, file_paths: List[Union[str, Path]], show_progress: bool = False
    ) -> np.ndarray:
        """读取并堆叠多个文件

        Args:
            file_paths: 文件路径列表
            show_progress: 是否显示进度条

        Returns:
            所有文件数据垂直堆叠后的数组
        """
        if not file_paths:
            return np.array([]).reshape(0, 0)

        # 可选进度条
        if show_progress:
            try:
                from tqdm import tqdm

                pbar = tqdm(file_paths, desc="读取文件", leave=False)
            except ImportError:
                pbar = file_paths
        else:
            pbar = file_paths

        arrays = []
        for idx, fp in enumerate(pbar):
            is_first = idx == 0
            arr = self.read_file(fp, is_first_file=is_first)
            if arr.size > 0:
                arrays.append(arr)

        if not arrays:
            return np.array([]).reshape(0, 0)

        # 处理列数不一致的情况
        try:
            return np.vstack(arrays)
        except ValueError:
            # 列数不一致，进行填充
            max_cols = max(a.shape[1] for a in arrays)
            padded = []
            for a in arrays:
                if a.shape[1] < max_cols:
                    pad_width = ((0, 0), (0, max_cols - a.shape[1]))
                    a = np.pad(a, pad_width, mode="constant", constant_values=np.nan)
                padded.append(a)
            return np.vstack(padded)

    def read_files_generator(
        self, file_paths: List[Union[str, Path]], chunk_size: int = 10
    ) -> Iterator[np.ndarray]:
        """生成器模式读取

        Args:
            file_paths: 文件路径列表
            chunk_size: 每次返回的文件数量

        Yields:
            每个 chunk 的数据数组
        """
        if not file_paths:
            return

        for i in range(0, len(file_paths), chunk_size):
            chunk_files = file_paths[i : i + chunk_size]
            arrays = []

            for j, fp in enumerate(chunk_files):
                # 只有第一个文件的第一个 chunk 才跳过头部
                is_first = i == 0 and j == 0
                arr = self.read_file(fp, is_first_file=is_first)
                if arr.size > 0:
                    arrays.append(arr)

            if arrays:
                try:
                    yield np.vstack(arrays)
                except ValueError:
                    # 处理列数不一致
                    max_cols = max(a.shape[1] for a in arrays)
                    padded = []
                    for a in arrays:
                        if a.shape[1] < max_cols:
                            pad_width = ((0, 0), (0, max_cols - a.shape[1]))
                            a = np.pad(a, pad_width, mode="constant", constant_values=np.nan)
                        padded.append(a)
                    yield np.vstack(padded)


# ============================================================================
# VX2730 完整适配器
# ============================================================================

VX2730_ADAPTER = export(
    DAQAdapter(
        name="vx2730",
        format_reader=VX2730Reader(VX2730_SPEC),
        directory_layout=VX2730_LAYOUT,
    ),
    name="VX2730_ADAPTER",
)

# 自动注册适配器
register_adapter(VX2730_ADAPTER)
