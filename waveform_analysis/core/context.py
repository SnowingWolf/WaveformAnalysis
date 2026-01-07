"""
Context 模块 - 插件系统的核心调度器。

负责管理插件注册、依赖解析、配置分发以及数据缓存的生命周期。
它是整个分析框架的“大脑”，通过 DAG（有向无环图）确保数据按需、有序地计算。
支持多级缓存校验和血缘追踪，是实现高效、可重复分析的基础。
"""

import hashlib
import json
import logging
import os
import re
import threading
import warnings
from typing import Any, Dict, Iterator, List, Optional, Type, Union, cast

import numpy as np
import pandas as pd

from waveform_analysis.utils.visualization.lineage_visualizer import plot_lineage_labview

from .cache import WATCH_SIG_KEY, CacheManager
from .mixins import CacheMixin, PluginMixin
from .plugins import Plugin
from .storage import MemmapStorage
from .utils import OneTimeGenerator, Profiler


class Context(CacheMixin, PluginMixin):
    """
    The Context orchestrates plugins and manages data storage/caching.
    Inspired by strax, it is the main entry point for data analysis.
    """

    def __init__(
        self,
        storage_dir: str = "./strax_data",
        config: Optional[Dict[str, Any]] = None,
        storage: Optional[Any] = None,
        plugin_dirs: Optional[List[str]] = None,
        auto_discover_plugins: bool = False,
    ):
        """
        Initialize Context.

        Args:
            storage_dir: 默认存储目录（使用 MemmapStorage 时）
            config: 全局配置字典
            storage: 自定义存储后端（必须实现 StorageBackend 接口）
                    如果为 None，使用默认的 MemmapStorage
            plugin_dirs: 插件搜索目录列表
            auto_discover_plugins: 是否自动发现并注册插件

        Examples:
            >>> # 使用默认 memmap 存储
            >>> ctx = Context(storage_dir="./data")

            >>> # 使用 SQLite 存储
            >>> from waveform_analysis.core.storage_backends import SQLiteBackend
            >>> ctx = Context(storage=SQLiteBackend("./data.db"))

            >>> # 使用工厂函数
            >>> from waveform_analysis.core.storage_backends import create_storage_backend
            >>> storage = create_storage_backend("sqlite", db_path="./data.db")
            >>> ctx = Context(storage=storage)
        """
        CacheMixin.__init__(self)
        PluginMixin.__init__(self)

        self.profiler = Profiler()
        self.storage_dir = storage_dir
        self.config = config or {}

        # Extensibility: Allow custom storage backend
        if storage is not None:
            # 验证存储后端接口（可选，记录警告）
            self._validate_storage_backend(storage)
            self.storage = storage
        else:
            # 默认使用 MemmapStorage
            self.storage = MemmapStorage(self.storage_dir, profiler=self.profiler)

        # Setup logger
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        # Dedicated storage for results to avoid namespace pollution
        self._results: Dict[tuple, Any] = {}
        # Re-entrancy guard: track (run_id, data_name) currently being computed
        self._in_progress: Dict[tuple, Any] = {}
        self._in_progress_lock = threading.Lock()  # Protect concurrent access
        # Cache of validated configs per plugin signature
        self._resolved_config_cache: Dict[tuple, Dict[str, Any]] = {}

        # Performance optimization caches
        self._execution_plan_cache: Dict[str, List[str]] = {}  # data_name -> execution plan
        self._lineage_cache: Dict[str, Dict[str, Any]] = {}    # data_name -> lineage dict
        self._lineage_hash_cache: Dict[str, str] = {}          # data_name -> lineage hash
        self._key_cache: Dict[tuple, str] = {}                 # (run_id, data_name) -> key

        # Plugin discovery
        self.plugin_dirs = plugin_dirs or []
        if auto_discover_plugins:
            self.discover_and_register_plugins()

        # Ensure storage directory exists if using default
        if not storage and not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)

    def register(self, *plugins: Union[Plugin, Type[Plugin], Any], allow_override: bool = False):
        """
        Register one or more plugins.
        Accepts plugin instances, classes (will be instantiated), or modules.
        """
        for p in plugins:
            if isinstance(p, type) and issubclass(p, Plugin):
                self.register_plugin(p(), allow_override=allow_override)
            elif isinstance(p, Plugin):
                self.register_plugin(p, allow_override=allow_override)
            elif hasattr(p, "__path__") or hasattr(p, "__file__"):  # It's a module
                self._register_from_module(p, allow_override=allow_override)
            else:
                # Fallback for other types if needed
                self.register_plugin(p, allow_override=allow_override)

    def _register_from_module(self, module, allow_override: bool = False):
        """Helper to register all Plugin classes found in a module."""
        import inspect

        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, Plugin) and obj != Plugin:
                self.register_plugin(obj(), allow_override=allow_override)

    def discover_and_register_plugins(self, allow_override: bool = False) -> int:
        """
        自动发现并注册插件

        发现顺序：
        1. Entry points (waveform_analysis.plugins)
        2. 配置的插件目录

        Args:
            allow_override: 是否允许覆盖已注册的插件

        Returns:
            注册的插件数量
        """
        from waveform_analysis.core.plugin_loader import PluginLoader

        loader = PluginLoader(self.plugin_dirs)
        total_discovered = loader.discover_all()

        # 注册发现的插件
        registered = 0
        for plugin_class in loader.get_plugins():
            try:
                self.register_plugin(plugin_class(), allow_override=allow_override)
                registered += 1
            except Exception as e:
                self.logger.warning(f"Failed to register plugin {plugin_class.__name__}: {e}")

        # 报告失败的插件
        failed = loader.get_failed_plugins()
        if failed:
            self.logger.warning(f"Failed to load {len(failed)} plugins")
            for name, error in list(failed.items())[:5]:  # 只显示前5个
                self.logger.debug(f"  - {name}: {error}")

        self.logger.info(f"Plugin discovery: {registered}/{total_discovered} plugins registered")
        return registered

    def set_config(self, config: Dict[str, Any]):
        """Update the context configuration."""
        self.config.update(config)

    def _validate_storage_backend(self, storage: Any) -> None:
        """
        验证存储后端是否实现了必需的接口

        如果后端缺少必需方法，记录警告但不阻止使用。
        """
        required_methods = [
            'exists', 'save_memmap', 'load_memmap',
            'save_metadata', 'get_metadata', 'delete',
            'list_keys', 'get_size', 'save_stream', 'finalize_save'
        ]

        missing_methods = []
        for method in required_methods:
            if not hasattr(storage, method) or not callable(getattr(storage, method)):
                missing_methods.append(method)

        if missing_methods:
            self.logger.warning(
                f"Storage backend {storage.__class__.__name__} is missing methods: {missing_methods}. "
                "This may cause errors during operation."
            )

    def _resolve_config_value(self, plugin: Plugin, name: str) -> Any:
        """Compute configuration value for an option without validation."""
        if name not in plugin.options:
            raise KeyError(f"Plugin '{plugin.provides}' does not have option '{name}'")

        option = plugin.options[name]
        provides = plugin.provides

        if provides in self.config and isinstance(self.config[provides], dict):
            if name in self.config[provides]:
                return self.config[provides][name]
            return self.config.get(f"{provides}.{name}", self.config.get(name, option.default))
        if f"{provides}.{name}" in self.config:
            return self.config[f"{provides}.{name}"]
        return self.config.get(name, option.default)

    def get_config(self, plugin: Plugin, name: str) -> Any:
        """
        Get a configuration value for a plugin, applying defaults and validation.
        Supports namespacing: config[plugin_provides][name] or config["plugin_provides.name"]
        """
        raw_value = self._resolve_config_value(plugin, name)
        option = plugin.options[name]
        return option.validate_value(name, raw_value, plugin_name=plugin.provides)

    def _make_config_signature(self, raw_config: Dict[str, Any]) -> str:
        """Generate a stable signature for a plugin's raw config dict."""

        def default(o: Any) -> str:
            if isinstance(o, np.ndarray):
                return o.tobytes().hex()
            return repr(o)

        normalized = {name: raw_config[name] for name in sorted(raw_config)}
        payload = json.dumps(normalized, sort_keys=True, default=default)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _ensure_plugin_config_validated(self, plugin: Plugin) -> Dict[str, Any]:
        """Validate and cache plugin configuration for reuse."""
        raw_config = {name: self._resolve_config_value(plugin, name) for name in plugin.options}
        signature = self._make_config_signature(raw_config)
        cache_key = (plugin.provides, signature)
        if cache_key in self._resolved_config_cache:
            return self._resolved_config_cache[cache_key]

        validated = {}
        for name, option in plugin.options.items():
            validated[name] = option.validate_value(name, raw_config[name], plugin_name=plugin.provides)
        self._resolved_config_cache[cache_key] = validated
        return validated

    def clear_config_cache(self):
        """Clear cached validated configurations."""
        self._resolved_config_cache.clear()

    def clear_performance_caches(self):
        """
        Clear all performance optimization caches.

        Should be called when plugins are registered/unregistered or
        when plugin configurations change.
        """
        self._execution_plan_cache.clear()
        self._lineage_cache.clear()
        self._lineage_hash_cache.clear()
        self._key_cache.clear()
        self.logger.debug("Performance caches cleared")

    def _invalidate_caches_for(self, data_name: str):
        """
        Invalidate caches that depend on a specific data type.

        Called when a plugin providing data_name is registered or changed.
        """
        # Clear execution plan cache for data_name and anything that depends on it
        if data_name in self._execution_plan_cache:
            del self._execution_plan_cache[data_name]

        # Find and clear plans that include this data_name
        to_remove = []
        for cached_name, plan in self._execution_plan_cache.items():
            if data_name in plan:
                to_remove.append(cached_name)

        for name in to_remove:
            del self._execution_plan_cache[name]

        # Clear lineage caches
        if data_name in self._lineage_cache:
            del self._lineage_cache[data_name]
        if data_name in self._lineage_hash_cache:
            del self._lineage_hash_cache[data_name]

        # Clear key cache entries for this data_name
        keys_to_remove = [k for k in self._key_cache if k[1] == data_name]
        for k in keys_to_remove:
            del self._key_cache[k]

        self.logger.debug(f"Caches invalidated for '{data_name}'")

    def _set_data(self, run_id: str, name: str, value: Any):
        """Internal helper to set data in _results and optionally as attribute."""
        self._results[(run_id, name)] = value

        is_generator = isinstance(value, (Iterator, OneTimeGenerator)) or hasattr(value, "__next__")

        # Safe attribute access: whitelist and conflict check
        # Whitelist: valid python identifier
        if re.match(r"^[a-zA-Z_]\w*$", name):
            # Reserved names check
            reserved = {
                "config",
                "storage",
                "storage_dir",
                "register",
                "get_data",
                "get_config",
                "run_plugin",
                "list_provided_data",
                "get_lineage",
                "show_config",
                "plot_lineage",
                "key_for",
                "logger",
            }
            # Check if it's a property on the class (e.g. in WaveformDataset)
            cls_attr = getattr(self.__class__, name, None)
            is_prop = isinstance(cls_attr, property)

            if name in reserved or (hasattr(self.__class__, name) and not is_prop):
                warnings.warn(
                    f"Data name '{name}' conflicts with a Context method or reserved attribute. "
                    f"Access it via context.get_data(run_id, '{name}') or context._results[(run_id, '{name}')].",
                    UserWarning,
                )
            elif not is_prop and not is_generator:
                # Note: This overwrites the attribute for different runs.
                # It's kept for convenience in interactive use.
                # We don't set it if it's a property, as the property handles access.
                setattr(self, name, value)

    def _get_data_from_memory(self, run_id: str, name: str) -> Any:
        """Internal helper to get data from _results or attributes."""
        if (run_id, name) in self._results:
            val = self._results[(run_id, name)]
            return val

        # Fallback for manually set attributes (if any)
        # But ONLY if it's not a reserved name/method to avoid returning the method itself
        # AND ONLY if it's not a plugin-provided data name, because plugin data MUST be run-id specific.
        reserved = {
            "config",
            "storage",
            "storage_dir",
            "register",
            "get_data",
            "get_config",
            "run_plugin",
            "list_provided_data",
            "get_lineage",
            "show_config",
            "plot_lineage",
            "key_for",
            "logger",
        }
        if (
            name not in reserved
            and name not in self._plugins
            and not hasattr(self.__class__, name)
            and hasattr(self, name)
        ):
            # This might return data from a different run if it was the last one set.
            # But it's a fallback for manually set attributes.
            return getattr(self, name)
        return None

    def _load_from_disk_with_check(self, run_id: str, name: str, key: str) -> Optional[Any]:
        """Internal helper to load data from disk with lineage verification."""
        if not self.storage.exists(key):
            # Check if it's a multi-channel data (e.g. peaks_ch0)
            if not self.storage.exists(f"{key}_ch0"):
                return None

        meta = self.storage.get_metadata(key) or self.storage.get_metadata(f"{key}_ch0")
        if meta and "lineage" in meta:
            current_lineage = self.get_lineage(name)
            import json

            s1 = json.dumps(meta["lineage"], sort_keys=True, default=str)
            s2 = json.dumps(current_lineage, sort_keys=True, default=str)
            if s1 != s2:
                warnings.warn(f"Lineage mismatch for '{name}' in cache. Recomputing.", UserWarning)
                return None

        # Determine how to load
        if meta.get("type") == "dataframe":
            data = self.storage.load_dataframe(key)
        elif self.storage.exists(f"{key}_ch0"):
            # Load multi-channel data
            data = []
            i = 0
            while self.storage.exists(f"{key}_ch{i}"):
                data.append(self.storage.load_memmap(f"{key}_ch{i}"))
                i += 1
        else:
            data = self.storage.load_memmap(key)

        if data is not None:
            if self.config.get("show_progress", True):
                print(f"[cache] Loaded '{name}' from disk (run_id: {run_id})")
            self._set_data(run_id, name, data)
        return data

    def get_data(self, run_id: str, data_name: str, **kwargs) -> Any:
        """
        Retrieve data by name for a specific run.
        If data is not in memory/cache, it will trigger the necessary plugins.
        """
        # 1. Check memory cache
        val = self._get_data_from_memory(run_id, data_name)
        if val is not None:
            return val

        # 2. Check disk cache (memmap)
        # Only check if it's a plugin-provided data
        if data_name in self._plugins:
            key = self.key_for(run_id, data_name)
            data = self._load_from_disk_with_check(run_id, data_name, key)
            if data is not None:
                return data

        # 3. Run plugin (this will also handle dependencies)
        return self.run_plugin(run_id, data_name, **kwargs)

    def run_plugin(self, run_id: str, data_name: str, **kwargs) -> Any:
        """
        Override run_plugin to add saving logic and config resolution.
        """
        with self.profiler.timeit("context.run_plugin"):
            # Re-entrancy guard (thread-safe)
            with self._in_progress_lock:
                if (run_id, data_name) in self._in_progress:
                    raise RuntimeError(
                        f"Re-entrant call for ({run_id}, {data_name}) detected. "
                        "This usually indicates a circular dependency at runtime."
                    )
                self._in_progress[(run_id, data_name)] = True

            try:
                # 1. Resolve execution plan (with caching)
                try:
                    with self.profiler.timeit("context.resolve_dependencies"):
                        # Check cache first
                        if data_name in self._execution_plan_cache:
                            plan = self._execution_plan_cache[data_name]
                        else:
                            plan = self.resolve_dependencies(data_name)
                            self._execution_plan_cache[data_name] = plan
                except ValueError:
                    val = self._get_data_from_memory(run_id, data_name)
                    if val is not None:
                        return val
                    raise

                # 2. Execute plan in order
                for name in plan:
                    # Check memory cache again (might have been loaded as dependency)
                    if self._get_data_from_memory(run_id, name) is not None:
                        continue

                    # Check disk cache for dependencies too
                    key = self.key_for(run_id, name)
                    with self.profiler.timeit("context.load_cache"):
                        data = self._load_from_disk_with_check(run_id, name, key)
                    if data is not None:
                        continue

                    if name not in self._plugins:
                        raise RuntimeError(f"Dependency '{name}' is missing and no plugin provides it.")

                    plugin = self._plugins[name]

                    # 打印当前运行的插件
                    if self.config.get("show_progress", True):
                        print(f"[+] Running plugin: {name} (run_id: {run_id})")

                    # 1. Validate all options (with caching) so we don't redo heavy validation each time
                    self._ensure_plugin_config_validated(plugin)

                    # 2. Validate input dtypes if specified
                    for dep_name, expected_dtype in plugin.input_dtype.items():
                        dep_data = self.get_data(run_id, dep_name)
                        # Helper to get dtype from various data structures
                        actual_dtype = None
                        if isinstance(dep_data, np.ndarray):
                            actual_dtype = dep_data.dtype
                        elif isinstance(dep_data, list) and len(dep_data) > 0 and isinstance(dep_data[0], np.ndarray):
                            actual_dtype = dep_data[0].dtype

                        if actual_dtype is not None and actual_dtype != expected_dtype:
                            raise TypeError(
                                f"Plugin '{name}' input compatibility check failed for dependency '{dep_name}': "
                                f"Expected dtype {expected_dtype}, but got {actual_dtype}."
                            )

                    # Side-effect isolation
                    if getattr(plugin, "is_side_effect", False):
                        side_effect_dir = os.path.join(self.storage_dir, "_side_effects", run_id, name)
                        os.makedirs(side_effect_dir, exist_ok=True)
                        kwargs["output_dir"] = side_effect_dir

                    try:
                        # Call plugin compute with explicit run_id
                        with self.profiler.timeit(f"plugin.{name}.compute"):
                            result = plugin.compute(self, run_id, **kwargs)
                    except Exception as e:
                        # Error handling hook
                        plugin.on_error(self, e)

                        # Detailed error logging
                        import traceback

                        print(f"\nError in plugin '{name}' ({plugin.__class__.__name__}):")
                        print(f"Run ID: {run_id}")
                        print(f"Config: { {k: self.get_config(plugin, k) for k in plugin.config_keys} }")
                        print(f"Traceback:\n{traceback.format_exc()}")

                        raise RuntimeError(f"Plugin '{name}' failed: {str(e)}") from e
                    finally:
                        # Cleanup hook
                        plugin.cleanup(self)

                    lineage = self.get_lineage(name)

                    # 3. Output Contract Validation
                    is_generator = isinstance(result, (Iterator, OneTimeGenerator)) or hasattr(result, "__next__")
                    effective_output_kind = plugin.output_kind
                    if is_generator and effective_output_kind == "static":
                        effective_output_kind = "stream"

                    if effective_output_kind == "stream" and not is_generator:
                        raise TypeError(
                            f"Plugin '{name}' output contract violation: "
                            f"output_kind is 'stream' but compute() returned {type(result).__name__} (not an iterator)."
                        )
                    if effective_output_kind == "static" and is_generator:
                        raise TypeError(
                            f"Plugin '{name}' output contract violation: "
                            f"output_kind is 'static' but compute() returned an iterator."
                        )

                    # Use output_dtype
                    target_dtype = plugin.output_dtype

                    skip_dtype_conversion = (
                        isinstance(result, list)
                        and len(result) > 0
                        and all(isinstance(item, np.ndarray) for item in result)
                    )
                    if target_dtype is not None and not is_generator and not skip_dtype_conversion:
                        try:
                            # Try to convert to expected dtype to validate contract
                            result = np.asarray(result, dtype=target_dtype)
                        except (ValueError, TypeError) as e:
                            raise TypeError(
                                f"Plugin '{name}' output contract violation: "
                                f"Expected dtype {target_dtype}, but got {type(result).__name__} "
                                f"which cannot be converted. Error: {str(e)}"
                            ) from e

                    # Handle saving
                    if plugin.save_when == "always" or (plugin.save_when == "target" and name == data_name):
                        with self.profiler.timeit("context.save_cache"):
                            if isinstance(result, pd.DataFrame):
                                # Save DataFrame as Parquet
                                self.storage.save_dataframe(key, result)
                                self.storage.save_metadata(key, {"lineage": lineage, "type": "dataframe"})
                                self._set_data(run_id, name, result)
                            elif isinstance(result, list) and all(isinstance(x, np.ndarray) for x in result):
                                # Save list of arrays (e.g. per-channel data)
                                for i, arr in enumerate(result):
                                    ch_key = f"{key}_ch{i}"
                                    self.storage.save_memmap(ch_key, arr, extra_metadata={"lineage": lineage})
                                self._set_data(run_id, name, result)
                            elif target_dtype is not None:
                                if is_generator:
                                    # It's a generator, wrap it to save while yielding
                                    result = self._wrap_generator_to_save(
                                        run_id, name, cast(Iterator, result), target_dtype, lineage=lineage
                                    )
                                    # Wrap with OneTimeGenerator to prevent multiple consumption issues
                                    result = OneTimeGenerator(result, name=f"Data '{name}' for run '{run_id}'")
                                    self._set_data(run_id, name, result)
                                else:
                                    # It's a static array, save it directly
                                    self.storage.save_stream(
                                        key, [result], target_dtype, extra_metadata={"lineage": lineage}
                                    )
                                    data = self.storage.load_memmap(key)
                                    self._set_data(run_id, name, data)
                            else:
                                # Fallback: just set in memory
                                self._set_data(run_id, name, result)
                    else:
                        self._set_data(run_id, name, result)

                return self._get_data_from_memory(run_id, data_name)
            finally:
                with self._in_progress_lock:
                    self._in_progress.pop((run_id, data_name), None)

    def _wrap_generator_to_save(
        self,
        run_id: str,
        data_name: str,
        generator: Iterator,
        dtype: np.dtype,
        lineage: Optional[Dict[str, Any]] = None,
    ) -> Iterator:
        """
        Wraps a generator to save its output to disk while yielding.
        Uses file locking and atomic writes for integrity.
        """
        key = self.key_for(run_id, data_name)
        bin_path, meta_path, lock_path = self.storage._get_paths(key)
        tmp_bin_path = bin_path + ".tmp"
        tmp_meta_path = meta_path + ".tmp"

        def wrapper():
            # Acquire lock before starting the stream
            lock_fd = self.storage._acquire_lock(lock_path)
            if lock_fd is None:
                self.logger.warning(f"Could not acquire lock for {key}, skipping cache write.")
                yield from generator
                return

            total_count = 0
            pbar = None
            if self.config.get("show_progress", True):
                try:
                    from tqdm import tqdm

                    pbar = tqdm(desc=f"Saving {data_name}", unit=" chunks", leave=False)
                except ImportError:
                    pass

            try:
                buffer = bytearray()
                buffered_bytes = 0
                flush_threshold = max(1, self.config.get("cache_buffer_bytes", 1 << 20))
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

                # Use unified storage finalization
                self.storage.finalize_save(key, total_count, dtype, extra_metadata={"lineage": lineage})

                if total_count > 0:
                    self.logger.info(f"Saved {total_count} items to cache for {data_name} ({run_id})")

                yield from []  # Just to ensure the generator finishes correctly if needed
            except Exception as e:
                self.logger.error(f"Error saving {data_name} to cache: {str(e)}")
                # Cleanup partial files
                if os.path.exists(tmp_bin_path):
                    try:
                        os.remove(tmp_bin_path)
                    except Exception:
                        pass
                raise e
            finally:
                self.storage._release_lock(lock_fd, lock_path)
                if os.path.exists(tmp_bin_path):
                    try:
                        os.remove(tmp_bin_path)
                    except:
                        pass

        return wrapper()

    def list_provided_data(self) -> List[str]:
        """List all data types provided by registered plugins."""
        return list(self._plugins.keys())

    @property
    def profiling_summary(self) -> str:
        """Return a summary of the profiling data."""
        return self.profiler.summary()

    def get_lineage(self, data_name: str, _visited: Optional[set] = None) -> Dict[str, Any]:
        """
        Get the lineage (recipe) for a data type.

        Uses caching for performance optimization.
        """
        # Check cache (only for non-recursive calls)
        if _visited is None and data_name in self._lineage_cache:
            return self._lineage_cache[data_name]

        if _visited is None:
            _visited = set()

        if data_name in _visited:
            return {"plugin_class": "CircularDependency", "target": data_name}

        if data_name not in self._plugins:
            # Check if it's a side-effect or manually set attribute
            if hasattr(self, data_name) and getattr(self, data_name) is not None:
                return {"plugin_class": "ManualData", "config": {}, "depends_on": {}}
            return {}

        plugin = self._plugins[data_name]

        # Extensibility: Allow plugin to customize its lineage info
        if hasattr(plugin, "get_lineage"):
            return plugin.get_lineage(self)

        _visited.add(data_name)

        # Filter config to only include tracked options
        config = {}
        for k in plugin.config_keys:
            opt = plugin.options.get(k)
            if opt and getattr(opt, "track", True):
                config[k] = self.get_config(plugin, k)

        lineage = {
            "plugin_class": plugin.__class__.__name__,
            "plugin_version": getattr(plugin, "version", "0.0.0"),
            "description": getattr(plugin, "description", ""),
            "config": config,
            "depends_on": {dep: self.get_lineage(dep, _visited=_visited.copy()) for dep in plugin.depends_on},
        }
        if plugin.output_dtype is not None:
            # Standardize dtype to avoid version differences in str(dtype)
            lineage["dtype"] = np.dtype(plugin.output_dtype).descr

        # Cache the lineage (only for top-level calls)
        if len(_visited) == 1:  # Top-level call
            self._lineage_cache[data_name] = lineage

        return lineage

    def show_config(self, data_name: Optional[str] = None):
        """Print the current configuration, optionally filtered for a data type."""
        if data_name and data_name in self._plugins:
            plugin = self._plugins[data_name]
            cfg = {k: self.get_config(plugin, k) for k in plugin.config_keys}
            desc = getattr(plugin, "description", "")
            print(f"Config for {data_name} ({plugin.__class__.__name__}):")
            if desc:
                print(f"Description: {desc}")
        else:
            cfg = self.config
            print("Global Context Config:")

        import json

        print(json.dumps(cfg, indent=2, default=str))

    def plot_lineage(self, data_name: str, kind: str = "labview", **kwargs):
        """
        Visualize the lineage of a data type.

        Args:
            data_name: Name of the target data.
            kind: Visualization style ('labview' or 'mermaid').
            **kwargs: Additional arguments passed to the visualizer.
        """
        from .model import build_lineage_graph

        lineage = self.get_lineage(data_name)
        if not lineage:
            print(f"No lineage found for '{data_name}'")
            return

        # 统一构建模型
        model = build_lineage_graph(lineage, data_name, plugins=getattr(self, "_plugins", {}))

        if kind == "labview":
            return plot_lineage_labview(model, data_name, context=self, **kwargs)
        elif kind == "mermaid":
            mermaid_str = model.to_mermaid()
            print(mermaid_str)
            return mermaid_str
        else:
            raise ValueError(f"Unsupported visualization kind: {kind}")

    def key_for(self, run_id: str, data_name: str) -> str:
        """
        Get a unique key (hash) for a data type and run.

        Uses caching for performance optimization.
        """
        # Check cache first
        cache_key = (run_id, data_name)
        if cache_key in self._key_cache:
            return self._key_cache[cache_key]

        import hashlib
        import json

        # Check if we have cached lineage hash
        if data_name in self._lineage_hash_cache:
            lineage_hash = self._lineage_hash_cache[data_name]
        else:
            lineage = self.get_lineage(data_name)
            # Use default=str to handle any non-serializable objects gracefully,
            # though we try to standardize them in get_lineage.
            lineage_json = json.dumps(lineage, sort_keys=True, default=str)
            lineage_hash = hashlib.sha1(lineage_json.encode()).hexdigest()[:8]
            self._lineage_hash_cache[data_name] = lineage_hash

        key = f"{run_id}-{data_name}-{lineage_hash}"
        self._key_cache[cache_key] = key
        return key

    def clear_cache_for(
        self, 
        run_id: str, 
        data_name: Optional[str] = None,
        clear_memory: bool = True,
        clear_disk: bool = True
    ) -> int:
        """
        清理指定运行和步骤的缓存。
        
        参数:
            run_id: 运行 ID
            data_name: 数据名称（步骤名称），如果为 None 则清理所有步骤
            clear_memory: 是否清理内存缓存
            clear_disk: 是否清理磁盘缓存
        
        返回:
            清理的缓存项数量
        
        示例:
            >>> ctx = Context()
            >>> # 清理单个步骤的缓存
            >>> ctx.clear_cache_for("run_001", "st_waveforms")
            >>> # 清理所有步骤的缓存
            >>> ctx.clear_cache_for("run_001")
            >>> # 只清理内存缓存
            >>> ctx.clear_cache_for("run_001", "df", clear_disk=False)
        """
        count = 0
        
        # 确定要清理的数据名称列表
        if data_name is None:
            # 清理所有已注册插件提供的数据
            data_names = list(self._plugins.keys())
        else:
            data_names = [data_name]
        
        for name in data_names:
            # 清理内存缓存
            if clear_memory:
                key = (run_id, name)
                if key in self._results:
                    del self._results[key]
                    count += 1
                    self.logger.debug(f"Cleared memory cache for ({run_id}, {name})")
            
            # 清理磁盘缓存
            if clear_disk:
                try:
                    cache_key = self.key_for(run_id, name)
                    deleted = self._delete_disk_cache(cache_key)
                    count += deleted
                    if deleted > 0:
                        self.logger.debug(f"Cleared disk cache for ({run_id}, {name})")
                except Exception as e:
                    self.logger.warning(f"Failed to clear disk cache for ({run_id}, {name}): {e}")
        
        return count
    
    def _delete_disk_cache(self, key: str) -> int:
        """
        删除磁盘缓存（包括多通道数据和 DataFrame）。
        
        参数:
            key: 缓存键
        
        返回:
            删除的缓存项数量
        """
        count = 0
        
        # 删除主缓存文件
        if self.storage.exists(key):
            try:
                self.storage.delete(key)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to delete cache key {key}: {e}")
        
        # 删除多通道数据（{key}_ch0, {key}_ch1, ...）
        ch_idx = 0
        while True:
            ch_key = f"{key}_ch{ch_idx}"
            if self.storage.exists(ch_key):
                try:
                    self.storage.delete(ch_key)
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to delete multi-channel cache {ch_key}: {e}")
                ch_idx += 1
            else:
                break
        
        # 删除 DataFrame 缓存（{key}.parquet）
        # 检查 storage 是否支持 DataFrame 存储（有 save_dataframe 方法）
        if hasattr(self.storage, 'save_dataframe'):
            # 对于 MemmapStorage，parquet 文件存储在 base_dir 中
            if hasattr(self.storage, 'base_dir'):
                parquet_path = os.path.join(self.storage.base_dir, f"{key}.parquet")
                if os.path.exists(parquet_path):
                    try:
                        os.remove(parquet_path)
                        count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to delete parquet file {parquet_path}: {e}")
            # 对于其他存储后端，如果 db_path 存在，可能在同目录下
            elif hasattr(self.storage, 'db_path'):
                base_dir = os.path.dirname(self.storage.db_path)
                parquet_path = os.path.join(base_dir, f"{key}.parquet")
                if os.path.exists(parquet_path):
                    try:
                        os.remove(parquet_path)
                        count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to delete parquet file {parquet_path}: {e}")
        
        return count

    def __repr__(self):
        return f"Context(storage='{self.storage_dir}', plugins={self.list_provided_data()})"
