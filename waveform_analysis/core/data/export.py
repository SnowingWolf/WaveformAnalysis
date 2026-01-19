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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from waveform_analysis.core.foundation.utils import exporter, is_notebook_environment

logger = logging.getLogger(__name__)
export, __all__ = exporter()



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
        on_error: str = "continue",  # 'continue', 'stop', 'raise'
        progress_tracker: Optional[Any] = None,
        cancellation_token: Optional[Any] = None,
        jupyter_mode: Optional[bool] = None,
        progress_update_interval: float = 0.5,
    ) -> Dict[str, Any]:
        """
        批量处理多个run (优化版: 支持Jupyter环境)

        Args:
            run_ids: 运行ID列表
            data_name: 要处理的数据名称
            max_workers: 最大并行工作进程数
            show_progress: 是否显示进度
            on_error: 错误处理策略 ('continue', 'stop', 'raise')
            progress_tracker: 进度追踪器（可选，如为None则自动创建）
            cancellation_token: 取消令牌（可选，如为None则自动创建）
            jupyter_mode: Jupyter优化模式
                - None (默认): 自动检测环境
                - True: 强制使用Jupyter优化（轮询模式，禁用信号处理）
                - False: 强制使用标准模式（as_completed，启用信号处理）
            progress_update_interval: 进度更新最小间隔（秒），用于减少锁争用

        Returns:
            结果字典 {'results': {run_id: data}, 'errors': {run_id: error}}
        """
        from waveform_analysis.core.foundation.progress import (
            ProgressTracker,
            format_throughput,
            format_time,
        )
        from waveform_analysis.core.cancellation import (
            CancellationToken,
            get_cancellation_manager,
            TaskCancelledException,
        )

        # 自动检测 Jupyter 环境
        if jupyter_mode is None:
            jupyter_mode = is_notebook_environment()

        if jupyter_mode:
            self.logger.debug("Running in Jupyter-optimized mode (polling-based)")

        results = {}
        errors = {}
        start_time = time.time()

        # 创建或使用cancellation_token
        owns_token = False
        cancel_manager = None
        if cancellation_token is None:
            cancellation_token = CancellationToken()
            owns_token = True

            # 只在非 Jupyter 环境中启用信号处理
            if not jupyter_mode:
                cancel_manager = get_cancellation_manager()
                cancel_manager.enable()
                cancel_manager.register_token(cancellation_token)
            else:
                self.logger.debug("Jupyter mode: skipping signal handler registration")

        # 创建或使用progress_tracker
        # 在 Jupyter 环境下，禁用 tqdm 进度条（会导致阻塞），改用简单输出
        owns_tracker = False
        use_simple_progress = jupyter_mode and show_progress

        if not jupyter_mode and progress_tracker is None and show_progress:
            progress_tracker = ProgressTracker()
            owns_tracker = True

        # 创建主进度条（仅非 Jupyter 模式）
        bar_name = None
        if progress_tracker and not jupyter_mode:
            bar_name = f"batch_{data_name}"
            progress_tracker.create_bar(
                bar_name, total=len(run_ids), desc=f"Processing {data_name}", unit="run"
            )

        # Jupyter 模式下的简单进度显示
        if use_simple_progress:
            print(f"Processing {data_name}: 0/{len(run_ids)} runs", end="", flush=True)

        # 进度更新状态（用于批量更新）
        last_progress_update = start_time
        pending_progress_count = 0

        def _update_progress(completed_count: int, force: bool = False):
            """批量更新进度以减少锁争用"""
            nonlocal last_progress_update, pending_progress_count

            now = time.time()

            # Jupyter 模式：简单输出
            if use_simple_progress:
                if force or (now - last_progress_update >= 0.5):
                    print(
                        f"\rProcessing {data_name}: {completed_count}/{len(run_ids)} runs",
                        end="",
                        flush=True,
                    )
                    last_progress_update = now
                return

            # 标准模式：使用 ProgressTracker
            if not progress_tracker or not bar_name:
                return

            should_update = force or (
                pending_progress_count > 0
                and (now - last_progress_update >= progress_update_interval)
            )

            if should_update and pending_progress_count > 0:
                progress_tracker.update(bar_name, n=pending_progress_count)

                # 减少 set_postfix 调用频率（每秒最多一次）
                if force or (now - last_progress_update >= 1.0):
                    elapsed = now - start_time
                    throughput = completed_count / elapsed if elapsed > 0 else 0
                    eta = progress_tracker.calculate_eta(bar_name)
                    progress_tracker.set_postfix(
                        bar_name,
                        success=len(results),
                        failed=len(errors),
                        throughput=format_throughput(throughput, "run"),
                        ETA=format_time(eta) if eta else "N/A",
                    )

                last_progress_update = now
                pending_progress_count = 0

        try:
            if max_workers == 1:
                # 串行处理
                for i, run_id in enumerate(run_ids):
                    # 检查取消
                    if cancellation_token.is_cancelled():
                        self.logger.info(
                            f"Processing cancelled. Processed {i}/{len(run_ids)} runs."
                        )
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

                        if on_error == "stop":
                            break
                        elif on_error == "raise":
                            raise

                    pending_progress_count += 1
                    _update_progress(i + 1, force=(i == len(run_ids) - 1))
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

                    if jupyter_mode:
                        # Jupyter 优化模式：使用 wait() 轮询避免 as_completed 阻塞
                        pending = set(future_to_run.keys())
                        completed = 0

                        while pending:
                            # 检查取消
                            if cancellation_token.is_cancelled():
                                for f in pending:
                                    f.cancel()
                                self.logger.info(
                                    f"Processing cancelled. Processed {completed}/{len(run_ids)} runs."
                                )
                                break

                            # 使用短超时轮询，保持响应性
                            done, pending = wait(
                                pending,
                                timeout=0.1,  # 100ms 轮询间隔
                                return_when=FIRST_COMPLETED,
                            )

                            for future in done:
                                run_id = future_to_run[future]
                                completed += 1

                                try:
                                    data = future.result(timeout=0)  # 已完成，立即返回
                                    results[run_id] = data
                                except TaskCancelledException:
                                    self.logger.info(f"Task cancelled: {run_id}")
                                    cancellation_token.cancel()
                                    break
                                except Exception as e:
                                    errors[run_id] = e
                                    self.logger.error(f"Failed to process {run_id}: {e}")
                                    if on_error == "raise":
                                        raise

                                pending_progress_count += 1

                            # 批量进度更新
                            _update_progress(completed)

                        # 最终进度更新
                        _update_progress(completed, force=True)

                    else:
                        # 标准模式：使用 as_completed（非 Jupyter 环境）
                        completed = 0
                        for future in as_completed(future_to_run):
                            # 检查取消
                            if cancellation_token.is_cancelled():
                                for f in future_to_run:
                                    if not f.done():
                                        f.cancel()
                                self.logger.info(
                                    f"Processing cancelled. Processed {completed}/{len(run_ids)} runs."
                                )
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
                                if on_error == "raise":
                                    raise

                            pending_progress_count += 1
                            _update_progress(completed)

                        # 最终进度更新
                        _update_progress(completed, force=True)

        except KeyboardInterrupt:
            # 捕获KeyboardInterrupt并转换为取消
            self.logger.info("Interrupted by user (KeyboardInterrupt)")
            cancellation_token.cancel()
            raise
        finally:
            # Jupyter 模式：完成进度显示
            if use_simple_progress:
                print(f"\rProcessing {data_name}: {len(results)}/{len(run_ids)} runs ✓")

            # 关闭进度条
            if progress_tracker and bar_name:
                progress_tracker.close(bar_name)
            if owns_tracker and progress_tracker:
                progress_tracker.close_all()

            # 注销取消token（仅在非 Jupyter 模式下注册过）
            if owns_token and cancel_manager:
                cancel_manager.unregister_token(cancellation_token)

        if errors and show_progress and not progress_tracker:
            # 如果没有进度条，打印错误摘要
            print(f"\nCompleted with {len(errors)} errors")

        return {"results": results, "errors": errors}

    def process_with_custom_func(
        self,
        run_ids: List[str],
        func: Callable,
        max_workers: Optional[int] = None,
        show_progress: bool = True,
        progress_tracker: Optional[Any] = None,
        jupyter_mode: Optional[bool] = None,
        progress_update_interval: float = 0.5,
    ) -> Dict[str, Any]:
        """
        使用自定义函数批量处理 (优化版: 支持Jupyter环境)

        Args:
            run_ids: 运行ID列表
            func: 处理函数 func(context, run_id) -> result
            max_workers: 最大并行工作进程数
            show_progress: 是否显示进度
            progress_tracker: 进度追踪器（可选）
            jupyter_mode: Jupyter优化模式 (None=自动检测)
            progress_update_interval: 进度更新最小间隔（秒）

        Returns:
            结果字典 {run_id: result}
        """
        from waveform_analysis.core.foundation.progress import (
            ProgressTracker,
            format_throughput,
            format_time,
        )

        # 自动检测 Jupyter 环境
        if jupyter_mode is None:
            jupyter_mode = is_notebook_environment()

        results = {}
        start_time = time.time()

        # 创建或使用progress_tracker
        # 在 Jupyter 环境下，禁用 tqdm 进度条（会导致阻塞），改用简单输出
        owns_tracker = False
        use_simple_progress = jupyter_mode and show_progress

        if not jupyter_mode and progress_tracker is None and show_progress:
            progress_tracker = ProgressTracker()
            owns_tracker = True

        # 创建主进度条（仅非 Jupyter 模式）
        bar_name = None
        if progress_tracker and not jupyter_mode:
            bar_name = "batch_custom"
            progress_tracker.create_bar(
                bar_name, total=len(run_ids), desc="Processing (custom)", unit="run"
            )

        # Jupyter 模式下的简单进度显示
        if use_simple_progress:
            print(f"Processing (custom): 0/{len(run_ids)} runs", end="", flush=True)

        # 进度更新状态（用于批量更新）
        last_progress_update = start_time
        pending_progress_count = 0

        def _update_progress(completed_count: int, force: bool = False):
            """批量更新进度以减少锁争用"""
            nonlocal last_progress_update, pending_progress_count

            now = time.time()

            # Jupyter 模式：简单输出
            if use_simple_progress:
                if force or (now - last_progress_update >= 0.5):
                    print(
                        f"\rProcessing (custom): {completed_count}/{len(run_ids)} runs",
                        end="",
                        flush=True,
                    )
                    last_progress_update = now
                return

            # 标准模式：使用 ProgressTracker
            if not progress_tracker or not bar_name:
                return

            should_update = force or (
                pending_progress_count > 0
                and (now - last_progress_update >= progress_update_interval)
            )

            if should_update and pending_progress_count > 0:
                progress_tracker.update(bar_name, n=pending_progress_count)

                if force or (now - last_progress_update >= 1.0):
                    elapsed = now - start_time
                    throughput = completed_count / elapsed if elapsed > 0 else 0
                    eta = progress_tracker.calculate_eta(bar_name)
                    progress_tracker.set_postfix(
                        bar_name,
                        throughput=format_throughput(throughput, "run"),
                        ETA=format_time(eta) if eta else "N/A",
                    )

                last_progress_update = now
                pending_progress_count = 0

        try:
            if max_workers == 1:
                for i, run_id in enumerate(run_ids):
                    results[run_id] = func(self.context, run_id)
                    pending_progress_count += 1
                    _update_progress(i + 1, force=(i == len(run_ids) - 1))
            else:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_run = {
                        executor.submit(func, self.context, run_id): run_id for run_id in run_ids
                    }

                    if jupyter_mode:
                        # Jupyter 优化模式：使用 wait() 轮询
                        pending = set(future_to_run.keys())
                        completed = 0

                        while pending:
                            done, pending = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)

                            for future in done:
                                run_id = future_to_run[future]
                                completed += 1
                                results[run_id] = future.result(timeout=0)
                                pending_progress_count += 1

                            _update_progress(completed)

                        _update_progress(completed, force=True)
                    else:
                        # 标准模式：使用 as_completed
                        completed = 0
                        for future in as_completed(future_to_run):
                            run_id = future_to_run[future]
                            completed += 1
                            results[run_id] = future.result()
                            pending_progress_count += 1
                            _update_progress(completed)

                        _update_progress(completed, force=True)

        finally:
            # Jupyter 模式：完成进度显示
            if use_simple_progress:
                print(f"\rProcessing (custom): {len(results)}/{len(run_ids)} runs ✓")

            # 关闭进度条
            if progress_tracker and bar_name:
                progress_tracker.close(bar_name)
            if owns_tracker and progress_tracker:
                progress_tracker.close_all()

        return results




