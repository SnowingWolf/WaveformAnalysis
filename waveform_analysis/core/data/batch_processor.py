# -*- coding: utf-8 -*-
"""
Batch processing utilities for Context.
"""

import logging
import shutil
import tempfile
import time
import traceback
from concurrent.futures import (
    ThreadPoolExecutor,
    ProcessPoolExecutor,
    as_completed,
    wait,
    FIRST_COMPLETED,
)
from typing import Any, Callable, Dict, List, Optional, Tuple

from waveform_analysis.core.foundation.utils import exporter, is_notebook_environment

logger = logging.getLogger(__name__)
export, __all__ = exporter()


def _build_error_info(exc: Exception) -> Dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }


def _apply_storage_dir_strategy(context: Any, strategy: str) -> Optional[str]:
    if strategy == "shared":
        return None

    temp_dir = tempfile.mkdtemp(prefix="batch_cache_")
    if hasattr(context, "storage_dir"):
        context.storage_dir = temp_dir
    storage = getattr(context, "storage", None)
    if storage is not None:
        if hasattr(storage, "work_dir"):
            storage.work_dir = temp_dir
        elif hasattr(storage, "set_work_dir"):
            storage.set_work_dir(temp_dir)
    return temp_dir


def _cleanup_temp_dir(temp_dir: Optional[str], clean_temp_cache: bool) -> None:
    if temp_dir and clean_temp_cache:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _run_single_task(
    run_id: str,
    data_name: str,
    context_factory: Callable[[], Any],
    storage_dir_strategy: str,
    clean_temp_cache: bool,
    retries: int,
    retry_on: Optional[Tuple[type, ...]],
) -> Tuple[str, Any, Optional[Dict[str, str]], Dict[str, Any]]:
    from waveform_analysis.core.cancellation import TaskCancelledException

    start_time = time.time()
    attempts = 0
    error_info: Optional[Dict[str, str]] = None

    while True:
        attempts += 1
        context = context_factory()
        temp_dir = _apply_storage_dir_strategy(context, storage_dir_strategy)

        try:
            data = context.get_data(run_id, data_name)
            meta = {
                "status": "success",
                "elapsed": time.time() - start_time,
                "attempts": attempts,
            }
            return run_id, data, None, meta
        except TaskCancelledException as exc:
            error_info = _build_error_info(exc)
            meta = {
                "status": "cancelled",
                "elapsed": time.time() - start_time,
                "attempts": attempts,
            }
            return run_id, None, error_info, meta
        except Exception as exc:
            error_info = _build_error_info(exc)
            retry_types = retry_on or ()
            should_retry = attempts <= retries and retry_types and isinstance(exc, retry_types)
            if should_retry:
                _cleanup_temp_dir(temp_dir, clean_temp_cache)
                continue
            meta = {
                "status": "failed",
                "elapsed": time.time() - start_time,
                "attempts": attempts,
            }
            return run_id, None, error_info, meta
        finally:
            _cleanup_temp_dir(temp_dir, clean_temp_cache)


