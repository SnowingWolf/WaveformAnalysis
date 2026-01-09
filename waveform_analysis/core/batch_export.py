"""
批量处理和数据导出模块 (Phase 3.1 & 3.2)

提供多运行批量处理和统一的数据导出功能:
- 批量处理多个run
- 并行执行支持
- 进度跟踪
- 统一的导出接口(Parquet, HDF5, CSV, JSON等)
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from waveform_analysis.core.utils import exporter

logger = logging.getLogger(__name__)
export, __all__ = exporter()


# ===========================
# 批量处理 (Phase 3.1)
# ===========================

@export
class BatchProcessor:
    """
    批量处理器

    支持并行处理多个run的数据

    使用示例:
        processor = BatchProcessor(ctx)
        results = processor.process_runs(
            run_ids=['run_001', 'run_002', 'run_003'],
            data_name='peaks',
            max_workers=4
        )
    """

    def __init__(self, context: Any):
        """
        初始化批量处理器

        Args:
            context: Context对象
        """
        self.context = context
        self.logger = logging.getLogger(self.__class__.__name__)

    def process_runs(
        self,
        run_ids: List[str],
        data_name: str,
        max_workers: Optional[int] = None,
        show_progress: bool = True,
        on_error: str = 'continue',  # 'continue', 'stop', 'raise'
    ) -> Dict[str, Any]:
        """
        批量处理多个run

        Args:
            run_ids: 运行ID列表
            data_name: 要处理的数据名称
            max_workers: 最大并行工作进程数
            show_progress: 是否显示进度
            on_error: 错误处理策略

        Returns:
            结果字典 {run_id: data or error}
        """
        results = {}
        errors = {}

        if max_workers == 1:
            # 串行处理
            for i, run_id in enumerate(run_ids):
                if show_progress:
                    print(f"Processing {i+1}/{len(run_ids)}: {run_id}")

                try:
                    data = self.context.get_data(run_id, data_name)
                    results[run_id] = data
                except Exception as e:
                    errors[run_id] = e
                    self.logger.error(f"Failed to process {run_id}: {e}")

                    if on_error == 'stop':
                        break
                    elif on_error == 'raise':
                        raise
        else:
            # 并行处理
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_run = {
                    executor.submit(self.context.get_data, run_id, data_name): run_id
                    for run_id in run_ids
                }

                completed = 0
                for future in as_completed(future_to_run):
                    run_id = future_to_run[future]
                    completed += 1

                    if show_progress:
                        print(f"Completed {completed}/{len(run_ids)}: {run_id}")

                    try:
                        data = future.result()
                        results[run_id] = data
                    except Exception as e:
                        errors[run_id] = e
                        self.logger.error(f"Failed to process {run_id}: {e}")

                        if on_error == 'raise':
                            raise

        if errors and show_progress:
            print(f"\nCompleted with {len(errors)} errors")

        return {'results': results, 'errors': errors}

    def process_with_custom_func(
        self,
        run_ids: List[str],
        func: Callable,
        max_workers: Optional[int] = None,
        show_progress: bool = True,
    ) -> Dict[str, Any]:
        """
        使用自定义函数批量处理

        Args:
            run_ids: 运行ID列表
            func: 处理函数 func(context, run_id) -> result
            max_workers: 最大并行工作进程数
            show_progress: 是否显示进度

        Returns:
            结果字典 {run_id: result}
        """
        results = {}

        if max_workers == 1:
            for i, run_id in enumerate(run_ids):
                if show_progress:
                    print(f"Processing {i+1}/{len(run_ids)}: {run_id}")
                results[run_id] = func(self.context, run_id)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_run = {
                    executor.submit(func, self.context, run_id): run_id
                    for run_id in run_ids
                }

                completed = 0
                for future in as_completed(future_to_run):
                    run_id = future_to_run[future]
                    completed += 1

                    if show_progress:
                        print(f"Completed {completed}/{len(run_ids)}: {run_id}")

                    results[run_id] = future.result()

        return results


# ===========================
# 数据导出 (Phase 3.2)
# ===========================

@export
class DataExporter:
    """
    统一的数据导出接口

    支持多种格式: Parquet, HDF5, CSV, JSON, NumPy

    使用示例:
        exporter = DataExporter()
        exporter.export(data, 'output.parquet', format='parquet')
    """

    SUPPORTED_FORMATS = ['parquet', 'hdf5', 'csv', 'json', 'npy', 'npz']

    def __init__(self):
        """初始化导出器"""
        self.logger = logging.getLogger(self.__class__.__name__)

    def export(
        self,
        data: Union[np.ndarray, pd.DataFrame, Dict[str, Any]],
        output_path: Union[str, Path],
        format: Optional[str] = None,
        **kwargs
    ):
        """
        导出数据到文件

        Args:
            data: 要导出的数据
            output_path: 输出文件路径
            format: 格式('parquet', 'hdf5', 'csv', 'json', 'npy', 'npz')
                   如果为None,从文件扩展名推断
            **kwargs: 格式特定的参数
        """
        output_path = Path(output_path)

        # 推断格式
        if format is None:
            format = output_path.suffix.lstrip('.')

        format = format.lower()

        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {format}. Supported: {self.SUPPORTED_FORMATS}")

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 根据格式导出
        if format == 'parquet':
            self._export_parquet(data, output_path, **kwargs)
        elif format == 'hdf5' or format == 'h5':
            self._export_hdf5(data, output_path, **kwargs)
        elif format == 'csv':
            self._export_csv(data, output_path, **kwargs)
        elif format == 'json':
            self._export_json(data, output_path, **kwargs)
        elif format == 'npy':
            self._export_npy(data, output_path, **kwargs)
        elif format == 'npz':
            self._export_npz(data, output_path, **kwargs)

        self.logger.info(f"Exported data to {output_path} (format: {format})")

    def _export_parquet(self, data, output_path, **kwargs):
        """导出为Parquet格式"""
        df = self._to_dataframe(data)
        df.to_parquet(output_path, **kwargs)

    def _export_hdf5(self, data, output_path, key='data', **kwargs):
        """导出为HDF5格式"""
        df = self._to_dataframe(data)
        df.to_hdf(output_path, key=key, mode='w', **kwargs)

    def _export_csv(self, data, output_path, **kwargs):
        """导出为CSV格式"""
        df = self._to_dataframe(data)
        df.to_csv(output_path, index=False, **kwargs)

    def _export_json(self, data, output_path, **kwargs):
        """导出为JSON格式"""
        if isinstance(data, pd.DataFrame):
            data.to_json(output_path, **kwargs)
        elif isinstance(data, dict):
            import json
            with open(output_path, 'w') as f:
                json.dump(data, f, **kwargs)
        else:
            df = self._to_dataframe(data)
            df.to_json(output_path, **kwargs)

    def _export_npy(self, data, output_path, **kwargs):
        """导出为NumPy .npy格式"""
        if isinstance(data, pd.DataFrame):
            data = data.to_records(index=False)
        np.save(output_path, data, **kwargs)

    def _export_npz(self, data, output_path, **kwargs):
        """导出为NumPy .npz格式"""
        if isinstance(data, dict):
            np.savez(output_path, **data, **kwargs)
        elif isinstance(data, pd.DataFrame):
            # 将DataFrame的每一列保存为独立的数组
            arrays = {col: data[col].values for col in data.columns}
            np.savez(output_path, **arrays, **kwargs)
        else:
            np.savez(output_path, data=data, **kwargs)

    def _to_dataframe(self, data) -> pd.DataFrame:
        """将数据转换为DataFrame"""
        if isinstance(data, pd.DataFrame):
            return data
        elif isinstance(data, np.ndarray):
            if data.dtype.names:
                # 结构化数组
                return pd.DataFrame(data)
            else:
                # 普通数组
                return pd.DataFrame({'data': data})
        elif isinstance(data, dict):
            return pd.DataFrame(data)
        else:
            raise TypeError(f"Cannot convert {type(data)} to DataFrame")


@export
def batch_export(
    context: Any,
    run_ids: List[str],
    data_name: str,
    output_dir: Union[str, Path],
    format: str = 'parquet',
    max_workers: Optional[int] = None,
):
    """
    批量导出多个run的数据

    Args:
        context: Context对象
        run_ids: 运行ID列表
        data_name: 数据名称
        output_dir: 输出目录
        format: 导出格式
        max_workers: 最大并行工作进程数
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    processor = BatchProcessor(context)
    exporter = DataExporter()

    # 批量获取数据
    batch_results = processor.process_runs(
        run_ids=run_ids,
        data_name=data_name,
        max_workers=max_workers,
        show_progress=True
    )

    # 导出每个run的数据
    for run_id, data in batch_results['results'].items():
        output_path = output_dir / f"{run_id}_{data_name}.{format}"
        try:
            exporter.export(data, output_path, format=format)
        except Exception as e:
            logger.error(f"Failed to export {run_id}: {e}")

    print(f"\nExported {len(batch_results['results'])} runs to {output_dir}")
