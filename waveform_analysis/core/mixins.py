import functools
import os
from contextlib import nullcontext
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .cache import WATCH_SIG_KEY, CacheManager


def chainable_step(fn: Callable):
    """Decorator for chainable steps with integrated caching and error handling."""

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        name = fn.__name__
        cfg: Dict[str, Any] = {}

        # 打印当前步骤
        verbose = kwargs.get("verbose", True)
        run_id = kwargs.get("run_id") or getattr(self, "char", "default")

        # 首次运行打印完整报告
        if verbose and not getattr(self, "_cache_report_printed", False):
            if hasattr(self, "print_cache_report"):
                self.print_cache_report()
                setattr(self, "_cache_report_printed", True)

        if verbose:
            print(f"[*] Running step: {name} (run_id: {run_id})")
            if hasattr(self, "check_cache_status"):
                status = self.check_cache_status(load_sig=False).get(name)
                if status:
                    m = "YES" if status["in_memory"] else "no"
                    d = "YES" if status["on_disk"] else "no"
                    # 如果不在磁盘上，Valid 显示 -
                    # 如果在磁盘上但未验证，Valid 显示 ?
                    # 如果在磁盘上且验证通过，Valid 显示 YES
                    if not status["on_disk"]:
                        v = "-"
                    elif status["disk_valid"]:
                        v = "YES"
                    else:
                        v = "?"
                    print(f"    [cache-status] Mem: {m}, Disk: {d}, Valid: {v}")

        try:
            # 缓存逻辑集成
            if hasattr(self, "_cache_config"):
                cfg = self._cache_config.get(name, {})
                if cfg.get("enabled"):
                    # 磁盘加载逻辑
                    persist = cfg.get("persist_path")
                    backend = cfg.get("backend", "joblib")
                    if persist:
                        data = CacheManager.load_data(persist, backend)
                        if data:
                            watch_attrs = cfg.get("watch_attrs") or []
                            saved_sig = data.get(WATCH_SIG_KEY)
                            if not watch_attrs or saved_sig == CacheManager.compute_watch_signature(self, watch_attrs):
                                for k, v in data.items():
                                    if k != WATCH_SIG_KEY:
                                        # Use _set_data if available (Context/WaveformDataset)
                                        if hasattr(self, "_set_data"):
                                            self._set_data(run_id, k, v)
                                        else:
                                            # Fallback for regular attributes, avoid setting read-only properties
                                            cls_attr = getattr(self.__class__, k, None)
                                            if not isinstance(cls_attr, property):
                                                setattr(self, k, v)
                                self._cache[name] = {k: v for k, v in data.items() if k != WATCH_SIG_KEY}
                                self._record_step_success(name)
                                if verbose:
                                    print(f"[cache] Step '{name}' loaded from disk (run_id: {run_id})")
                                return self
                    # 内存加载逻辑
                    mem = self._cache.get(name)
                    if mem is not None:
                        for k, v in mem.items():
                            if hasattr(self, "_set_data"):
                                self._set_data(run_id, k, v)
                            else:
                                # Fallback for regular attributes, avoid setting read-only properties
                                cls_attr = getattr(self.__class__, k, None)
                                if not isinstance(cls_attr, property):
                                    setattr(self, k, v)
                        self._record_step_success(name)
                        if verbose:
                            print(f"[cache] Step '{name}' loaded from memory (run_id: {run_id})")
                        return self

            # 执行实际函数
            res = fn(self, *args, **kwargs)

            # 缓存结果
            if cfg.get("enabled"):
                cache_attrs = cfg.get("cache_attrs") or []
                cache_data = {}
                for attr in cache_attrs:
                    if hasattr(self, attr):
                        cache_data[attr] = getattr(self, attr)

                self._cache[name] = cache_data
                if cfg.get("persist_path"):
                    if cfg.get("watch_attrs"):
                        cache_data[WATCH_SIG_KEY] = CacheManager.compute_watch_signature(self, cfg["watch_attrs"])
                    CacheManager.save_data(cfg["persist_path"], cache_data, cfg.get("backend", "joblib"))

            self._record_step_success(name)
            return self if res is None else res
        except Exception as e:
            self._record_step_failure(name, e)
            if getattr(self, "raise_on_error", False):
                raise
            print(f"[warning] step '{name}' failed: {e}")
            return self

    return wrapper