@export
class DataExporter:
    """
    统一的数据导出接口

    支持多种格式: Parquet, HDF5, CSV, JSON, NumPy

    使用示例:
        exporter = DataExporter()
        exporter.export(data, 'output.parquet', format='parquet')
    """

    SUPPORTED_FORMATS = ["parquet", "hdf5", "csv", "json", "npy", "npz"]

    def __init__(self):
        """初始化导出器"""
        self.logger = logging.getLogger(self.__class__.__name__)

    def export(
        self,
        data: Union[np.ndarray, pd.DataFrame, Dict[str, Any]],
        output_path: Union[str, Path],
        format: Optional[str] = None,
        **kwargs,
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
            format = output_path.suffix.lstrip(".")

        format = format.lower()

        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {format}. Supported: {self.SUPPORTED_FORMATS}")

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 根据格式导出
        if format == "parquet":
            self._export_parquet(data, output_path, **kwargs)
        elif format == "hdf5" or format == "h5":
            self._export_hdf5(data, output_path, **kwargs)
        elif format == "csv":
            self._export_csv(data, output_path, **kwargs)
        elif format == "json":
            self._export_json(data, output_path, **kwargs)
        elif format == "npy":
            self._export_npy(data, output_path, **kwargs)
        elif format == "npz":
            self._export_npz(data, output_path, **kwargs)

        self.logger.info(f"Exported data to {output_path} (format: {format})")

    def _export_parquet(self, data, output_path, **kwargs):
        """导出为Parquet格式"""
        df = self._to_dataframe(data)
        df.to_parquet(output_path, **kwargs)

    def _export_hdf5(self, data, output_path, key="data", **kwargs):
        """导出为HDF5格式"""
        df = self._to_dataframe(data)
        df.to_hdf(output_path, key=key, mode="w", **kwargs)

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

            with open(output_path, "w") as f:
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
                return pd.DataFrame({"data": data})
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
    format: str = "parquet",
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
        run_ids=run_ids, data_name=data_name, max_workers=max_workers, show_progress=True
    )

    # 导出每个run的数据
    for run_id, data in batch_results["results"].items():
        output_path = output_dir / f"{run_id}_{data_name}.{format}"
        try:
            exporter.export(data, output_path, format=format)
        except Exception as e:
            logger.error(f"Failed to export {run_id}: {e}")

    print(f"\nExported {len(batch_results['results'])} runs to {output_dir}")
