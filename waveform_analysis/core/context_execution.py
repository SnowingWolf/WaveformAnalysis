from __future__ import annotations

from collections.abc import Iterator
import os
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
                if data_name in self.ctx._execution_plan_cache:
                    plan = self.ctx._execution_plan_cache[data_name]
                else:
                    plan = self.ctx.resolve_dependencies(data_name, run_id=run_id)
                    self.ctx._execution_plan_cache[data_name] = plan
            return plan
        except ValueError:
            val = self.ctx._get_data_from_memory(run_id, data_name)
            if val is not None:
                return []
            raise

    def compute_needed_set(self, run_id: str, data_name: str, plan: list[str]) -> set[str]:
        needed: set[str] = set()
        visited: set[str] = set()

        def dfs(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            if self.ctx._is_cache_hit(run_id, name, load=False):
                return
            if name not in self.ctx._plugins:
                return
            plugin = self.ctx._plugins[name]
            for dep_name in self.ctx._get_plugin_dependency_names(plugin, run_id=run_id):
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
            for dep_name in self.ctx._get_plugin_dependency_names(plugin, run_id=run_id):
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
        if self.ctx.config.get("show_progress", True):
            print(f"[+] Running plugin: {name} (run_id: {run_id})")
        self.ctx._validation_manager.validate_plugin_config(plugin)
        self.ctx._validation_manager.validate_input_dtypes(plugin, run_id)
        input_size_mb = self.calculate_input_size(plugin, run_id)
        kwargs = self.prepare_side_effect_isolation(plugin, run_id, kwargs)
        result = self.execute_plugin_compute(plugin, name, run_id, input_size_mb, kwargs)
        self.postprocess_plugin_result(
            plugin, name, run_id, result, key, data_name, tracker, bar_name
        )

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
                for name in plan:
                    if name not in needed_set:
                        key = self.ctx.key_for(run_id, name)
                        self.ctx._cache_manager.check_cache(run_id, name, key)
                        if tracker and bar_name:
                            tracker.update(bar_name, n=1)
                        continue
                    # Go back through Context so subclasses overriding the hook still see executions.
                    self.ctx._execute_single_plugin(
                        name, run_id, data_name, kwargs, tracker, bar_name, skip_cache_check=True
                    )
                return self.ctx._get_data_from_memory(run_id, data_name)
            finally:
                if tracker and bar_name:
                    tracker.close(bar_name)
                with self.ctx._in_progress_lock:
                    self.ctx._in_progress.pop((run_id, data_name), None)

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