class CacheMixin:
    """Mixin for handling memory and disk caching in WaveformDataset."""

    def __init__(self):
        # _cache: { step_name: {attr_name: value, ...} }
        self._cache: Dict[str, Dict[str, object]] = {}
        # _cache_config: { step_name: {enabled: bool, attrs: [str], persist_path: Optional[str]} }
        self._cache_config: Dict[str, Dict[str, object]] = {}
        self.cache_dir: Optional[str] = None

    def set_step_cache(
        self,
        step_name: str,
        enabled: bool = True,
        attrs: Optional[List[str]] = None,
        persist_path: Optional[str] = None,
        watch_attrs: Optional[List[str]] = None,
        backend: str = "joblib",
    ) -> None:
        """配置指定步骤的缓存。"""
        self._cache_config[step_name] = {
            "enabled": bool(enabled),
            "attrs": list(attrs or []),
            "persist_path": persist_path,
            "watch_attrs": list(watch_attrs or []),
            "backend": backend,
        }

    def clear_cache(self, step_name: Optional[str] = None) -> None:
        """清除指定步骤或所有步骤的缓存。"""
        if step_name:
            self._cache.pop(step_name, None)
            self._cache_config.pop(step_name, None)
        else:
            self._cache.clear()
            self._cache_config.clear()

    def get_cached_result(self, step_name: str) -> Optional[Dict[str, object]]:
        """返回指定步骤的内存缓存字典（若存在）。"""
        return self._cache.get(step_name)

    def save_step_cache(self, step_name: str, path: str, backend: str = "joblib") -> bool:
        """
        将当前内存缓存写入磁盘，格式与装饰器加载时期待的 persist 文件兼容。
        """
        cache = self._cache.get(step_name)
        if not cache:
            return False

        cache_data = {k: v for k, v in cache.items()}

        cfg = self._cache_config.get(step_name, {})
        watch_attrs = cfg.get("watch_attrs") or []
        if watch_attrs:
            try:
                sig = CacheManager.compute_watch_signature(self, watch_attrs)
                cache_data[WATCH_SIG_KEY] = sig
            except Exception:
                pass

        return CacheManager.save_data(path, cache_data, backend)

    def check_cache_status(self, load_sig: bool = False) -> Dict[str, Dict[str, Any]]:
        """检查所有步骤的缓存状态。

        Args:
            load_sig: 是否加载磁盘文件以验证签名（较慢）。
        """
        report = {}
        for name, cfg in self._cache_config.items():
            in_mem = name in self._cache
            on_disk = False
            disk_valid = False
            persist_path = cfg.get("persist_path")
            if persist_path and os.path.exists(persist_path):
                on_disk = True
                watch_attrs = cfg.get("watch_attrs")
                if watch_attrs and load_sig:
                    try:
                        current_sig = CacheManager.compute_watch_signature(self, watch_attrs)
                        data = CacheManager.load_data(persist_path, cfg.get("backend", "joblib"))
                        if data and data.get(WATCH_SIG_KEY) == current_sig:
                            disk_valid = True
                    except Exception:
                        pass
                elif not watch_attrs:
                    disk_valid = True
            report[name] = {
                "in_memory": in_mem,
                "on_disk": on_disk,
                "disk_valid": disk_valid,
                "backend": cfg.get("backend"),
                "path": persist_path,
            }
        return report

    def print_cache_report(self, verify: bool = False) -> None:
        """打印缓存状态报告。

        Args:
            verify: 是否通过加载磁盘文件来验证签名（对于大文件可能较慢）。
        """
        report = self.check_cache_status(load_sig=verify)
        print(f"\nCache report (before running steps):")
        if not verify:
            print(f"注: 'Valid' 列仅表示文件存在，未验证内容签名 (使用 verify=True 验证)")
        print(f"{'Step Name':<25} | {'Mem':<5} | {'Disk':<5} | {'Valid':<5} | {'Backend':<8}")
        print("-" * 65)
        for name, s in report.items():
            m = "YES" if s["in_memory"] else "no"
            d = "YES" if s["on_disk"] else "no"
            # 如果在磁盘上且验证通过 -> YES
            # 如果在磁盘上且验证失败 -> no
            # 如果在磁盘上但未验证 -> ?
            # 如果不在磁盘上 -> -
            if s["disk_valid"]:
                v = "YES"
            elif s["on_disk"]:
                v = "no" if verify else "?"
            else:
                v = "-"
            b = s["backend"] or "-"
            print(f"{name:<25} | {m:<5} | {d:<5} | {v:<5} | {b:<8}")
        print()


class StepMixin:
    """Mixin for chainable step management and error tracking."""

    chainable_step = staticmethod(chainable_step)

    def __init__(self):
        self._step_errors: Dict[str, str] = {}
        self._step_status: Dict[str, str] = {}
        self._last_failed_step: Optional[str] = None
        self.raise_on_error: bool = False

    def _record_step_success(self, name: str) -> None:
        self._step_status[name] = "success"

    def _record_step_failure(self, name: str, exc: Exception) -> None:
        self._step_status[name] = "failed"
        self._step_errors[name] = str(exc)
        self._last_failed_step = name

    def set_raise_on_error(self, value: bool) -> None:
        """Toggle whether chainable steps raise on failure."""
        self.raise_on_error = bool(value)

    def get_step_errors(self) -> Dict[str, str]:
        return self._step_errors

    def clear_step_errors(self) -> None:
        self._step_errors.clear()
        self._step_status.clear()
        self._last_failed_step = None


