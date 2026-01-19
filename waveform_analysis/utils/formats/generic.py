# -*- coding: utf-8 -*-
"""
通用 CSV 格式读取器

可通过 FormatSpec 配置来读取任意 CSV 格式的 DAQ 数据。

Examples:
    >>> from waveform_analysis.utils.formats import GenericCSVReader, FormatSpec
    >>> spec = FormatSpec(
    ...     name="custom",
    ...     columns=ColumnMapping(timestamp=3),
    ...     delimiter=",",
    ... )
    >>> reader = GenericCSVReader(spec)
    >>> data = reader.read_file('data.csv')
"""

import logging
from pathlib import Path
from typing import Iterator, List, Optional, Union

import numpy as np
import pandas as pd

from waveform_analysis.core.foundation.utils import exporter
from .base import FormatReader, FormatSpec

export, __all__ = exporter()

logger = logging.getLogger(__name__)


@export
class GenericCSVReader(FormatReader):
    """通用 CSV 格式读取器

    可通过 FormatSpec 配置来读取任意 CSV 格式的 DAQ 数据。

    Attributes:
        spec: 格式规范

    Examples:
        >>> from waveform_analysis.utils.formats import (
        ...     GenericCSVReader, FormatSpec, ColumnMapping
        ... )
        >>> spec = FormatSpec(
        ...     name="custom",
        ...     columns=ColumnMapping(timestamp=3),
        ...     delimiter=",",
        ... )
        >>> reader = GenericCSVReader(spec)
        >>> data = reader.read_file('data.csv')
    """

    def read_file(
        self,
        file_path: Union[str, Path],
        is_first_file: bool = True
    ) -> np.ndarray:
        """读取单个 CSV 文件

        Args:
            file_path: 文件路径
            is_first_file: 是否为首个文件

        Returns:
            二维数组，每行一条记录
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.warning(f"文件不存在: {file_path}")
            return np.array([]).reshape(0, 0)

        if file_path.stat().st_size == 0:
            logger.debug(f"跳过空文件: {file_path}")
            return np.array([]).reshape(0, 0)

        skiprows = (
            self.spec.header_rows_first_file if is_first_file
            else self.spec.header_rows_other_files
        )

        try:
            df = pd.read_csv(
                file_path,
                delimiter=self.spec.delimiter,
                skiprows=skiprows,
                header=None,
                on_bad_lines="warn",
            )
            df.dropna(how="all", inplace=True)

            if df.empty:
                return np.array([]).reshape(0, 0)

            return df.to_numpy()

        except Exception as e:
            logger.warning(f"读取文件失败 {file_path}: {e}")
            return np.array([]).reshape(0, 0)

    def read_files(
        self,
        file_paths: List[Union[str, Path]],
        show_progress: bool = False
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
            arr = self.read_file(fp, is_first_file=(idx == 0))
            if arr.size > 0:
                arrays.append(arr)

        if not arrays:
            return np.array([]).reshape(0, 0)

        try:
            return np.vstack(arrays)
        except ValueError:
            max_cols = max(a.shape[1] for a in arrays)
            padded = []
            for a in arrays:
                if a.shape[1] < max_cols:
                    pad_width = ((0, 0), (0, max_cols - a.shape[1]))
                    a = np.pad(a, pad_width, mode='constant', constant_values=np.nan)
                padded.append(a)
            return np.vstack(padded)

    def read_files_generator(
        self,
        file_paths: List[Union[str, Path]],
        chunk_size: int = 10
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
            chunk_files = file_paths[i:i + chunk_size]
            arrays = []

            for j, fp in enumerate(chunk_files):
                is_first = (i == 0 and j == 0)
                arr = self.read_file(fp, is_first_file=is_first)
                if arr.size > 0:
                    arrays.append(arr)

            if arrays:
                try:
                    yield np.vstack(arrays)
                except ValueError:
                    max_cols = max(a.shape[1] for a in arrays)
                    padded = []
                    for a in arrays:
                        if a.shape[1] < max_cols:
                            pad_width = ((0, 0), (0, max_cols - a.shape[1]))
                            a = np.pad(a, pad_width, mode='constant', constant_values=np.nan)
                        padded.append(a)
                    yield np.vstack(padded)
