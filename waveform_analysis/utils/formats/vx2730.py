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
from typing import Callable, Iterator, List, Optional, Union

import numpy as np
import pandas as pd

from waveform_analysis.core.foundation.utils import exporter

from .adapter import DAQAdapter, register_adapter
from .base import ColumnMapping, FormatReader, FormatSpec, TimestampUnit
from .directory import DirectoryLayout

export, __all__ = exporter()

logger = logging.getLogger(__name__)

# Check for Polars availability (fastest option)
_POLARS_AVAILABLE = False
try:
    import polars as pl

    _POLARS_AVAILABLE = True
except ImportError:
    pl = None

# Check for PyArrow availability
_PYARROW_AVAILABLE = False
try:
    import pyarrow as pa
    import pyarrow.csv as pa_csv

    _PYARROW_AVAILABLE = True
except ImportError:
    pa = None
    pa_csv = None


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

        # Priority: Polars > PyArrow > Pandas
        # Polars is fastest (Rust implementation, 2-3x faster than PyArrow)
        if _POLARS_AVAILABLE:
            try:
                return self._read_file_polars(file_path, skiprows)
            except Exception as e:
                logger.debug(f"Polars read failed for {file_path}: {e}, falling back to PyArrow")

        # PyArrow fallback (40-60% faster than pandas)
        if _PYARROW_AVAILABLE:
            try:
                return self._read_file_pyarrow(file_path, skiprows)
            except Exception as e:
                logger.debug(f"PyArrow read failed for {file_path}: {e}, falling back to pandas")

        # Pandas fallback with explicit dtype
        return self._read_file_pandas(file_path, skiprows)

    def _read_file_polars(self, file_path: Path, skiprows: int) -> np.ndarray:
        """使用 Polars 读取文件（Rust 实现，比 PyArrow 快 2-3x）

        Polars 优势：
        - Rust 实现，解析速度最快
        - 内存效率高（列式存储）
        - 自动并行解析

        Args:
            file_path: 文件路径
            skiprows: 跳过的行数

        Returns:
            二维数组
        """
        samples_start = self.spec.columns.samples_start

        # 先读取一行确定列数
        with open(file_path, 'r') as f:
            for _ in range(skiprows):
                f.readline()
            first_line = f.readline()
            if not first_line.strip():
                return np.array([]).reshape(0, 0)
            n_cols = first_line.count(self.spec.delimiter) + 1

        # 构建 schema：前 samples_start 列为 Int64，其余为 Int16
        schema = {}
        for i in range(n_cols):
            col_name = f'column_{i}'
            if i < samples_start:
                schema[col_name] = pl.Int64
            else:
                schema[col_name] = pl.Int16

        df = pl.read_csv(
            file_path,
            separator=self.spec.delimiter,
            skip_rows=skiprows,
            has_header=False,
            schema=schema,
            infer_schema_length=0,  # 禁用推断，使用显式 schema
        )

        if df.is_empty():
            return np.array([]).reshape(0, 0)

        # 转换为 numpy 数组
        arr = df.to_numpy()

        # 验证时间戳列有效性
        try:
            timestamp_col = arr[:, self.spec.columns.timestamp]
            if np.issubdtype(timestamp_col.dtype, np.floating):
                valid_mask = ~np.isnan(timestamp_col)
            else:
                valid_mask = np.ones(len(arr), dtype=bool)

            if not np.all(valid_mask):
                return arr[valid_mask]
        except (IndexError, TypeError):
            pass

        return arr

    def _read_file_pyarrow(self, file_path: Path, skiprows: int) -> np.ndarray:
        """使用 PyArrow 读取文件（显式指定 dtype，避免 pd.to_numeric）"""
        read_options = pa_csv.ReadOptions(
            skip_rows=skiprows,
            autogenerate_column_names=True,
        )
        parse_options = pa_csv.ParseOptions(delimiter=self.spec.delimiter)

        # 显式指定列类型：前 samples_start 列为 int64，波形列为 int16
        samples_start = self.spec.columns.samples_start
        column_types = {}
        for i in range(samples_start):
            column_types[f'f{i}'] = pa.int64()

        # 波形列指定为 int16（14-bit ADC 数据）
        # 注意：PyArrow 会自动检测列数，这里预设一个较大的范围
        for i in range(samples_start, samples_start + 2000):
            column_types[f'f{i}'] = pa.int16()

        convert_options = pa_csv.ConvertOptions(
            column_types=column_types,
            strings_can_be_null=False,
            auto_dict_encode=False,
        )

        table = pa_csv.read_csv(
            str(file_path),
            read_options=read_options,
            parse_options=parse_options,
            convert_options=convert_options,
        )

        # 直接转换为 numpy，无需额外的类型转换
        arr = table.to_pandas().to_numpy()

        if arr.size == 0:
            return arr

        # 验证时间戳列有效性
        try:
            timestamp_col = arr[:, self.spec.columns.timestamp]
            if np.issubdtype(timestamp_col.dtype, np.floating):
                valid_mask = ~np.isnan(timestamp_col)
            else:
                valid_mask = np.ones(len(arr), dtype=bool)

            if not np.all(valid_mask):
                return arr[valid_mask]
        except (IndexError, TypeError):
            pass

        return arr

    def _read_file_pandas(self, file_path: Path, skiprows: int) -> np.ndarray:
        """使用 Pandas 读取文件（自动推断 dtype，后转换类型）"""
        try:
            # 不指定 dtype，让 pandas 自动推断（更快）
            df = pd.read_csv(
                file_path,
                delimiter=self.spec.delimiter,
                skiprows=skiprows,
                header=None,
                on_bad_lines="warn",
            )
        except Exception as e:
            logger.debug(f"pandas 读取失败 {file_path}: {e}")
            return np.array([]).reshape(0, 0)

        if df.empty:
            return np.array([]).reshape(0, 0)

        df.dropna(how="all", inplace=True)

        if df.empty:
            return np.array([]).reshape(0, 0)

        arr = df.to_numpy()

        # 验证时间戳列有效性
        try:
            timestamp_col = arr[:, self.spec.columns.timestamp]
            if np.issubdtype(timestamp_col.dtype, np.floating):
                valid_mask = ~np.isnan(timestamp_col)
                if not np.all(valid_mask):
                    return arr[valid_mask]
        except (IndexError, TypeError):
            pass

        return arr

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

    def count_total_rows(self, file_paths: List[Union[str, Path]]) -> int:
        """快速统计总行数（不加载数据）

        Args:
            file_paths: 文件路径列表

        Returns:
            总行数（不含头部）
        """
        total = 0
        for idx, fp in enumerate(file_paths):
            fp = Path(fp)
            if not fp.exists() or fp.stat().st_size == 0:
                continue

            if idx == 0:
                skiprows = self.spec.header_rows_first_file
            else:
                skiprows = self.spec.header_rows_other_files

            # 快速行计数（使用二进制模式）
            with open(fp, 'rb') as f:
                line_count = sum(1 for _ in f)
            total += max(0, line_count - skiprows)

        return total

    def read_files_streaming(
        self,
        file_paths: List[Union[str, Path]],
        output_dtype: np.dtype,
        output_path: Path,
        structurizer: Callable[[np.ndarray, np.memmap, int], int],
        show_progress: bool = False,
    ) -> np.memmap:
        """流式读取并结构化，直接写入 memmap

        边读边处理，避免全量 vstack 内存爆炸。

        Args:
            file_paths: 文件路径列表
            output_dtype: 输出结构化数组的 dtype
            output_path: memmap 输出文件路径
            structurizer: 结构化函数，签名为 (raw_arr, output_memmap, offset) -> n_written
                          将原始数组结构化并写入 memmap 的指定偏移位置，返回写入的行数
            show_progress: 是否显示进度条

        Returns:
            np.memmap: 结构化后的 memmap 数组

        Example:
            >>> def my_structurizer(raw, output, offset):
            ...     n = len(raw)
            ...     output[offset:offset+n]['timestamp'] = raw[:, 2]
            ...     output[offset:offset+n]['wave'] = raw[:, 7:]
            ...     return n
            >>> reader = VX2730Reader()
            >>> result = reader.read_files_streaming(
            ...     files, output_dtype, Path('output.dat'), my_structurizer
            ... )
        """
        if not file_paths:
            # 返回空 memmap
            output = np.memmap(output_path, dtype=output_dtype, mode='w+', shape=(0,))
            return output

        # 第一遍：统计总行数
        total_rows = self.count_total_rows(file_paths)

        if total_rows == 0:
            output = np.memmap(output_path, dtype=output_dtype, mode='w+', shape=(0,))
            return output

        # 预分配 memmap
        output = np.memmap(output_path, dtype=output_dtype, mode='w+', shape=(total_rows,))

        # 可选进度条
        if show_progress:
            try:
                from tqdm import tqdm
                pbar = tqdm(file_paths, desc="流式读取", leave=False)
            except ImportError:
                pbar = file_paths
        else:
            pbar = file_paths

        # 第二遍：逐文件读取并结构化
        offset = 0
        for idx, fp in enumerate(pbar):
            is_first = idx == 0
            arr = self.read_file(fp, is_first_file=is_first)

            if arr.size == 0:
                continue

            # 调用结构化函数，写入 memmap
            n_written = structurizer(arr, output, offset)
            offset += n_written

        # 刷新到磁盘
        output.flush()

        # 如果实际写入行数少于预估，返回截断的视图
        if offset < total_rows:
            logger.debug(f"实际写入 {offset} 行，预估 {total_rows} 行")
            # 创建新的 memmap 视图
            return np.memmap(output_path, dtype=output_dtype, mode='r+', shape=(offset,))

        return output


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