class PluginMixin:
    """Mixin for orchestrating plugins in WaveformDataset."""

    def __init__(self):
        self._plugins: Dict[str, Any] = {}

    def register_plugin(self, plugin: Any, allow_override: bool = False) -> None:
        """
        Register a plugin instance with strict validation.
        """
        # 1. Basic validation
        if hasattr(plugin, "validate"):
            plugin.validate()

        provides = plugin.provides

        # 2. Uniqueness check
        if provides in self._plugins and not allow_override:
            existing = self._plugins[provides]
            raise RuntimeError(
                f"Plugin conflict: '{provides}' is already provided by {existing.__class__.__name__}. "
                f"Use allow_override=True if you want to replace it."
            )

        # 3. Record metadata
        import inspect

        plugin._registered_class = plugin.__class__.__name__
        try:
            module = inspect.getmodule(plugin.__class__)
            plugin._registered_from_module = module.__name__ if module else "unknown"
        except Exception:
            plugin._registered_from_module = "unknown"

        # 4. Register
        self._plugins[provides] = plugin

    def resolve_dependencies(self, target: str) -> List[str]:
        """
        Resolve dependencies and return a list of data_names to compute in order.
        Uses topological sort to determine execution order and detect cycles.
        """
        profiler = getattr(self, "profiler", None)
        with profiler.timeit("context.resolve_dependencies") if profiler else nullcontext():
            plan = []
            visited = set()
            visiting_stack = []  # Use a stack to track the path for better error messages

            def visit(node):
                if node in visiting_stack:
                    # Found a cycle!
                    cycle_path = " -> ".join(visiting_stack + [node])
                    raise RuntimeError(f"Circular dependency detected: {cycle_path}")

                if node in visited:
                    return

                if node not in self._plugins:
                    # If it's not provided by a plugin, check if it's already in memory
                    # (e.g. manually set or provided by a side-effect)
                    # If it's not a plugin and not a known attribute, it's a missing dependency
                    if not hasattr(self, node) or getattr(self, node) is None:
                        # Check memory results (this is tricky without run_id, but we can check if it's a known data name)
                        _results = getattr(self, "_results", {})
                        if not any(k[1] == node for k in _results.keys()):
                            raise ValueError(f"No plugin registered for '{node}'")

                    # If it's not a plugin, it's a leaf node (base input)
                    visited.add(node)
                    return

                visiting_stack.append(node)
                plugin = self._plugins[node]
                for dep in plugin.depends_on:
                    try:
                        visit(dep)
                    except ValueError as e:
                        # Re-raise with path information
                        if "No plugin registered" in str(e):
                            raise ValueError(f"Missing dependency: {' -> '.join(visiting_stack + [dep])}") from None
                        raise

                visiting_stack.pop()
                visited.add(node)
                plan.append(node)

        if target not in self._plugins:
            # Check if it's already available
            _get_mem = getattr(self, "_get_data_from_memory", None)
            if hasattr(self, target) and getattr(self, target) is not None:
                return []
            raise ValueError(f"No plugin registered for '{target}'")

        visit(target)
        return plan

    def run_plugin(self, run_id: str, data_name: str, **kwargs) -> Any:
        """
        Run a plugin that provides data_name, automatically resolving dependencies.
        """
        # This method is usually overridden by Context to add caching/saving.
        # If not overridden, we use a simple implementation.

        # 1. Resolve execution plan
        try:
            plan = self.resolve_dependencies(data_name)
        except ValueError:
            _get_mem = getattr(self, "_get_data_from_memory", None)
            if _get_mem:
                val = _get_mem(run_id, data_name)
                if val is not None:
                    return val
            elif hasattr(self, data_name) and getattr(self, data_name) is not None:
                return getattr(self, data_name)
            raise

        # 2. Execute plan in order
        for name in plan:
            # Check if already computed
            _get_mem = getattr(self, "_get_data_from_memory", None)
            if _get_mem:
                if _get_mem(run_id, name) is not None:
                    continue
            elif hasattr(self, name) and getattr(self, name) is not None:
                continue

            if name not in self._plugins:
                raise RuntimeError(f"Dependency '{name}' is missing and no plugin provides it.")

            plugin = self._plugins[name]
            # Inject run_id into kwargs
            plugin_kwargs = kwargs.copy()
            plugin_kwargs["run_id"] = run_id
            result = plugin.compute(self, **plugin_kwargs)

            # Use _set_data if available (Context has it)
            _set_data = getattr(self, "_set_data", None)
            if _set_data:
                try:
                    _set_data(run_id, name, result)
                except TypeError:
                    # Fallback for old _set_data signature if any
                    _set_data(name, result)
            else:
                setattr(self, name, result)

        # Use _get_data_from_memory if available
        _get_mem = getattr(self, "_get_data_from_memory", None)
        if _get_mem:
            return _get_mem(run_id, data_name)
        return getattr(self, data_name)