def _run_single_custom_task(
    run_id: str,
    context_factory: Callable[[], Any],
    func: Callable[[Any, str], Any],
    storage_dir_strategy: str,
    clean_temp_cache: bool,
    retries: int,
    retry_on: Optional[Tuple[type, ...]],
) -> Tuple[str, Any, Optional[Dict[str, str]], Dict[str, Any]]:
    start_time = time.time()
    attempts = 0
    error_info: Optional[Dict[str, str]] = None

    while True:
        attempts += 1
        context = context_factory()
        temp_dir = _apply_storage_dir_strategy(context, storage_dir_strategy)

        try:
            data = func(context, run_id)
            meta = {
                "status": "success",
                "elapsed": time.time() - start_time,
                "attempts": attempts,
            }
            return run_id, data, None, meta
        except Exception as exc:
            error_info = _build_error_info(exc)
            retry_types = retry_on or ()
            should_retry = attempts <= retries and retry_types and isinstance(exc, retry_types)
            if should_retry:
                _cleanup_temp_dir(temp_dir, clean_temp_cache)
                continue
            meta = {
                "status": "failed",
                "elapsed": time.time() - start_time,
                "attempts": attempts,
            }
            return run_id, None, error_info, meta
        finally:
            _cleanup_temp_dir(temp_dir, clean_temp_cache)


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
        context_factory: Optional[Callable[[], Any]] = None,
        executor_type: str = "thread",
        storage_dir_strategy: str = "shared",
        clean_temp_cache: bool = True,
        show_progress: bool = True,
        on_error: str = "continue",  # 'continue', 'stop', 'raise'
        progress_tracker: Optional[Any] = None,
        cancellation_token: Optional[Any] = None,
        jupyter_mode: Optional[bool] = None,
        progress_update_interval: float = 0.5,
        poll_interval: float = 0.1,
        retries: int = 0,
        retry_on: Optional[Tuple[type, ...]] = None,
    ) -> Dict[str, Any]:
        """
        批量处理多个run (优化版: 支持Jupyter环境)

        Args:
            run_ids: 运行ID列表
            data_name: 要处理的数据名称
            max_workers: 最大并行工作进程数
            context_factory: 并行时为每个任务创建独立 Context 的工厂函数
            executor_type: 执行器类型 ("thread" 或 "process")
            storage_dir_strategy: 缓存目录策略 ("shared" | "per_worker" | "readonly")
            clean_temp_cache: 是否清理临时缓存目录
            show_progress: 是否显示进度
            on_error: 错误处理策略 ('continue', 'stop', 'raise')
            progress_tracker: 进度追踪器（可选，如为None则自动创建）
            cancellation_token: 取消令牌（可选，如为None则自动创建）
            jupyter_mode: Jupyter优化模式
                - None (默认): 自动检测环境
                - True: 强制使用Jupyter优化（轮询模式，禁用信号处理）
                - False: 强制使用标准模式（as_completed，启用信号处理）
            progress_update_interval: 进度更新最小间隔（秒），用于减少锁争用
            poll_interval: Jupyter 轮询等待间隔（秒）
            retries: 失败重试次数
            retry_on: 重试异常类型元组

        Returns:
            结果字典 {'results': ..., 'errors': ..., 'meta': ..., 'ordered_run_ids': ...}
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

        results: Dict[str, Any] = {}
        errors: Dict[str, Dict[str, str]] = {}
        meta: Dict[str, Dict[str, Any]] = {}
        ordered_run_ids = list(run_ids)
        start_time = time.time()

        if executor_type not in ("thread", "process"):
            raise ValueError("executor_type must be 'thread' or 'process'")

        if storage_dir_strategy not in ("shared", "per_worker", "readonly"):
            raise ValueError("storage_dir_strategy must be 'shared', 'per_worker', or 'readonly'")

        parallel_requested = max_workers is None or (max_workers is not None and max_workers > 1)
        use_parallel = parallel_requested
        if use_parallel and context_factory is None:
            self.logger.warning("context_factory is required for parallel execution; falling back to serial mode.")
            use_parallel = False
            max_workers = 1

        if not use_parallel and storage_dir_strategy != "shared":
            self.logger.warning("storage_dir_strategy is ignored in serial mode; using 'shared'.")
            storage_dir_strategy = "shared"

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
            progress_tracker.create_bar(bar_name, total=len(run_ids), desc=f"Processing {data_name}", unit="run")

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
                pending_progress_count > 0 and (now - last_progress_update >= progress_update_interval)
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

        def _record_outcome(
            run_id: str,
            data: Any,
            error_info: Optional[Dict[str, str]],
            meta_info: Dict[str, Any],
        ) -> None:
            meta[run_id] = meta_info
            if data is not None:
                results[run_id] = data
            if error_info is not None:
                errors[run_id] = error_info

        def _mark_skipped(remaining: List[str]) -> None:
            for run_id in remaining:
                if run_id not in meta:
                    meta[run_id] = {"status": "skipped", "elapsed": 0.0, "attempts": 0}

        try:
            if not use_parallel:
                # 串行处理
                for i, run_id in enumerate(run_ids):
                    # 检查取消
                    if cancellation_token.is_cancelled():
                        self.logger.info(f"Processing cancelled. Processed {i}/{len(run_ids)} runs.")
                        _mark_skipped(run_ids[i:])
                        break

                    run_start = time.time()
                    attempts = 0
                    stop_processing = False
                    while True:
                        attempts += 1
                        try:
                            data = self.context.get_data(run_id, data_name)
                            _record_outcome(
                                run_id,
                                data,
                                None,
                                {
                                    "status": "success",
                                    "elapsed": time.time() - run_start,
                                    "attempts": attempts,
                                },
                            )
                            break
                        except TaskCancelledException as exc:
                            _record_outcome(
                                run_id,
                                None,
                                _build_error_info(exc),
                                {
                                    "status": "cancelled",
                                    "elapsed": time.time() - run_start,
                                    "attempts": attempts,
                                },
                            )
                            cancellation_token.cancel()
                            _mark_skipped(run_ids[i + 1 :])
                            stop_processing = True
                            break
                        except Exception as exc:
                            retry_types = retry_on or ()
                            should_retry = attempts <= retries and retry_types and isinstance(exc, retry_types)
                            if should_retry:
                                continue

                            _record_outcome(
                                run_id,
                                None,
                                _build_error_info(exc),
                                {
                                    "status": "failed",
                                    "elapsed": time.time() - run_start,
                                    "attempts": attempts,
                                },
                            )
                            if on_error == "stop":
                                _mark_skipped(run_ids[i + 1 :])
                                stop_processing = True
                            elif on_error == "raise":
                                raise
                            break

                    pending_progress_count += 1
                    _update_progress(i + 1, force=(i == len(run_ids) - 1))
                    if stop_processing:
                        break
            else:
                executor_cls = ProcessPoolExecutor if executor_type == "process" else ThreadPoolExecutor

                with executor_cls(max_workers=max_workers) as executor:
                    # 注册executor清理回调
                    def shutdown_executor():
                        """在取消时立即关闭executor"""
                        try:
                            executor.shutdown(wait=False, cancel_futures=True)
                        except Exception as exc:
                            self.logger.debug(f"Error shutting down executor: {exc}")

                    cancellation_token.register_callback(shutdown_executor)

                    # 提交任务
                    future_to_run = {
                        executor.submit(
                            _run_single_task,
                            run_id,
                            data_name,
                            context_factory,
                            storage_dir_strategy,
                            clean_temp_cache,
                            retries,
                            retry_on,
                        ): run_id
                        for run_id in run_ids
                    }

                    def _cancel_pending(pending_futures):
                        for fut in pending_futures:
                            fut.cancel()

                    if jupyter_mode:
                        # Jupyter 优化模式：使用 wait() 轮询避免 as_completed 阻塞
                        pending = set(future_to_run.keys())
                        completed = 0
                        stop_processing = False

                        while pending:
                            # 检查取消
                            if cancellation_token.is_cancelled():
                                _cancel_pending(pending)
                                self.logger.info(
                                    f"Processing cancelled. Processed {completed}/{len(run_ids)} runs."
                                )
                                _mark_skipped([future_to_run[f] for f in pending])
                                break

                            # 使用短超时轮询，保持响应性
                            done, pending = wait(
                                pending,
                                timeout=poll_interval,
                                return_when=FIRST_COMPLETED,
                            )

                            for future in done:
                                run_id = future_to_run[future]
                                completed += 1

                                try:
                                    run_id, data, error_info, meta_info = future.result(timeout=0)
                                except Exception as exc:
                                    data = None
                                    error_info = _build_error_info(exc)
                                    meta_info = {"status": "failed", "elapsed": 0.0, "attempts": 1}

                                _record_outcome(run_id, data, error_info, meta_info)

                                if error_info and on_error in ("stop", "raise"):
                                    _cancel_pending(pending)
                                    _mark_skipped([future_to_run[f] for f in pending])
                                    stop_processing = True
                                    if on_error == "raise":
                                        raise
                                    break

                                pending_progress_count += 1

                            # 批量进度更新
                            _update_progress(completed)
                            if stop_processing:
                                break

                        # 最终进度更新
                        _update_progress(completed, force=True)

                    else:
                        # 标准模式：使用 as_completed（非 Jupyter 环境）
                        completed = 0
                        stop_processing = False
                        for future in as_completed(future_to_run):
                            # 检查取消
                            if cancellation_token.is_cancelled():
                                _cancel_pending([f for f in future_to_run if not f.done()])
                                self.logger.info(
                                    f"Processing cancelled. Processed {completed}/{len(run_ids)} runs."
                                )
                                _mark_skipped([future_to_run[f] for f in future_to_run if not f.done()])
                                break

                            run_id = future_to_run[future]
                            completed += 1

                            try:
                                run_id, data, error_info, meta_info = future.result()
                            except Exception as exc:
                                data = None
                                error_info = _build_error_info(exc)
                                meta_info = {"status": "failed", "elapsed": 0.0, "attempts": 1}

                            _record_outcome(run_id, data, error_info, meta_info)

                            if error_info and on_error in ("stop", "raise"):
                                _cancel_pending([f for f in future_to_run if not f.done()])
                                _mark_skipped([future_to_run[f] for f in future_to_run if not f.done()])
                                stop_processing = True
                                if on_error == "raise":
                                    raise
                                break

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

        return {
            "results": results,
            "errors": errors,
            "meta": meta,
            "ordered_run_ids": ordered_run_ids,
        }

    def process_with_custom_func(
        self,
        run_ids: List[str],
        func: Callable,
        max_workers: Optional[int] = None,
        context_factory: Optional[Callable[[], Any]] = None,
        executor_type: str = "thread",
        storage_dir_strategy: str = "shared",
        clean_temp_cache: bool = True,
        show_progress: bool = True,
        on_error: str = "continue",
        progress_tracker: Optional[Any] = None,
        jupyter_mode: Optional[bool] = None,
        progress_update_interval: float = 0.5,
        poll_interval: float = 0.1,
        retries: int = 0,
        retry_on: Optional[Tuple[type, ...]] = None,
    ) -> Dict[str, Any]:
        """
        使用自定义函数批量处理 (优化版: 支持Jupyter环境)

        Args:
            run_ids: 运行ID列表
            func: 处理函数 func(context, run_id) -> result
            max_workers: 最大并行工作进程数
            context_factory: 并行时为每个任务创建独立 Context 的工厂函数
            executor_type: 执行器类型 ("thread" 或 "process")
            storage_dir_strategy: 缓存目录策略 ("shared" | "per_worker" | "readonly")
            clean_temp_cache: 是否清理临时缓存目录
            show_progress: 是否显示进度
            on_error: 错误处理策略 ('continue', 'stop', 'raise')
            progress_tracker: 进度追踪器（可选）
            jupyter_mode: Jupyter优化模式 (None=自动检测)
            progress_update_interval: 进度更新最小间隔（秒）
            poll_interval: Jupyter 轮询等待间隔（秒）
            retries: 失败重试次数
            retry_on: 重试异常类型元组

        Returns:
            结果字典 {'results': ..., 'errors': ..., 'meta': ..., 'ordered_run_ids': ...}
        """
        from waveform_analysis.core.foundation.progress import (
            ProgressTracker,
            format_throughput,
            format_time,
        )

        # 自动检测 Jupyter 环境
        if jupyter_mode is None:
            jupyter_mode = is_notebook_environment()

        results: Dict[str, Any] = {}
        errors: Dict[str, Dict[str, str]] = {}
        meta: Dict[str, Dict[str, Any]] = {}
        ordered_run_ids = list(run_ids)
        start_time = time.time()

        if executor_type not in ("thread", "process"):
            raise ValueError("executor_type must be 'thread' or 'process'")

        if storage_dir_strategy not in ("shared", "per_worker", "readonly"):
            raise ValueError("storage_dir_strategy must be 'shared', 'per_worker', or 'readonly'")

        parallel_requested = max_workers is None or (max_workers is not None and max_workers > 1)
        use_parallel = parallel_requested
        if use_parallel and context_factory is None:
            self.logger.warning("context_factory is required for parallel execution; falling back to serial mode.")
            use_parallel = False
            max_workers = 1

        if not use_parallel and storage_dir_strategy != "shared":
            self.logger.warning("storage_dir_strategy is ignored in serial mode; using 'shared'.")
            storage_dir_strategy = "shared"

        # 创建或使用progress_tracker
        owns_tracker = False
        use_simple_progress = jupyter_mode and show_progress

        if not jupyter_mode and progress_tracker is None and show_progress:
            progress_tracker = ProgressTracker()
            owns_tracker = True

        # 创建主进度条（仅非 Jupyter 模式）
        bar_name = None
        if progress_tracker and not jupyter_mode:
            bar_name = "batch_custom"
            progress_tracker.create_bar(bar_name, total=len(run_ids), desc="Processing (custom)", unit="run")

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
                pending_progress_count > 0 and (now - last_progress_update >= progress_update_interval)
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

        def _record_outcome(
            run_id: str,
            data: Any,
            error_info: Optional[Dict[str, str]],
            meta_info: Dict[str, Any],
        ) -> None:
            meta[run_id] = meta_info
            if data is not None:
                results[run_id] = data
            if error_info is not None:
                errors[run_id] = error_info

        def _mark_skipped(remaining: List[str]) -> None:
            for run_id in remaining:
                if run_id not in meta:
                    meta[run_id] = {"status": "skipped", "elapsed": 0.0, "attempts": 0}

        try:
            if not use_parallel:
                for i, run_id in enumerate(run_ids):
                    run_start = time.time()
                    attempts = 0
                    stop_processing = False
                    while True:
                        attempts += 1
                        try:
                            data = func(self.context, run_id)
                            _record_outcome(
                                run_id,
                                data,
                                None,
                                {
                                    "status": "success",
                                    "elapsed": time.time() - run_start,
                                    "attempts": attempts,
                                },
                            )
                            break
                        except Exception as exc:
                            retry_types = retry_on or ()
                            should_retry = attempts <= retries and retry_types and isinstance(exc, retry_types)
                            if should_retry:
                                continue

                            _record_outcome(
                                run_id,
                                None,
                                _build_error_info(exc),
                                {
                                    "status": "failed",
                                    "elapsed": time.time() - run_start,
                                    "attempts": attempts,
                                },
                            )
                            if on_error == "stop":
                                _mark_skipped(run_ids[i + 1 :])
                                stop_processing = True
                            elif on_error == "raise":
                                raise
                            break

                    pending_progress_count += 1
                    _update_progress(i + 1, force=(i == len(run_ids) - 1))
                    if stop_processing:
                        break
            else:
                executor_cls = ProcessPoolExecutor if executor_type == "process" else ThreadPoolExecutor
                with executor_cls(max_workers=max_workers) as executor:
                    future_to_run = {
                        executor.submit(
                            _run_single_custom_task,
                            run_id,
                            context_factory,
                            func,
                            storage_dir_strategy,
                            clean_temp_cache,
                            retries,
                            retry_on,
                        ): run_id
                        for run_id in run_ids
                    }

                    def _cancel_pending(pending_futures):
                        for fut in pending_futures:
                            fut.cancel()

                    if jupyter_mode:
                        pending = set(future_to_run.keys())
                        completed = 0
                        stop_processing = False

                        while pending:
                            done, pending = wait(
                                pending,
                                timeout=poll_interval,
                                return_when=FIRST_COMPLETED,
                            )

                            for future in done:
                                run_id = future_to_run[future]
                                completed += 1
                                try:
                                    run_id, data, error_info, meta_info = future.result(timeout=0)
                                except Exception as exc:
                                    data = None
                                    error_info = _build_error_info(exc)
                                    meta_info = {"status": "failed", "elapsed": 0.0, "attempts": 1}

                                _record_outcome(run_id, data, error_info, meta_info)

                                if error_info and on_error in ("stop", "raise"):
                                    _cancel_pending(pending)
                                    _mark_skipped([future_to_run[f] for f in pending])
                                    stop_processing = True
                                    if on_error == "raise":
                                        raise
                                    break

                                pending_progress_count += 1

                            _update_progress(completed)
                            if stop_processing:
                                break

                        _update_progress(completed, force=True)
                    else:
                        completed = 0
                        stop_processing = False
                        for future in as_completed(future_to_run):
                            run_id = future_to_run[future]
                            completed += 1
                            try:
                                run_id, data, error_info, meta_info = future.result()
                            except Exception as exc:
                                data = None
                                error_info = _build_error_info(exc)
                                meta_info = {"status": "failed", "elapsed": 0.0, "attempts": 1}

                            _record_outcome(run_id, data, error_info, meta_info)

                            if error_info and on_error in ("stop", "raise"):
                                _cancel_pending([f for f in future_to_run if not f.done()])
                                _mark_skipped([future_to_run[f] for f in future_to_run if not f.done()])
                                stop_processing = True
                                if on_error == "raise":
                                    raise
                                break

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

        if errors and show_progress and not progress_tracker:
            print(f"\nCompleted with {len(errors)} errors")

        return {
            "results": results,
            "errors": errors,
            "meta": meta,
            "ordered_run_ids": ordered_run_ids,
        }

    def process_runs_with_config_grid(
        self,
        run_ids: List[str],
        data_name: str,
        plugin_name: str,
        configs: List[Dict[str, Any]],
        max_workers: Optional[int] = None,
        context_factory: Optional[Callable[[], Any]] = None,
        executor_type: str = "thread",
        storage_dir_strategy: str = "shared",
        clean_temp_cache: bool = True,
        show_progress: bool = True,
        on_error: str = "continue",
        jupyter_mode: Optional[bool] = None,
        progress_update_interval: float = 0.5,
        poll_interval: float = 0.1,
        retries: int = 0,
        retry_on: Optional[Tuple[type, ...]] = None,
        tmp_cache: bool = False,
    ) -> Dict[str, Any]:
        """
        配置网格扫参批处理

        Args:
            run_ids: 运行ID列表
            data_name: 数据名称
            plugin_name: 目标插件名称
            configs: 配置列表（每个元素为 dict）
            max_workers: 最大并行工作进程数
            context_factory: 并行时为每个任务创建独立 Context 的工厂函数
            executor_type: 执行器类型 ("thread" 或 "process")
            storage_dir_strategy: 缓存目录策略 ("shared" | "per_worker" | "readonly")
            clean_temp_cache: 是否清理临时缓存目录
            show_progress: 是否显示进度
            on_error: 错误处理策略 ('continue', 'stop', 'raise')
            jupyter_mode: Jupyter优化模式 (None=自动检测)
            progress_update_interval: 进度更新最小间隔（秒）
            poll_interval: Jupyter 轮询等待间隔（秒）
            retries: 失败重试次数
            retry_on: 重试异常类型元组
            tmp_cache: 是否为每个配置使用临时缓存目录

        Returns:
            结果字典 {"configs": configs, "results": [ {config, batch} ... ]}
        """
        results: List[Dict[str, Any]] = []

        if tmp_cache:
            storage_dir_strategy = "per_worker"
            if context_factory is None:
                self.logger.warning("tmp_cache requires context_factory; using shared cache in serial mode.")

        for idx, config in enumerate(configs):
            if context_factory is None:
                ctx = self.context
                ctx.set_config(config, plugin_name=plugin_name)
                if hasattr(ctx, "clear_performance_caches"):
                    ctx.clear_performance_caches()
                batch = self.process_runs(
                    run_ids=run_ids,
                    data_name=data_name,
                    max_workers=1,
                    context_factory=None,
                    executor_type=executor_type,
                    storage_dir_strategy="shared",
                    clean_temp_cache=clean_temp_cache,
                    show_progress=show_progress,
                    on_error=on_error,
                    jupyter_mode=jupyter_mode,
                    progress_update_interval=progress_update_interval,
                    poll_interval=poll_interval,
                    retries=retries,
                    retry_on=retry_on,
                )
            else:
                def _config_factory(config=config) -> Any:
                    ctx = context_factory()
                    ctx.set_config(config, plugin_name=plugin_name)
                    if hasattr(ctx, "clear_performance_caches"):
                        ctx.clear_performance_caches()
                    return ctx

                batch = self.process_runs(
                    run_ids=run_ids,
                    data_name=data_name,
                    max_workers=max_workers,
                    context_factory=_config_factory,
                    executor_type=executor_type,
                    storage_dir_strategy=storage_dir_strategy,
                    clean_temp_cache=clean_temp_cache,
                    show_progress=show_progress,
                    on_error=on_error,
                    jupyter_mode=jupyter_mode,
                    progress_update_interval=progress_update_interval,
                    poll_interval=poll_interval,
                    retries=retries,
                    retry_on=retry_on,
                )

            results.append({"config_index": idx, "config": config, "batch": batch})

        return {"configs": configs, "results": results}
