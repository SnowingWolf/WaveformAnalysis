# -*- coding: utf-8 -*-
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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from waveform_analysis.core.foundation.utils import exporter

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
        progress_tracker: Optional[Any] = None,  # 新增：进度追踪器
        cancellation_token: Optional[Any] = None,  # 新增：取消令牌
    ) -> Dict[str, Any]:
        """
        批量处理多个run

        Args:
            run_ids: 运行ID列表
            data_name: 要处理的数据名称
            max_workers: 最大并行工作进程数
            show_progress: 是否显示进度
            on_error: 错误处理策略
            progress_tracker: 进度追踪器（可选，如为None则自动创建）
            cancellation_token: 取消令牌（可选，如为None则自动创建）

        Returns:
            结果字典 {run_id: data or error}
        """
        from waveform_analysis.core.foundation.progress import (
            ProgressTracker, format_throughput, format_time
        )
        from waveform_analysis.core.cancellation import (
            CancellationToken, get_cancellation_manager, TaskCancelledException
        )

        results = {}
        errors = {}
        start_time = time.time()

        # 创建或使用cancellation_token
        owns_token = False
        if cancellation_token is None:
            cancellation_token = CancellationToken()
            cancel_manager = get_cancellation_manager()
            cancel_manager.enable()
            cancel_manager.register_token(cancellation_token)
            owns_token = True

        # 创建或使用progress_tracker
        owns_tracker = False
        if progress_tracker is None and show_progress:
            progress_tracker = ProgressTracker()
            owns_tracker = True

        # 创建主进度条
        bar_name = None
        if progress_tracker:
            bar_name = f"batch_{data_name}"
            progress_tracker.create_bar(
                bar_name,
                total=len(run_ids),
                desc=f"Processing {data_name}",
                unit="run"
            )

        try:
            if max_workers == 1:
                # 串行处理
                for i, run_id in enumerate(run_ids):
                    # 检查取消
                    if cancellation_token.is_cancelled():
                        self.logger.info(f"Processing cancelled. Processed {i}/{len(run_ids)} runs.")
                        break

                    try:
                        data = self.context.get_data(run_id, data_name)
                        results[run_id] = data
                    except TaskCancelledException:
                        self.logger.info("Task cancelled during processing")
                        break
                    except Exception as e:
                        errors[run_id] = e
                        self.logger.error(f"Failed to process {run_id}: {e}")

                        if on_error == 'stop':
                            break
                        elif on_error == 'raise':
                            raise

                    # 更新进度
                    if progress_tracker:
                        progress_tracker.update(bar_name, n=1)
                        elapsed = time.time() - start_time
                        throughput = (i + 1) / elapsed if elapsed > 0 else 0
                        progress_tracker.set_postfix(
                            bar_name,
                            success=len(results),
                            failed=len(errors),
                            throughput=format_throughput(throughput, "run")
                        )
            else:
                # 并行处理
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    # 注册executor清理回调
                    def shutdown_executor():
                        """在取消时立即关闭executor"""
                        try:
                            executor.shutdown(wait=False, cancel_futures=True)
                        except Exception as e:
                            self.logger.debug(f"Error shutting down executor: {e}")

                    cancellation_token.register_callback(shutdown_executor)

                    # 提交任务
                    future_to_run = {
                        executor.submit(self.context.get_data, run_id, data_name): run_id
                        for run_id in run_ids
                    }

                    completed = 0
                    for future in as_completed(future_to_run):
                        # 检查取消
                        if cancellation_token.is_cancelled():
                            # 取消未完成的future
                            for f in future_to_run:
                                if not f.done():
                                    f.cancel()
                            self.logger.info(f"Processing cancelled. Processed {completed}/{len(run_ids)} runs.")
                            break

                        run_id = future_to_run[future]
                        completed += 1

                        try:
                            data = future.result()
                            results[run_id] = data
                        except TaskCancelledException:
                            self.logger.info(f"Task cancelled: {run_id}")
                            break
                        except Exception as e:
                            errors[run_id] = e
                            self.logger.error(f"Failed to process {run_id}: {e}")

                            if on_error == 'raise':
                                raise

                        # 更新进度
                        if progress_tracker:
                            progress_tracker.update(bar_name, n=1)
                            elapsed = time.time() - start_time
                            throughput = completed / elapsed if elapsed > 0 else 0
                            eta = progress_tracker.calculate_eta(bar_name)
                            progress_tracker.set_postfix(
                                bar_name,
                                success=len(results),
                                failed=len(errors),
                                throughput=format_throughput(throughput, "run"),
                                ETA=format_time(eta) if eta else "N/A"
                            )

        except KeyboardInterrupt:
            # 捕获KeyboardInterrupt并转换为取消
            self.logger.info("Interrupted by user (KeyboardInterrupt)")
            cancellation_token.cancel()
            raise
        finally:
            # 关闭进度条
            if progress_tracker and bar_name:
                progress_tracker.close(bar_name)
            if owns_tracker and progress_tracker:
                progress_tracker.close_all()

            # 注销取消token
            if owns_token:
                cancel_manager = get_cancellation_manager()
                cancel_manager.unregister_token(cancellation_token)

        if errors and show_progress and not progress_tracker:
            # 如果没有进度条，打印错误摘要
            print(f"\nCompleted with {len(errors)} errors")

        return {'results': results, 'errors': errors}

    def process_with_custom_func(
        self,
        run_ids: List[str],
        func: Callable,
        max_workers: Optional[int] = None,
        show_progress: bool = True,
        progress_tracker: Optional[Any] = None,  # 新增：进度追踪器
    ) -> Dict[str, Any]:
        """
        使用自定义函数批量处理

        Args:
            run_ids: 运行ID列表
            func: 处理函数 func(context, run_id) -> result
            max_workers: 最大并行工作进程数
            show_progress: 是否显示进度
            progress_tracker: 进度追踪器（可选）

        Returns:
            结果字典 {run_id: result}
        """
        from waveform_analysis.core.foundation.progress import (
            ProgressTracker, format_throughput, format_time
        )

        results = {}
        start_time = time.time()

        # 创建或使用progress_tracker
        owns_tracker = False
        if progress_tracker is None and show_progress:
            progress_tracker = ProgressTracker()
            owns_tracker = True

        # 创建主进度条
        bar_name = None
        if progress_tracker:
            bar_name = "batch_custom"
            progress_tracker.create_bar(
                bar_name,
                total=len(run_ids),
                desc="Processing (custom)",
                unit="run"
            )

        try:
            if max_workers == 1:
                for i, run_id in enumerate(run_ids):
                    results[run_id] = func(self.context, run_id)

                    # 更新进度
                    if progress_tracker:
                        progress_tracker.update(bar_name, n=1)
                        elapsed = time.time() - start_time
                        throughput = (i + 1) / elapsed if elapsed > 0 else 0
                        progress_tracker.set_postfix(
                            bar_name,
                            throughput=format_throughput(throughput, "run")
                        )
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
                        results[run_id] = future.result()

                        # 更新进度
                        if progress_tracker:
                            progress_tracker.update(bar_name, n=1)
                            elapsed = time.time() - start_time
                            throughput = completed / elapsed if elapsed > 0 else 0
                            eta = progress_tracker.calculate_eta(bar_name)
                            progress_tracker.set_postfix(
                                bar_name,
                                throughput=format_throughput(throughput, "run"),
                                ETA=format_time(eta) if eta else "N/A"
                            )

        finally:
            # 关闭进度条
            if progress_tracker and bar_name:
                progress_tracker.close(bar_name)
            if owns_tracker and progress_tracker:
                progress_tracker.close_all()

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
