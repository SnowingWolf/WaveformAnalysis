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
    ):
        CacheMixin.__init__(self)
        PluginMixin.__init__(self)

        self.profiler = Profiler()
        self.storage_dir = storage_dir
        self.config = config or {}
        # Extensibility: Allow custom storage backend
        self.storage = storage or MemmapStorage(self.storage_dir, profiler=self.profiler)

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
        # Cache of validated configs per plugin signature
        self._resolved_config_cache: Dict[tuple, Dict[str, Any]] = {}

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

    def set_config(self, config: Dict[str, Any]):
        """Update the context configuration."""
        self.config.update(config)

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
            # Re-entrancy guard
            if (run_id, data_name) in self._in_progress:
                raise RuntimeError(
                    f"Re-entrant call for ({run_id}, {data_name}) detected. "
                    "This usually indicates a circular dependency at runtime."
                )

            self._in_progress[(run_id, data_name)] = True
            try:
                # 1. Resolve execution plan
                try:
                    with self.profiler.timeit("context.resolve_dependencies"):
                        plan = self.resolve_dependencies(data_name)
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
                del self._in_progress[(run_id, data_name)]

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
            if not self.storage._acquire_lock(lock_path):
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
                    except:
                        pass
                raise e
            finally:
                self.storage._release_lock(lock_path)
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
        """
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
        """
        import hashlib
        import json

        lineage = self.get_lineage(data_name)
        # Use default=str to handle any non-serializable objects gracefully,
        # though we try to standardize them in get_lineage.
        lineage_json = json.dumps(lineage, sort_keys=True, default=str)
        lineage_hash = hashlib.sha1(lineage_json.encode()).hexdigest()[:8]

        return f"{run_id}-{data_name}-{lineage_hash}"

    def __repr__(self):
        return f"Context(storage='{self.storage_dir}', plugins={self.list_provided_data()})"
