from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import time
from typing import Any, cast

import numpy as np
import pandas as pd

from .foundation.exceptions import ErrorSeverity
from .foundation.utils import OneTimeGenerator
from .plugins.core.base import Plugin


class ContextExecutionDomain:
    """Plugin execution helpers used by Context."""

    def __init__(self, context: Any) -> None:
        self.ctx = context

    def build_dependency_graph(self, plan: list[str], run_id: str) -> dict[str, list[str]]:
        """构建依赖图: plugin_name -> [依赖的 plugin_name 列表]

        Args:
            plan: 执行计划（插件名称列表）
            run_id: 运行 ID

        Returns:
            依赖图字典
        """
        graph: dict[str, list[str]] = {}
        for name in plan:
            if name not in self.ctx._plugins:
                graph[name] = []
                continue
            plugin = self.ctx._plugins[name]
            deps = self.ctx._plugin_domain.get_dependency_names(plugin, run_id=run_id)
            # 仅保留在 plan 中的依赖
            graph[name] = [d for d in deps if d in plan]
        return graph

    def get_execution_layers(self, graph: dict[str, list[str]]) -> list[list[str]]:
        """将依赖图分层，返回可并行执行的层

        Args:
            graph: 依赖图

        Returns:
            分层列表，每层是可并行执行的插件列表
        """
        # 计算入度
        in_degree: dict[str, int] = defaultdict(int)
        for node in graph:
            in_degree[node] = 0
        for node, deps in graph.items():
            for _dep in deps:
                in_degree[node] += 1

        layers: list[list[str]] = []
        remaining = set(graph.keys())

        while remaining:
            # 找到所有入度为 0 的节点（当前层）
            current_layer = [node for node in remaining if in_degree[node] == 0]
            if not current_layer:
                # 存在循环依赖，剩余节点无法执行
                self.ctx.logger.warning(
                    f"Circular dependency detected, cannot execute: {remaining}"
                )
                break

            layers.append(current_layer)
            remaining -= set(current_layer)

            # 更新入度
            for node in current_layer:
                for successor in graph:
                    if node in graph[successor]:
                        in_degree[successor] -= 1

        return layers

    def check_reentrancy(self, run_id: str, data_name: str) -> None:
        with self.ctx._in_progress_lock:
            if (run_id, data_name) in self.ctx._in_progress:
                raise RuntimeError(
                    f"Re-entrant call for ({run_id}, {data_name}) detected. "
                    "This usually indicates a circular dependency at runtime."
                )
            self.ctx._in_progress[(run_id, data_name)] = True

    def resolve_execution_plan(self, run_id: str, data_name: str) -> list[str]:
        try:
            with self.ctx.profiler.timeit("context.resolve_dependencies"):
                cache_key = (run_id, data_name)
                if cache_key in self.ctx._execution_plan_cache:
                    plan = self.ctx._execution_plan_cache[cache_key]
                else:
                    plan = self.ctx.resolve_dependencies(data_name, run_id=run_id)
                    self.ctx._execution_plan_cache[cache_key] = plan
            return plan
        except ValueError:
            val = self.ctx._get_data_from_memory(run_id, data_name)
            if val is not None:
                return []
            raise

    def compute_needed_set(
        self,
        run_id: str,
        data_name: str,
        plan: list[str],
        target_is_missing: bool = False,
    ) -> set[str]:
        needed: set[str] = set()
        visited: set[str] = set()

        def dfs(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            # get_data 第 2 步已确认目标非内存/磁盘命中；跳过重复检查。
            if not (name == data_name and target_is_missing):
                if self.ctx._is_cache_hit(run_id, name, load=False):
                    return
            if name not in self.ctx._plugins:
                return
            plugin = self.ctx._plugins[name]
            for dep_name in self.ctx._plugin_domain.get_dependency_names(plugin, run_id=run_id):
                dfs(dep_name)
            needed.add(name)

        dfs(data_name)
        return {name for name in plan if name in needed}

    def init_progress_tracking(
        self,
        show_progress: bool,
        plan: list[str],
        run_id: str,
        data_name: str,
        progress_desc: str | None,
    ) -> tuple[Any | None, str | None]:
        if show_progress and len(plan) > 0:
            from waveform_analysis.core.foundation.progress import get_global_tracker

            tracker = get_global_tracker()
            bar_name = f"load_{run_id}_{data_name}"
            desc = progress_desc or f"Loading {data_name}"
            tracker.create_bar(bar_name, total=len(plan), desc=desc, unit="plugin")
            return tracker, bar_name
        return None, None

    def calculate_input_size(self, plugin: Plugin, run_id: str) -> float | None:
        if not (self.ctx.stats_collector and self.ctx.stats_collector.mode == "detailed"):
            return None
        try:
            total_bytes = 0
            for dep_name in self.ctx._plugin_domain.get_dependency_names(plugin, run_id=run_id):
                dep_data = self.ctx._get_data_from_memory(run_id, dep_name)
                if dep_data is not None:
                    if isinstance(dep_data, np.ndarray):
                        total_bytes += dep_data.nbytes
                    elif isinstance(dep_data, list):
                        total_bytes += sum(
                            arr.nbytes for arr in dep_data if isinstance(arr, np.ndarray)
                        )
            return total_bytes / (1024 * 1024) if total_bytes > 0 else None
        except (AttributeError, TypeError) as e:
            self.ctx.logger.debug("Could not calculate input size for %s: %s", plugin.provides, e)
            return None
        except Exception as e:
            self.ctx.logger.warning(
                "Unexpected error calculating input size for %s: %s", plugin.provides, e
            )
            return None

    def prepare_side_effect_isolation(self, plugin: Plugin, run_id: str, kwargs: dict) -> dict:
        if getattr(plugin, "is_side_effect", False):
            if hasattr(self.ctx.storage, "get_run_side_effects_dir"):
                side_effect_dir = os.path.join(
                    self.ctx.storage.get_run_side_effects_dir(run_id), plugin.provides
                )
            else:
                side_effect_dir = os.path.join(
                    self.ctx.storage_dir, "_side_effects", run_id, plugin.provides
                )
            os.makedirs(side_effect_dir, exist_ok=True)
            kwargs = kwargs.copy()
            kwargs["output_dir"] = side_effect_dir
        return kwargs

    def calculate_output_size(self, result: Any) -> float | None:
        if not (self.ctx.stats_collector and self.ctx.stats_collector.mode == "detailed"):
            return None
        try:
            if isinstance(result, np.ndarray):
                return result.nbytes / (1024 * 1024)
            if isinstance(result, list) and all(isinstance(x, np.ndarray) for x in result):
                return sum(arr.nbytes for arr in result) / (1024 * 1024)
            if isinstance(result, pd.DataFrame):
                return result.memory_usage(deep=True).sum() / (1024 * 1024)
            return None
        except (AttributeError, TypeError) as e:
            self.ctx.logger.debug("Could not calculate output size: %s", e)
            return None
        except Exception as e:
            self.ctx.logger.warning("Unexpected error calculating output size: %s", e)
            return None

    def execute_plugin_compute(
        self, plugin: Plugin, name: str, run_id: str, input_size_mb: float | None, kwargs: dict
    ) -> Any:
        if self.ctx.stats_collector and self.ctx.stats_collector.is_enabled():
            self.ctx.stats_collector.start_execution(name, run_id, input_size_mb=input_size_mb)

        try:
            with self.ctx.profiler.timeit(f"plugin.{name}.compute"):
                result = plugin.compute(self.ctx, run_id, **kwargs)
            return result
        except Exception as e:
            if self.ctx.stats_collector and self.ctx.stats_collector.is_enabled():
                self.ctx.stats_collector.end_execution(
                    name, success=False, cache_hit=False, error=e
                )
            plugin.on_error(self.ctx, e)
            severity = getattr(e, "severity", ErrorSeverity.FATAL)
            recoverable = getattr(e, "recoverable", False)
            error_context = self.ctx._error_manager.collect_context(
                plugin,
                run_id,
                context=self.ctx,
                get_config_fn=self.ctx.get_config,
                get_data_fn=self.ctx._get_data_from_memory,
            )
            if severity == ErrorSeverity.FATAL:
                self.ctx._error_manager.log_error(
                    name, e, run_id, plugin, error_context, get_config_fn=self.ctx.get_config
                )
                raise RuntimeError(f"Plugin '{name}' failed: {str(e)}") from e
            if severity == ErrorSeverity.RECOVERABLE and recoverable:
                self.ctx.logger.warning("Plugin '%s' failed but recoverable: %s", name, e)
                raise RuntimeError(f"Plugin '{name}' failed: {str(e)}") from e
            self.ctx._error_manager.log_error(
                name, e, run_id, plugin, error_context, get_config_fn=self.ctx.get_config
            )
            raise RuntimeError(f"Plugin '{name}' failed: {str(e)}") from e
        finally:
            try:
                plugin.cleanup(self.ctx)
            except Exception as cleanup_error:
                self.ctx.logger.warning(
                    "Plugin '%s' cleanup failed: %s", name, cleanup_error, exc_info=True
                )

    def save_plugin_result(
        self,
        plugin: Plugin,
        name: str,
        run_id: str,
        result: Any,
        key: str,
        lineage: dict[str, Any],
        is_generator: bool,
        target_dtype: np.dtype | None,
    ) -> Any:
        storage = self.ctx._get_storage_for_data_name(name)
        self.ctx._invalidate_storage_key_list_cache(storage, run_id)
        if isinstance(result, pd.DataFrame):
            if hasattr(storage, "save_dataframe"):
                self.ctx._storage_call(storage, "save_dataframe", key, run_id, result)
                self.ctx._storage_call(
                    storage,
                    "save_metadata",
                    key,
                    run_id,
                    {"lineage": lineage, "type": "dataframe"},
                )
            else:
                raise RuntimeError(
                    f"Storage backend {storage.__class__.__name__} does not support DataFrame."
                )
            self.ctx._set_data(run_id, name, result)
        elif isinstance(result, list) and all(isinstance(x, np.ndarray) for x in result):
            if self.ctx._expects_flat_channel_array(name):
                raise ValueError(
                    f"Plugin '{name}' returned a list of arrays, but this data now "
                    "uses a single structured array with a 'channel' field."
                )
            channel_count = len(result)
            for i, arr in enumerate(result):
                ch_key = f"{key}_ch{i}"
                self.ctx._storage_call(
                    storage,
                    "save_memmap",
                    ch_key,
                    run_id,
                    arr,
                    extra_metadata={"lineage": lineage, "channel_count": channel_count},
                )
            self.ctx._set_data(run_id, name, result)
        elif target_dtype is not None:
            if is_generator:
                result = self.wrap_generator_to_save(
                    run_id, name, cast(Iterator, result), target_dtype, lineage=lineage
                )
                result = OneTimeGenerator(result, name=f"Data '{name}' for run '{run_id}'")
                self.ctx._set_data(run_id, name, result)
            else:
                if isinstance(result, np.ndarray) and result.size == 0:
                    self.ctx._set_data(run_id, name, result)
                    return result
                self.ctx._storage_call(
                    storage,
                    "save_memmap",
                    key,
                    run_id,
                    result,
                    extra_metadata={"lineage": lineage},
                )
                data = self.ctx._storage_call(storage, "load_memmap", key, run_id)
                self.ctx._set_data(run_id, name, data)
                result = data
        else:
            self.ctx._set_data(run_id, name, result)
        return result

    def postprocess_plugin_result(
        self,
        plugin: Plugin,
        name: str,
        run_id: str,
        result: Any,
        key: str,
        data_name: str,
        tracker: Any | None,
        bar_name: str | None,
    ) -> None:
        lineage = self.ctx.get_lineage(name)
        result, effective_output_kind = self.ctx._validation_manager.validate_output_contract(
            plugin, result
        )
        is_generator = effective_output_kind == "stream"
        target_dtype = plugin.output_dtype
        if not is_generator:
            result = self.ctx._validation_manager.convert_to_dtype(
                result, target_dtype, name, is_generator=False
            )
        if plugin.save_when == "always" or (plugin.save_when == "target" and name == data_name):
            with self.ctx.profiler.timeit("context.save_cache"):
                result = self.save_plugin_result(
                    plugin, name, run_id, result, key, lineage, is_generator, target_dtype
                )
        else:
            self.ctx._set_data(run_id, name, result)

        output_size_mb = self.calculate_output_size(result)
        if self.ctx.stats_collector and self.ctx.stats_collector.is_enabled():
            self.ctx.stats_collector.end_execution(
                name, success=True, cache_hit=False, output_size_mb=output_size_mb
            )
        if tracker and bar_name:
            tracker.update(bar_name, n=1)

    def execute_single_plugin(
        self,
        name: str,
        run_id: str,
        data_name: str,
        kwargs: dict,
        tracker: Any | None,
        bar_name: str | None,
        skip_cache_check: bool = False,
    ) -> None:
        key = self.ctx.key_for(run_id, name)
        if not skip_cache_check:
            _data, cache_hit = self.ctx._cache_manager.check_cache(run_id, name, key)
            if cache_hit:
                if tracker and bar_name:
                    tracker.update(bar_name, n=1)
                return
        if name not in self.ctx._plugins:
            raise RuntimeError(f"Dependency '{name}' is missing and no plugin provides it.")
        plugin = self.ctx._plugins[name]
        show_progress = self.ctx.config.get("show_progress", True)
        if show_progress:
            print(f"[+] Running plugin: {name} (run_id: {run_id})")
        started_at = time.perf_counter()
        self.ctx._validation_manager.validate_plugin_config(plugin)
        self.ctx._validation_manager.validate_input_dtypes(plugin, run_id)
        input_size_mb = self.calculate_input_size(plugin, run_id)
        kwargs = self.prepare_side_effect_isolation(plugin, run_id, kwargs)
        result = self.execute_plugin_compute(plugin, name, run_id, input_size_mb, kwargs)
        self.postprocess_plugin_result(
            plugin, name, run_id, result, key, data_name, tracker, bar_name
        )
        if show_progress:
            elapsed = time.perf_counter() - started_at
            print(f"[done] Finished plugin: {name} (run_id: {run_id}, elapsed: {elapsed:.3f}s)")

    def run_plugin(
        self,
        run_id: str,
        data_name: str,
        show_progress: bool = False,
        progress_desc: str | None = None,
        plan: list[str] | None = None,
        needed_set: set[str] | None = None,
        **kwargs,
    ) -> Any:
        with self.ctx.profiler.timeit("context.run_plugin"):
            self.check_reentrancy(run_id, data_name)
            tracker = None
            bar_name = None
            try:
                if plan is None:
                    plan = self.resolve_execution_plan(run_id, data_name)
                if not plan:
                    return self.ctx._get_data_from_memory(run_id, data_name)
                if needed_set is None:
                    needed_set = set(plan)
                tracker, bar_name = self.init_progress_tracking(
                    show_progress, plan, run_id, data_name, progress_desc
                )

                # 检查是否启用插件级并行
                enable_parallelism = self.ctx.config.get("enable_plugin_parallelism", False)
                if enable_parallelism and len(needed_set) > 1:
                    # 并行执行路径
                    self._run_plugin_parallel(
                        run_id, data_name, plan, needed_set, kwargs, tracker, bar_name
                    )
                else:
                    # 串行执行路径（原有逻辑）
                    for name in plan:
                        if name not in needed_set:
                            key = self.ctx.key_for(run_id, name)
                            self.ctx._cache_manager.check_cache(run_id, name, key)
                            if tracker and bar_name:
                                tracker.update(bar_name, n=1)
                            continue
                        # Go back through Context so subclasses overriding the hook still see executions.
                        self.ctx._execute_single_plugin(
                            name,
                            run_id,
                            data_name,
                            kwargs,
                            tracker,
                            bar_name,
                            skip_cache_check=True,
                        )
                        # 重算会改变下游结果身份：级联失效下游谱系/键缓存，并用新鲜谱系
                        # 复查下游；复查失败的下游加入 needed_set，随计划执行重算，
                        # 而不是命中陈旧的 _lineage_cache 结果。
                        self._invalidate_downstream_caches(name, run_id, needed_set)

                return self.ctx._get_data_from_memory(run_id, data_name)
            finally:
                if tracker and bar_name:
                    tracker.close(bar_name)
                with self.ctx._in_progress_lock:
                    self.ctx._in_progress.pop((run_id, data_name), None)

    def _invalidate_downstream_caches(
        self, data_name: str, run_id: str, needed_set: set[str]
    ) -> None:
        """Cascade-invalidate lineage/key caches for a node's transitive downstream.

        重算一个节点会改变其下游结果身份（下游 lineage 内嵌该节点）。对每个下游：
        1. 清除 _lineage_cache / _lineage_hash_cache / _key_cache（保留执行计划缓存），
           使后续校验用新鲜谱系重新派生；
        2. 用新鲜谱系复查下游磁盘/内存缓存，失败的加入 needed_set 以便随后重算。
        """
        for downstream in self.ctx._collect_downstream_data_names(data_name, run_id=run_id):
            self.ctx._cache_domain._clear_lineage_key_caches(downstream)
            if not self.ctx._is_cache_hit(run_id, downstream, load=False):
                needed_set.add(downstream)

    def _run_plugin_parallel(
        self,
        run_id: str,
        data_name: str,
        plan: list[str],
        needed_set: set[str],
        kwargs: dict,
        tracker: Any | None,
        bar_name: str | None,
    ) -> None:
        """并行执行插件（基于依赖图分层）

        Args:
            run_id: 运行 ID
            data_name: 目标数据名
            plan: 执行计划
            needed_set: 需要执行的插件集合
            kwargs: 传递给插件的参数
            tracker: 进度追踪器
            bar_name: 进度条名称
        """
        # 构建依赖图并分层
        graph = self.build_dependency_graph(plan, run_id)
        layers = self.get_execution_layers(graph)

        max_workers = self.ctx.config.get("max_parallel_workers", 2)

        # 复用同一个线程池跨所有层，避免每层重建线程带来的开销。
        executor = ThreadPoolExecutor(max_workers=max_workers)
        failed = False
        try:
            for layer in layers:
                # 过滤出需要执行的插件
                layer_needed = [name for name in layer if name in needed_set]

                if not layer_needed:
                    # 当前层全部是缓存命中，跳过
                    for name in layer:
                        if name in plan and name not in needed_set:
                            key = self.ctx.key_for(run_id, name)
                            self.ctx._cache_manager.check_cache(run_id, name, key)
                            if tracker and bar_name:
                                tracker.update(bar_name, n=1)
                    continue

                if len(layer_needed) == 1:
                    # 当前层只有一个插件，串行执行
                    for name in layer_needed:
                        self.ctx._execute_single_plugin(
                            name,
                            run_id,
                            data_name,
                            kwargs,
                            tracker,
                            bar_name,
                            skip_cache_check=True,
                        )
                else:
                    # 当前层有多个插件，并行执行
                    futures = {}
                    for name in layer_needed:
                        future = executor.submit(
                            self._execute_plugin_safe,
                            name,
                            run_id,
                            data_name,
                            kwargs,
                            tracker,
                            bar_name,
                        )
                        futures[future] = name

                    # 等待所有任务完成
                    for future in as_completed(futures):
                        name = futures[future]
                        try:
                            future.result()
                        except Exception as e:
                            # 取消剩余任务
                            for f in futures:
                                if not f.done():
                                    f.cancel()
                            failed = True
                            raise RuntimeError(
                                f"Parallel execution failed for plugin '{name}': {e}"
                            ) from e

                # 层内节点互不依赖；下游必在更后层。层执行完后在单线程里级联失效下游，
                # 避免并发修改共享缓存字典。
                for name in layer_needed:
                    self._invalidate_downstream_caches(name, run_id, needed_set)
        finally:
            # 出错时取消未开始任务并不阻塞等待；正常路径等所有任务完成。
            executor.shutdown(wait=not failed, cancel_futures=failed)

    def _execute_plugin_safe(
        self,
        name: str,
        run_id: str,
        data_name: str,
        kwargs: dict,
        tracker: Any | None,
        bar_name: str | None,
    ) -> None:
        """线程安全的插件执行包装器

        Args:
            name: 插件名
            run_id: 运行 ID
            data_name: 目标数据名
            kwargs: 插件参数
            tracker: 进度追踪器
            bar_name: 进度条名称
        """
        try:
            self.ctx._execute_single_plugin(
                name, run_id, data_name, kwargs, tracker, bar_name, skip_cache_check=True
            )
        except Exception as e:
            self.ctx.logger.error(f"Plugin '{name}' execution failed: {e}", exc_info=True)
            raise

    def wrap_generator_to_save(
        self,
        run_id: str,
        data_name: str,
        generator: Iterator,
        dtype: np.dtype,
        lineage: dict[str, Any] | None = None,
    ) -> Iterator:
        key = self.ctx.key_for(run_id, data_name)
        bin_path, _meta_path, lock_path = self.ctx.storage._get_paths(key)
        tmp_bin_path = bin_path + ".tmp"

        def wrapper() -> Iterator:
            lock_fd = self.ctx.storage._acquire_lock(lock_path)
            if lock_fd is None:
                self.ctx.logger.warning("Could not acquire lock for %s, skipping cache write.", key)
                yield from generator
                return

            total_count = 0
            pbar = None
            if self.ctx.config.get("show_progress", True):
                try:
                    from tqdm import tqdm

                    pbar = tqdm(desc=f"Saving {data_name}", unit=" chunks", leave=False)
                except ImportError:
                    pass

            try:
                buffer = bytearray()
                buffered_bytes = 0
                flush_threshold = max(1, self.ctx.config.get("cache_buffer_bytes", 1 << 20))
                with open(tmp_bin_path, "wb") as f:
                    for chunk in generator:
                        if len(chunk) > 0:
                            try:
                                arr = np.asarray(chunk, dtype=dtype)
                            except (ValueError, TypeError) as e:
                                raise TypeError(
                                    f"Generator for '{data_name}' produced an invalid chunk: "
                                    f"Cannot convert to expected dtype {dtype}. Error: {str(e)}"
                                ) from e

                            chunk_bytes = arr.tobytes()
                            buffer.extend(chunk_bytes)
                            buffered_bytes += len(chunk_bytes)
                            total_count += len(arr)

                            if buffered_bytes >= flush_threshold:
                                f.write(buffer)
                                buffer.clear()
                                buffered_bytes = 0
                        if pbar is not None:
                            pbar.update(1)
                        yield chunk
                    if buffered_bytes > 0:
                        f.write(buffer)

                if pbar is not None:
                    pbar.close()

                self.ctx.storage.finalize_save(
                    key, total_count, dtype, extra_metadata={"lineage": lineage}
                )
                self.ctx._invalidate_storage_key_list_cache(self.ctx.storage, run_id)
                self.ctx._invalidate_storage_key_list_cache(
                    self.ctx._get_storage_for_data_name(data_name), run_id
                )

                if total_count > 0:
                    self.ctx.logger.info(
                        "Saved %s items to cache for %s (%s)", total_count, data_name, run_id
                    )

                yield from []
            except Exception as e:
                self.ctx.logger.error("Error saving %s to cache: %s", data_name, str(e))
                if os.path.exists(tmp_bin_path):
                    try:
                        os.remove(tmp_bin_path)
                    except (PermissionError, OSError) as cleanup_err:
                        self.ctx.logger.warning(
                            "Failed to remove temporary file %s after error: %s",
                            tmp_bin_path,
                            cleanup_err,
                        )
                    except Exception as cleanup_err:
                        self.ctx.logger.error(
                            "Unexpected error removing temp file %s: %s",
                            tmp_bin_path,
                            cleanup_err,
                            exc_info=True,
                        )
                raise
            finally:
                self.ctx.storage._release_lock(lock_fd, lock_path)
                if os.path.exists(tmp_bin_path):
                    try:
                        os.remove(tmp_bin_path)
                    except (PermissionError, OSError) as cleanup_err:
                        self.ctx.logger.debug(
                            "Failed to remove lingering temp file %s: %s",
                            tmp_bin_path,
                            cleanup_err,
                        )
                    except Exception as cleanup_err:
                        self.ctx.logger.warning(
                            "Unexpected error removing temp file %s: %s",
                            tmp_bin_path,
                            cleanup_err,
                        )

        return wrapper()
