# -*- coding: utf-8 -*-
"""
Context 模块 - 插件系统的核心调度器。

负责管理插件注册、依赖解析、配置分发以及数据缓存的生命周期。
它是整个分析框架的"大脑"，通过 DAG（有向无环图）确保数据按需、有序地计算。
支持多级缓存校验和血缘追踪，是实现高效、可重复分析的基础。
"""

# 1. Standard library imports
import hashlib
import json
import logging
import os
import re
import threading
import warnings
from typing import Any, Dict, Iterator, List, Optional, Type, Union, cast

# 2. Third-party imports
import numpy as np
import pandas as pd

# 3. Local imports (使用相对导入)
from ..utils.visualization.lineage_visualizer import (
    plot_lineage_labview,
    plot_lineage_plotly,
)
from .execution.validation import ValidationManager
from .foundation.error import ErrorManager
from .foundation.exceptions import ErrorSeverity
from .foundation.mixins import CacheMixin, PluginMixin
from .foundation.utils import OneTimeGenerator, Profiler
from .plugins.core.base import Plugin
from .storage.cache_manager import RuntimeCacheManager
from .storage.memmap import MemmapStorage


class Context(CacheMixin, PluginMixin):
    """
    The Context orchestrates plugins and manages data storage/caching.
    Inspired by strax, it is the main entry point for data analysis.
    """

    # 保留名称集合：这些名称不能用作数据名，因为它们是 Context 的方法或属性
    _RESERVED_NAMES = frozenset({
        "analyze_dependencies",
        "build_time_index",
        "clear_cache_for",
        "clear_config_cache",
        "clear_performance_caches",
        "clear_time_index",
        "config",
        "get_data",
        "get_config",
        "get_data_time_range",
        "get_lineage",
        "get_performance_report",
        "get_time_index_stats",
        "help",
        "key_for",
        "list_plugin_configs",
        "list_provided_data",
        "logger",
        "plot_lineage",
        "preview_execution",
        "profiling_summary",
        "quickstart",
        "register",
        "resolve_dependencies",
        "run_plugin",
        "set_config",
        "show_config",
        "storage",
        "storage_dir",
    })

    def __init__(
        self,
        storage_dir: str = "./strax_data",
        config: Optional[Dict[str, Any]] = None,
        storage: Optional[Any] = None,
        plugin_dirs: Optional[List[str]] = None,
        auto_discover_plugins: bool = False,
        enable_stats: bool = False,
        stats_mode: str = 'basic',
        stats_log_file: Optional[str] = None,
        work_dir: Optional[str] = None,
        use_run_subdirs: bool = True,
    ):
        """
        Initialize Context.

        Args:
            storage_dir: 默认存储目录（使用 MemmapStorage 时的旧版模式）
            config: 全局配置字典
            storage: 自定义存储后端（必须实现 StorageBackend 接口）
                    如果为 None，使用默认的 MemmapStorage
            plugin_dirs: 插件搜索目录列表
            auto_discover_plugins: 是否自动发现并注册插件
            enable_stats: 是否启用插件性能统计
            stats_mode: 统计模式 ('off', 'basic', 'detailed')
            stats_log_file: 统计日志文件路径
            work_dir: 工作目录（新版分层模式）。如果设置，数据将按 run_id 分目录存储。
            use_run_subdirs: 是否启用 run_id 子目录（仅当 work_dir 设置时生效）

        Storage Modes:
            1. 旧版兼容模式（work_dir=None 且 storage_dir 有旧缓存）：
               - 所有文件在 storage_dir 根目录（扁平结构）

            2. 新版分层模式（work_dir=None 且 storage_dir 为空，或显式设置 work_dir）：
               - 数据按 run_id 分目录存储
               - 结构：work_dir/{run_id}/data/*.bin

        Examples:
            >>> # 旧版兼容模式（storage_dir 有旧缓存会自动检测）
            >>> ctx = Context(storage_dir="./strax_data")

            >>> # 新版分层模式（显式指定 work_dir）
            >>> ctx = Context(work_dir="./workspace")

            >>> # 使用 SQLite 存储
            >>> from waveform_analysis.core.storage.backends import SQLiteBackend
            >>> ctx = Context(storage=SQLiteBackend("./data.db"))

            >>> # 启用详细统计和日志
            >>> ctx = Context(enable_stats=True, stats_mode='detailed', stats_log_file='./logs/plugins.log')
        """
        CacheMixin.__init__(self)
        PluginMixin.__init__(self)

        self.profiler = Profiler()
        self.storage_dir = storage_dir
        self.work_dir = work_dir
        self.config = config or {}

        # Extensibility: Allow custom storage backend
        if storage is not None:
            # 验证存储后端接口（可选，记录警告）
            self._validate_storage_backend(storage)
            self.storage = storage
        else:
            # 智能默认：检测旧缓存，自动回退
            if work_dir is None:
                # 未指定 work_dir，检测 storage_dir 是否有旧缓存
                if self._has_legacy_cache(storage_dir):
                    # 存在旧缓存，使用旧模式（扁平结构）
                    self.storage = MemmapStorage(
                        storage_dir,
                        profiler=self.profiler
                    )
                else:
                    # 全新项目，使用新模式（work_dir=storage_dir）
                    self.storage = MemmapStorage(
                        storage_dir,
                        work_dir=storage_dir,
                        use_run_subdirs=use_run_subdirs,
                        profiler=self.profiler
                    )
            else:
                # 显式指定 work_dir，使用新模式
                self.storage = MemmapStorage(
                    storage_dir,  # 保留用于回退
                    work_dir=work_dir,
                    use_run_subdirs=use_run_subdirs,
                    profiler=self.profiler
                )

        # Setup logger
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        # Initialize ErrorManager
        self._error_manager = ErrorManager(self.logger)

        # Initialize RuntimeCacheManager
        self._cache_manager = RuntimeCacheManager(self)

        # Initialize ValidationManager
        self._validation_manager = ValidationManager(self)

        # Setup plugin statistics collector
        self.enable_stats = enable_stats
        self.stats_collector = None
        if enable_stats:
            from waveform_analysis.core.plugins.core.stats import PluginStatsCollector
            # Create dedicated collector for this context (not global singleton)
            self.stats_collector = PluginStatsCollector(
                mode=stats_mode,
                log_file=stats_log_file
            )

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

        # Help system (lazy initialization)
        self._help_system = None

    def register(self, *plugins: Union[Plugin, Type[Plugin], Any], allow_override: bool = False):
        """
        注册一个或多个插件到 Context 中。

        此方法是注册插件的便捷接口，支持多种输入类型：
        - 插件实例：直接注册
        - 插件类：自动实例化后注册
        - Python 模块：自动发现模块中的所有 Plugin 子类并注册

        注册后的插件可以通过其 `provides` 属性标识的数据名称来访问。
        Context 会自动管理插件之间的依赖关系，并在获取数据时按需执行。

        Args:
            *plugins: 要注册的插件，可以是以下类型之一：
                - Plugin 实例：已实例化的插件对象
                - Plugin 类：插件类，会自动调用无参构造函数实例化
                - Python 模块：包含 Plugin 子类的模块，会自动发现并注册所有插件类
            allow_override: 如果为 True，允许覆盖已注册的同名插件（基于 `provides` 属性）
                          如果为 False（默认），注册同名插件会抛出 RuntimeError

        Raises:
            RuntimeError: 当尝试注册已存在的插件且 `allow_override=False` 时
            ValueError: 当插件验证失败时（通过 `plugin.validate()` 方法）
            TypeError: 当插件依赖版本不兼容时

        Examples:
            >>> from waveform_analysis.core.context import Context
            >>> from waveform_analysis.core.plugins.builtin.standard import (
            ...     RawFilesPlugin, WaveformsPlugin, StWaveformsPlugin
            ... )
            >>>
            >>> ctx = Context(storage_dir="./strax_data")
            >>>
            >>> # 方式1: 注册插件实例
            >>> ctx.register(RawFilesPlugin())
            >>>
            >>> # 方式2: 注册插件类（会自动实例化）
            >>> ctx.register(WaveformsPlugin)
            >>>
            >>> # 方式3: 一次注册多个插件
            >>> ctx.register(
            ...     RawFilesPlugin(),
            ...     WaveformsPlugin(),
            ...     StWaveformsPlugin()
            ... )
            >>>
            >>> # 方式4: 注册模块中的所有插件
            >>> import waveform_analysis.core.plugins.builtin.standard as standard_plugins
            >>> ctx.register(standard_plugins)
            >>>
            >>> # 方式5: 允许覆盖已注册的插件
            >>> ctx.register(RawFilesPlugin(), allow_override=True)
            >>>
            >>> # 注册后可以通过数据名称访问
            >>> raw_files = ctx.get_data("run_001", "raw_files")

        Notes:
            - 插件注册时会自动调用 `plugin.validate()` 进行验证
            - 注册插件会清除相关的执行计划缓存，确保依赖关系正确
            - 如果插件类需要参数，请先实例化再传入，不要直接传入类
            - 模块注册会递归查找所有 Plugin 子类，但会跳过 Plugin 基类本身
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
        from waveform_analysis.core.plugins.core.loader import PluginLoader

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

    def set_config(self, config: Dict[str, Any], plugin_name: Optional[str] = None):
        """
        更新上下文配置。
        
        支持三种配置方式：
        1. 全局配置：set_config({'threshold': 50})
        2. 插件特定配置（命名空间）：set_config({'threshold': 50}, plugin_name='my_plugin')
        3. 嵌套字典格式：set_config({'my_plugin': {'threshold': 50}})
        
        Args:
            config: 配置字典
            plugin_name: 可选，如果提供，则所有配置项都会作为该插件的命名空间配置
        
        Examples:
            >>> # 全局配置
            >>> ctx.set_config({'n_channels': 2, 'threshold': 50})
            
            >>> # 插件特定配置（推荐，避免冲突）
            >>> ctx.set_config({'threshold': 50}, plugin_name='peaks')
            >>> # 等价于: ctx.set_config({'peaks': {'threshold': 50}})
            >>> # 或: ctx.set_config({'peaks.threshold': 50})
            
            >>> # 查看配置归属
            >>> ctx.list_plugin_configs()  # 列出所有插件的配置选项
        """
        if plugin_name is not None:
            # 按插件名称设置配置，自动使用命名空间
            if plugin_name not in self._plugins:
                self.logger.warning(
                    f"Plugin '{plugin_name}' is not registered. "
                    f"Config will be set but may not be used by any plugin."
                )
            # 使用嵌套字典格式（优先级最高）
            if plugin_name not in self.config:
                self.config[plugin_name] = {}
            if isinstance(self.config[plugin_name], dict):
                self.config[plugin_name].update(config)
            else:
                # 如果已存在但不是字典，转换为字典
                self.config[plugin_name] = {**config}
        else:
            # 直接更新全局配置
            self.config.update(config)

        # 清除配置缓存，确保新配置生效
        self.clear_config_cache()

    @staticmethod
    def _has_legacy_cache(base_dir: str) -> bool:
        """
        检测是否存在旧格式缓存（扁平结构）

        检查 base_dir 根目录下是否有形如 "run_xxx-data_name-hash.bin" 的文件。
        如果存在，说明这是旧版缓存目录，应该使用旧模式。

        Args:
            base_dir: 检查的目录路径

        Returns:
            True 如果存在旧格式缓存文件，False 否则
        """
        if not os.path.exists(base_dir):
            return False

        try:
            for f in os.listdir(base_dir):
                # 跳过目录和隐藏文件
                if f.startswith('.') or f.startswith('_'):
                    continue
                # 检查是否是旧格式的 .bin 或 .json 文件
                if f.endswith('.bin') or f.endswith('.json'):
                    # 旧格式: "run_xxx-data_name-hash.bin"
                    # 解析文件名，检查是否包含 run_id 前缀
                    parts = f.rsplit('.', 1)[0].split('-')
                    if len(parts) >= 2:
                        # 文件名包含多个 - 分隔的部分，可能是旧格式
                        return True
        except (PermissionError, OSError):
            # 如果无法读取目录，假设是新项目
            return False

        return False

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
        """计算插件配置选项的值（不进行验证）。

        配置值的查找优先级（从高到低）：
        1. 插件特定配置（嵌套字典）: config[plugin_name][option_name]
        2. 插件特定配置（点分隔）: config['plugin_name.option_name']
        3. 全局配置: config[option_name]
        4. 插件选项默认值: plugin.options[name].default

        Args:
            plugin: 目标插件实例
            name: 配置选项名称

        Returns:
            解析后的配置值（任意类型）

        Raises:
            KeyError: 当插件没有该配置选项时

        Examples:
            >>> # 假设 plugin.options = {'threshold': Option(default=0.5)}
            >>> ctx.config = {'my_plugin': {'threshold': 0.8}}
            >>> ctx._resolve_config_value(plugin, 'threshold')
            0.8  # 使用插件特定配置

            >>> ctx.config = {'threshold': 0.6}
            >>> ctx._resolve_config_value(plugin, 'threshold')
            0.6  # 使用全局配置

            >>> ctx.config = {}
            >>> ctx._resolve_config_value(plugin, 'threshold')
            0.5  # 使用默认值
        """
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
        """获取插件的配置值（带验证和类型转换）。

        这是获取插件配置的推荐方法。相比 _resolve_config_value，此方法会：
        1. 应用插件选项的类型验证
        2. 执行值的范围检查（如果定义）
        3. 调用自定义验证器（如果存在）

        配置支持命名空间，查找顺序同 _resolve_config_value。

        Args:
            plugin: 目标插件实例
            name: 配置选项名称

        Returns:
            验证并可能转换后的配置值

        Raises:
            KeyError: 当插件没有该配置选项时
            ValueError: 当配置值不符合验证规则时
            TypeError: 当配置值类型不匹配时

        Examples:
            >>> # 假设选项定义为 Option(type=int, validator=lambda x: 0 < x < 100)
            >>> ctx.config = {'my_plugin': {'threshold': '50'}}  # 字符串形式
            >>> ctx.get_config(plugin, 'threshold')
            50  # 自动转换为 int

            >>> ctx.config = {'threshold': 150}  # 超出范围
            >>> ctx.get_config(plugin, 'threshold')
            ValueError: threshold must satisfy validator
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
            # Check if it's a property on the class (e.g. in WaveformDataset)
            cls_attr = getattr(self.__class__, name, None)
            is_prop = isinstance(cls_attr, property)

            if name in self._RESERVED_NAMES or (hasattr(self.__class__, name) and not is_prop):
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
        if (
            name not in self._RESERVED_NAMES
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
        if not self.storage.exists(key, run_id):
            # Check if it's a multi-channel data (e.g. peaks_ch0)
            if not self.storage.exists(f"{key}_ch0", run_id):
                return None

        meta = self.storage.get_metadata(key, run_id) or self.storage.get_metadata(f"{key}_ch0", run_id)
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
            data = self.storage.load_dataframe(key, run_id)
        elif self.storage.exists(f"{key}_ch0", run_id):
            # Load multi-channel data
            data = []
            i = 0
            while self.storage.exists(f"{key}_ch{i}", run_id):
                data.append(self.storage.load_memmap(f"{key}_ch{i}", run_id))
                i += 1
        else:
            data = self.storage.load_memmap(key, run_id)

        if data is not None:
            if self.config.get("show_progress", True):
                print(f"[cache] Loaded '{name}' from disk (run_id: {run_id})")
            self._set_data(run_id, name, data)
        return data

    def get_data(self, run_id: str, data_name: str, show_progress: bool = False, progress_desc: Optional[str] = None, **kwargs) -> Any:
        """
        Retrieve data by name for a specific run.
        If data is not in memory/cache, it will trigger the necessary plugins.

        参数:
            run_id: Run identifier
            data_name: Name of the data to retrieve
            show_progress: Whether to show progress bar during plugin execution
            progress_desc: Custom description for progress bar (default: auto-generated)
            **kwargs: Additional arguments passed to plugins
        """
        # 1. Check memory cache
        val = self._get_data_from_memory(run_id, data_name)
        if val is not None:
            # Memory cache hit at top level - record stats if enabled
            if self.stats_collector and self.stats_collector.is_enabled():
                self.stats_collector.start_execution(data_name, run_id)
                self.stats_collector.end_execution(data_name, success=True, cache_hit=True)
            return val

        # 2. Check disk cache (memmap)
        # Only check if it's a plugin-provided data
        if data_name in self._plugins:
            key = self.key_for(run_id, data_name)
            data = self._load_from_disk_with_check(run_id, data_name, key)
            if data is not None:
                # Disk cache hit at top level - record stats if enabled
                if self.stats_collector and self.stats_collector.is_enabled():
                    self.stats_collector.start_execution(data_name, run_id)
                    self.stats_collector.end_execution(data_name, success=True, cache_hit=True)
                return data

        # 3. Run plugin (this will also handle dependencies)
        return self.run_plugin(run_id, data_name, show_progress=show_progress, progress_desc=progress_desc, **kwargs)

    def run_plugin(self, run_id: str, data_name: str, show_progress: bool = False, progress_desc: Optional[str] = None, **kwargs) -> Any:
        """
        Override run_plugin to add saving logic and config resolution.

        参数:
            run_id: Run identifier
            data_name: Name of the data to produce
            show_progress: Whether to show progress bar during plugin execution
            progress_desc: Custom description for progress bar (default: auto-generated)
            **kwargs: Additional arguments passed to plugins
        """
        with self.profiler.timeit("context.run_plugin"):
            # 1. Check re-entrancy and mark as in-progress
            self._check_reentrancy(run_id, data_name)

            # Initialize variables for finally block
            tracker = None
            bar_name = None

            try:
                # 2. Resolve execution plan (with caching and fallback)
                plan = self._resolve_execution_plan(run_id, data_name)

                # Early return if data already in memory
                if not plan:
                    return self._get_data_from_memory(run_id, data_name)

                # 3. Initialize progress tracking
                tracker, bar_name = self._init_progress_tracking(
                    show_progress, plan, run_id, data_name, progress_desc
                )

                # 4. Execute plan in order
                for name in plan:
                    self._execute_single_plugin(name, run_id, data_name, kwargs, tracker, bar_name)

                return self._get_data_from_memory(run_id, data_name)
            finally:
                # 5. Cleanup execution state
                self._cleanup_execution(run_id, data_name, tracker, bar_name)

    def _check_reentrancy(self, run_id: str, data_name: str) -> None:
        """检查并记录重入状态

        Args:
            run_id: 运行标识符
            data_name: 数据名称

        Raises:
            RuntimeError: 当检测到重入调用时
        """
        with self._in_progress_lock:
            if (run_id, data_name) in self._in_progress:
                raise RuntimeError(
                    f"Re-entrant call for ({run_id}, {data_name}) detected. "
                    "This usually indicates a circular dependency at runtime."
                )
            self._in_progress[(run_id, data_name)] = True

    def _resolve_execution_plan(self, run_id: str, data_name: str) -> List[str]:
        """解析执行计划（带缓存）

        Args:
            run_id: 运行标识符
            data_name: 目标数据名称

        Returns:
            执行计划（插件名称列表）

        Raises:
            ValueError: 当依赖解析失败时
        """
        try:
            with self.profiler.timeit("context.resolve_dependencies"):
                # Check cache first
                if data_name in self._execution_plan_cache:
                    plan = self._execution_plan_cache[data_name]
                else:
                    plan = self.resolve_dependencies(data_name)
                    self._execution_plan_cache[data_name] = plan
            return plan
        except ValueError:
            # Fallback: check if data already in memory
            val = self._get_data_from_memory(run_id, data_name)
            if val is not None:
                return []  # Empty plan, data already available
            raise

    def _init_progress_tracking(
        self,
        show_progress: bool,
        plan: List[str],
        run_id: str,
        data_name: str,
        progress_desc: Optional[str]
    ) -> tuple:
        """初始化进度追踪

        Args:
            show_progress: 是否显示进度条
            plan: 执行计划
            run_id: 运行标识符
            data_name: 目标数据名称
            progress_desc: 自定义进度描述

        Returns:
            (tracker, bar_name) 元组
        """
        if show_progress and len(plan) > 0:
            from waveform_analysis.core.foundation.progress import get_global_tracker
            tracker = get_global_tracker()
            bar_name = f"load_{run_id}_{data_name}"
            desc = progress_desc or f"Loading {data_name}"
            tracker.create_bar(bar_name, total=len(plan), desc=desc, unit="plugin")
            return tracker, bar_name
        return None, None

    def _cleanup_execution(
        self,
        run_id: str,
        data_name: str,
        tracker: Optional[Any],
        bar_name: Optional[str]
    ) -> None:
        """清理执行状态

        Args:
            run_id: 运行标识符
            data_name: 数据名称
            tracker: 进度追踪器
            bar_name: 进度条名称
        """
        # Close progress bar
        if tracker and bar_name:
            tracker.close(bar_name)

        # Remove re-entrancy flag
        with self._in_progress_lock:
            self._in_progress.pop((run_id, data_name), None)

    def _record_cache_hit(
        self,
        name: str,
        run_id: str,
        tracker: Optional[Any],
        bar_name: Optional[str]
    ) -> None:
        """记录缓存命中并更新进度

        Args:
            name: 插件名称
            run_id: 运行标识符
            tracker: 进度追踪器
            bar_name: 进度条名称
        """
        # 更新进度条（缓存命中）
        if tracker and bar_name:
            tracker.update(bar_name, n=1)

    def _calculate_input_size(self, plugin: Plugin, run_id: str) -> Optional[float]:
        """计算插件输入数据大小（MB）

        Args:
            plugin: 插件实例
            run_id: 运行标识符

        Returns:
            输入数据大小（MB），如果无法计算则返回 None
        """
        if not (self.stats_collector and self.stats_collector.mode == 'detailed'):
            return None

        try:
            total_bytes = 0
            for dep_name in plugin.depends_on:
                dep_data = self._get_data_from_memory(run_id, dep_name)
                if dep_data is not None:
                    if isinstance(dep_data, np.ndarray):
                        total_bytes += dep_data.nbytes
                    elif isinstance(dep_data, list):
                        total_bytes += sum(
                            arr.nbytes for arr in dep_data
                            if isinstance(arr, np.ndarray)
                        )
            return total_bytes / (1024 * 1024) if total_bytes > 0 else None
        except (AttributeError, TypeError) as e:
            # 某些数据类型可能没有 nbytes 属性
            self.logger.debug(f"Could not calculate input size for {plugin.provides}: {e}")
            return None
        except Exception as e:
            # 其他未预期的错误
            self.logger.warning(f"Unexpected error calculating input size for {plugin.provides}: {e}")
            return None

    def _prepare_side_effect_isolation(
        self,
        plugin: Plugin,
        run_id: str,
        kwargs: dict
    ) -> dict:
        """准备侧作用隔离

        Args:
            plugin: 插件实例
            run_id: 运行标识符
            kwargs: 插件参数字典

        Returns:
            更新后的 kwargs 字典
        """
        if getattr(plugin, "is_side_effect", False):
            # 检查存储模式，使用适当的副作用目录
            if hasattr(self.storage, 'get_run_side_effects_dir'):
                # 新模式：使用 storage 的方法获取正确路径
                side_effect_dir = os.path.join(
                    self.storage.get_run_side_effects_dir(run_id), plugin.provides
                )
            else:
                # 旧模式或自定义存储后端：使用 storage_dir
                side_effect_dir = os.path.join(
                    self.storage_dir, "_side_effects", run_id, plugin.provides
                )
            os.makedirs(side_effect_dir, exist_ok=True)
            kwargs = kwargs.copy()
            kwargs["output_dir"] = side_effect_dir
        return kwargs

    def _calculate_output_size(self, result: Any) -> Optional[float]:
        """计算输出数据大小（MB）

        Args:
            result: 插件输出结果

        Returns:
            输出数据大小（MB），如果无法计算则返回 None
        """
        if not (self.stats_collector and self.stats_collector.mode == 'detailed'):
            return None

        try:
            if isinstance(result, np.ndarray):
                return result.nbytes / (1024 * 1024)
            elif isinstance(result, list) and all(isinstance(x, np.ndarray) for x in result):
                total_bytes = sum(arr.nbytes for arr in result)
                return total_bytes / (1024 * 1024)
            elif isinstance(result, pd.DataFrame):
                return result.memory_usage(deep=True).sum() / (1024 * 1024)
            return None
        except (AttributeError, TypeError) as e:
            # 某些数据类型可能没有所需的属性或方法
            self.logger.debug(f"Could not calculate output size: {e}")
            return None
        except Exception as e:
            # 其他未预期的错误
            self.logger.warning(f"Unexpected error calculating output size: {e}")
            return None

    def _execute_plugin_compute(
        self,
        plugin: Plugin,
        name: str,
        run_id: str,
        input_size_mb: Optional[float],
        kwargs: dict
    ) -> Any:
        """执行插件计算核心逻辑

        统一处理：
        - 统计收集开始
        - 插件计算调用（带 profiler）
        - 错误处理（错误钩子、严重程度判断、上下文收集）
        - 清理钩子

        Args:
            plugin: 插件实例
            name: 插件名称（provides）
            run_id: 运行标识符
            input_size_mb: 输入数据大小（MB）
            kwargs: 传递给插件的参数

        Returns:
            插件计算结果

        Raises:
            RuntimeError: 当插件执行失败时
        """
        # Start stats collection
        if self.stats_collector and self.stats_collector.is_enabled():
            self.stats_collector.start_execution(name, run_id, input_size_mb=input_size_mb)

        try:
            # Call plugin compute with explicit run_id
            with self.profiler.timeit(f"plugin.{name}.compute"):
                result = plugin.compute(self, run_id, **kwargs)
            return result
        except Exception as e:
            # Record error in stats
            if self.stats_collector and self.stats_collector.is_enabled():
                self.stats_collector.end_execution(name, success=False, cache_hit=False, error=e)

            # Error handling hook
            plugin.on_error(self, e)

            # 检查错误严重程度
            severity = getattr(e, 'severity', ErrorSeverity.FATAL)
            recoverable = getattr(e, 'recoverable', False)

            # 收集错误上下文
            error_context = self._error_manager.collect_context(
                plugin, run_id,
                get_config_fn=self.get_config,
                get_data_fn=self._get_data_from_memory
            )

            # 根据严重程度处理
            if severity == ErrorSeverity.FATAL:
                # 致命错误：记录并抛出
                self._error_manager.log_error(
                    name, e, run_id, plugin, error_context,
                    get_config_fn=self.get_config
                )
                raise RuntimeError(f"Plugin '{name}' failed: {str(e)}") from e
            elif severity == ErrorSeverity.RECOVERABLE and recoverable:
                # 可恢复错误：记录警告，尝试降级处理
                self.logger.warning(f"Plugin '{name}' failed but recoverable: {e}")
                # 可以在这里添加降级逻辑
                raise RuntimeError(f"Plugin '{name}' failed: {str(e)}") from e
            else:
                # 默认处理
                self._error_manager.log_error(
                    name, e, run_id, plugin, error_context,
                    get_config_fn=self.get_config
                )
                raise RuntimeError(f"Plugin '{name}' failed: {str(e)}") from e
        finally:
            # Cleanup hook
            try:
                plugin.cleanup(self)
            except Exception as cleanup_error:
                # 记录清理错误，但不掩盖原始错误
                self.logger.warning(
                    f"Plugin '{name}' cleanup failed: {cleanup_error}",
                    exc_info=True
                )

    def _save_plugin_result(
        self,
        plugin: Plugin,
        name: str,
        run_id: str,
        result: Any,
        key: str,
        lineage: Dict[str, Any],
        is_generator: bool,
        target_dtype: Optional[np.dtype]
    ) -> Any:
        """保存插件结果到存储

        根据结果类型和插件配置决定保存策略：
        - DataFrame: 保存为 Parquet
        - List[ndarray]: 多通道数据，保存为 {key}_ch{i}
        - Generator: 包装为保存流
        - ndarray: 保存为 memmap

        Args:
            plugin: 插件实例
            name: 插件名称
            run_id: 运行标识符
            result: 插件计算结果
            key: 存储键
            lineage: 血缘信息
            is_generator: 是否为生成器
            target_dtype: 目标 dtype

        Returns:
            可能包装后的结果
        """
        if isinstance(result, pd.DataFrame):
            # Save DataFrame as Parquet
            self.storage.save_dataframe(key, result, run_id)
            self.storage.save_metadata(key, {"lineage": lineage, "type": "dataframe"}, run_id)
            self._set_data(run_id, name, result)
        elif isinstance(result, list) and all(isinstance(x, np.ndarray) for x in result):
            # Save list of arrays (e.g. per-channel data)
            for i, arr in enumerate(result):
                ch_key = f"{key}_ch{i}"
                self.storage.save_memmap(ch_key, arr, extra_metadata={"lineage": lineage}, run_id=run_id)
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
                    key, [result], target_dtype, extra_metadata={"lineage": lineage}, run_id=run_id
                )
                data = self.storage.load_memmap(key, run_id)
                self._set_data(run_id, name, data)
                result = data  # Return loaded data
        else:
            # Fallback: just set in memory
            self._set_data(run_id, name, result)

        return result

    def _postprocess_plugin_result(
        self,
        plugin: Plugin,
        name: str,
        run_id: str,
        result: Any,
        key: str,
        data_name: str,
        tracker: Optional[Any],
        bar_name: Optional[str]
    ) -> None:
        """后处理插件结果

        完整的结果后处理流程：
        1. 获取血缘信息
        2. 验证输出契约
        3. 转换 dtype
        4. 保存结果（根据 save_when 策略）
        5. 计算输出大小
        6. 记录统计
        7. 更新进度条

        Args:
            plugin: 插件实例
            name: 插件名称
            run_id: 运行标识符
            result: 插件计算结果
            key: 存储键
            data_name: 目标数据名称
            tracker: 进度追踪器
            bar_name: 进度条名称
        """
        # Get lineage
        lineage = self.get_lineage(name)

        # Validate output contract and convert dtype
        result, effective_output_kind = self._validation_manager.validate_output_contract(plugin, result)
        is_generator = effective_output_kind == "stream"

        # Convert to target dtype if needed
        target_dtype = plugin.output_dtype
        if not is_generator:
            result = self._validation_manager.convert_to_dtype(
                result, target_dtype, name, is_generator=False
            )

        # Handle saving
        if plugin.save_when == "always" or (plugin.save_when == "target" and name == data_name):
            with self.profiler.timeit("context.save_cache"):
                result = self._save_plugin_result(
                    plugin, name, run_id, result, key, lineage, is_generator, target_dtype
                )
        else:
            self._set_data(run_id, name, result)

        # Calculate output size for stats (detailed mode)
        output_size_mb = self._calculate_output_size(result)

        # Record successful execution in stats
        if self.stats_collector and self.stats_collector.is_enabled():
            self.stats_collector.end_execution(
                name,
                success=True,
                cache_hit=False,
                output_size_mb=output_size_mb
            )

        # Update progress bar
        if tracker and bar_name:
            tracker.update(bar_name, n=1)

    def _execute_single_plugin(
        self,
        name: str,
        run_id: str,
        data_name: str,
        kwargs: dict,
        tracker: Optional[Any],
        bar_name: Optional[str]
    ) -> None:
        """执行单个插件的完整流程

        协调单个插件的完整执行，包括：
        1. 检查缓存
        2. 获取插件
        3. 打印进度
        4. 验证（配置和输入 dtype）
        5. 计算输入大小
        6. 侧作用隔离
        7. 执行插件计算
        8. 后处理结果

        Args:
            name: 插件名称（provides）
            run_id: 运行标识符
            data_name: 目标数据名称
            kwargs: 传递给插件的参数
            tracker: 进度追踪器
            bar_name: 进度条名称

        Raises:
            RuntimeError: 当插件不存在或执行失败时
        """
        # Check cache (memory + disk)
        key = self.key_for(run_id, name)
        data, cache_hit = self._cache_manager.check_cache(run_id, name, key)

        if cache_hit:
            # Update progress bar (cache hit)
            if tracker and bar_name:
                tracker.update(bar_name, n=1)
            return

        if name not in self._plugins:
            raise RuntimeError(f"Dependency '{name}' is missing and no plugin provides it.")

        plugin = self._plugins[name]

        # Print current running plugin
        if self.config.get("show_progress", True):
            print(f"[+] Running plugin: {name} (run_id: {run_id})")

        # Validate plugin config and input dtypes
        self._validation_manager.validate_plugin_config(plugin)
        self._validation_manager.validate_input_dtypes(plugin, run_id)

        # Calculate input size for stats (detailed mode)
        input_size_mb = self._calculate_input_size(plugin, run_id)

        # Side-effect isolation
        kwargs = self._prepare_side_effect_isolation(plugin, run_id, kwargs)

        # Execute plugin compute (with error handling and cleanup)
        result = self._execute_plugin_compute(plugin, name, run_id, input_size_mb, kwargs)

        # Postprocess result (validate, convert, save, stats, progress)
        self._postprocess_plugin_result(
            plugin, name, run_id, result, key, data_name, tracker, bar_name
        )

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
        bin_path, _meta_path, lock_path = self.storage._get_paths(key)
        tmp_bin_path = bin_path + ".tmp"

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
                    except (PermissionError, OSError) as cleanup_err:
                        self.logger.warning(
                            f"Failed to remove temporary file {tmp_bin_path} after error: {cleanup_err}"
                        )
                    except Exception as cleanup_err:
                        self.logger.error(
                            f"Unexpected error removing temp file {tmp_bin_path}: {cleanup_err}",
                            exc_info=True
                        )
                raise e
            finally:
                self.storage._release_lock(lock_fd, lock_path)
                if os.path.exists(tmp_bin_path):
                    try:
                        os.remove(tmp_bin_path)
                    except (PermissionError, OSError) as cleanup_err:
                        self.logger.debug(
                            f"Failed to remove lingering temp file {tmp_bin_path}: {cleanup_err}"
                        )
                    except Exception as cleanup_err:
                        self.logger.warning(
                            f"Unexpected error removing temp file {tmp_bin_path}: {cleanup_err}"
                        )

        return wrapper()

    def list_provided_data(self) -> List[str]:
        """List all data types provided by registered plugins."""
        return list(self._plugins.keys())

    def get_plugin(self, plugin_name: str) -> Plugin:
        """
        获取已注册的插件对象

        返回插件对象，可以直接访问和修改其属性。

        Args:
            plugin_name: 插件名称（provides 属性）

        Returns:
            Plugin: 插件对象

        Raises:
            KeyError: 当插件未注册时

        Examples:
            >>> ctx = Context()
            >>> ctx.register(WaveformsPlugin())
            >>>
            >>> # 获取插件并修改属性
            >>> plugin = ctx.get_plugin('waveforms')
            >>> plugin.save_when = 'always'
            >>> plugin.timeout = 300
            >>>
            >>> # 链式调用
            >>> ctx.get_plugin('st_waveforms').save_when = 'never'
            >>>
            >>> # 查看插件配置
            >>> print(ctx.get_plugin('waveforms').save_when)
            >>> print(ctx.get_plugin('waveforms').options)
        """
        if plugin_name not in self._plugins:
            available = ', '.join(self._plugins.keys())
            raise KeyError(
                f"Plugin '{plugin_name}' is not registered. "
                f"Available plugins: {available}"
            )
        return self._plugins[plugin_name]

    @property
    def profiling_summary(self) -> str:
        """Return a summary of the profiling data."""
        return self.profiler.summary()

    def get_performance_report(self, plugin_name: Optional[str] = None, format: str = 'text') -> Any:
        """
        获取插件性能统计报告

        Args:
            plugin_name: 插件名称,None返回所有插件的统计
            format: 报告格式 ('text' 或 'dict')

        Returns:
            性能报告(文本或字典格式)

        Example:
            >>> ctx = Context(enable_stats=True, stats_mode='detailed')
            >>> # ... 执行一些插件 ...
            >>> print(ctx.get_performance_report())
            >>> # 或获取特定插件的统计
            >>> stats = ctx.get_performance_report(plugin_name='my_plugin', format='dict')
        """
        if not self.stats_collector or not self.stats_collector.is_enabled():
            return "Performance statistics are disabled. Enable with enable_stats=True"

        if plugin_name:
            stats = self.stats_collector.get_statistics(plugin_name)
            if format == 'dict':
                return stats
            else:
                # Generate text report for single plugin
                if not stats or plugin_name not in stats:
                    return f"No statistics available for plugin '{plugin_name}'"

                s = stats[plugin_name]
                lines = [
                    f"Performance Report for '{plugin_name}':",
                    f"  Total calls: {s.total_calls}",
                    f"  Cache hit rate: {s.cache_hit_rate():.1%} ({s.cache_hits}/{s.total_calls})",
                    f"  Success rate: {s.success_rate():.1%}",
                    f"  Time: mean={s.mean_time:.3f}s, min={s.min_time:.3f}s, max={s.max_time:.3f}s",
                ]
                if self.stats_collector.mode == 'detailed':
                    lines.append(f"  Memory: peak={s.peak_memory_mb:.2f}MB, avg={s.avg_memory_mb:.2f}MB")
                if s.recent_errors:
                    lines.append(f"  Recent errors: {len(s.recent_errors)}")
                return "\n".join(lines)
        else:
            return self.stats_collector.generate_report(format=format)

    def analyze_dependencies(
        self,
        target_name: str,
        include_performance: bool = True,
        run_id: Optional[str] = None
    ):
        """
        分析插件依赖关系，识别关键路径、并行机会和性能瓶颈

        Args:
            target_name: 目标数据名称
            include_performance: 是否包含性能数据分析（需要enable_stats=True）
            run_id: 可选的run_id，用于获取特定运行的性能数据（暂未使用，为未来扩展预留）

        Returns:
            DependencyAnalysisResult: 分析结果对象

        Example:
            >>> ctx = Context(enable_stats=True)
            >>> # ... 注册插件并执行一些操作 ...
            >>> analysis = ctx.analyze_dependencies('paired_events')
            >>> print(analysis.summary())
            >>> analysis.to_markdown('report.md')  # 导出为 Markdown
            >>> data = analysis.to_dict()          # 导出为字典（可保存为 JSON）

            # 可视化增强
            >>> from waveform_analysis.utils.visualization import plot_lineage_labview
            >>> plot_lineage_labview(
            ...     ctx.get_lineage('paired_events'),
            ...     'paired_events',
            ...     context=ctx,
            ...     analysis_result=analysis,
            ...     highlight_critical_path=True,
            ...     highlight_bottlenecks=True
            ... )
        """
        from waveform_analysis.core.data.dependency_analysis import DependencyAnalyzer

        analyzer = DependencyAnalyzer(self)
        return analyzer.analyze(
            target_name=target_name,
            include_performance=include_performance,
            run_id=run_id
        )

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
            try:
                lineage["dtype"] = np.dtype(plugin.output_dtype).descr
            except (TypeError, ValueError):
                # If dtype is not a valid numpy dtype (e.g., "List[str]"), store as string
                lineage["dtype"] = str(plugin.output_dtype)

        # Cache the lineage (only for top-level calls)
        if len(_visited) == 1:  # Top-level call
            self._lineage_cache[data_name] = lineage

        return lineage

    def list_plugin_configs(
        self,
        plugin_name: Optional[str] = None,
        show_current_values: bool = True,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        列出所有插件的配置选项

        显示每个插件可用的配置选项，包括：
        - 选项名称
        - 默认值
        - 类型
        - 帮助文本
        - 当前配置值（如果已设置）

        Args:
            plugin_name: 可选，指定插件名称以只显示该插件的配置
            show_current_values: 是否显示当前配置值
            verbose: 是否显示详细信息（类型、帮助文本等）

        Returns:
            插件配置信息字典

        Examples:
            >>> ctx = Context()
            >>> ctx.register(RawFilesPlugin(), WaveformsPlugin())
            >>>
            >>> # 列出所有插件的配置选项
            >>> ctx.list_plugin_configs()
            >>>
            >>> # 只列出特定插件的配置
            >>> ctx.list_plugin_configs(plugin_name='waveforms')
            >>>
            >>> # 获取配置字典而不打印
            >>> config_info = ctx.list_plugin_configs(verbose=False)
        """
        result = {}

        # 确定要显示的插件列表
        if plugin_name is not None:
            if plugin_name not in self._plugins:
                print(f"❌ 插件 '{plugin_name}' 未注册")
                print(f"已注册的插件: {', '.join(self._plugins.keys())}")
                return {}
            plugins_to_show = {plugin_name: self._plugins[plugin_name]}
        else:
            plugins_to_show = self._plugins

        if not plugins_to_show:
            print("⚠️  没有已注册的插件")
            return {}

        # 收集每个插件的配置信息
        for name, plugin in plugins_to_show.items():
            plugin_info = {
                'class': plugin.__class__.__name__,
                'description': getattr(plugin, 'description', ''),
                'version': getattr(plugin, 'version', '0.0.0'),
                'options': {}
            }

            for opt_name, option in plugin.options.items():
                opt_info = {
                    'default': option.default,
                    'type': option.type.__name__ if hasattr(option.type, '__name__') else str(option.type) if option.type else 'Any',
                    'help': option.help,
                    'track': option.track,
                }

                # 获取当前配置值
                if show_current_values:
                    try:
                        current_value = self._resolve_config_value(plugin, opt_name)
                        opt_info['current_value'] = current_value
                        opt_info['is_default'] = (current_value == option.default)
                    except KeyError:
                        opt_info['current_value'] = None
                        opt_info['is_default'] = True

                plugin_info['options'][opt_name] = opt_info

            result[name] = plugin_info

        # 打印格式化输出
        if verbose:
            # 统计信息
            total_options = sum(len(info['options']) for info in result.values())
            modified_count = 0
            if show_current_values:
                for info in result.values():
                    for opt_info in info['options'].values():
                        if not opt_info.get('is_default', True):
                            modified_count += 1

            # 标题
            if plugin_name is not None:
                print(f"\n╔{'═'*78}╗")
                print(f"║ 插件配置详情: {plugin_name:<60} ║")
                print(f"╚{'═'*78}╝")
            else:
                print(f"\n╔{'═'*78}╗")
                print(f"║ 所有插件配置概览{' '*60}║")
                print(f"║ • 已注册插件: {len(plugins_to_show):<3}  • 配置选项总数: {total_options:<4}", end="")
                if show_current_values and modified_count > 0:
                    print(f" • 已修改: {modified_count:<3}        ║")
                else:
                    print(f"{' '*17}║")
                print(f"╚{'═'*78}╝")

            for idx, (name, info) in enumerate(result.items(), 1):
                # 插件标题
                print(f"\n┌{'─'*78}┐")
                print(f"│ {idx}. 📦 {name:<71}│")
                print(f"├{'─'*78}┤")

                # 基本信息
                print(f"│   类名:   {info['class']:<64}│")
                if info['version'] and info['version'] != '0.0.0':
                    print(f"│   版本:   {info['version']:<64}│")
                if info['description']:
                    # 处理长描述，自动换行
                    desc = info['description']
                    desc_width = 64
                    if len(desc) <= desc_width:
                        print(f"│   描述:   {desc:<{desc_width}}│")
                    else:
                        # 分行显示
                        words = desc.split()
                        lines = []
                        current_line = ""
                        for word in words:
                            if len(current_line) + len(word) + 1 <= desc_width:
                                current_line += (word + " ")
                            else:
                                lines.append(current_line.rstrip())
                                current_line = word + " "
                        if current_line:
                            lines.append(current_line.rstrip())

                        print(f"│   描述:   {lines[0]:<{desc_width}}│")
                        for line in lines[1:]:
                            print(f"│           {line:<{desc_width}}│")

                if not info['options']:
                    print(f"│{' '*78}│")
                    print(f"│   ℹ️  此插件无可配置选项{' '*47}│")
                else:
                    # 配置选项
                    print(f"├{'─'*78}┤")
                    print(f"│   ⚙️  配置选项 ({len(info['options'])} 个){' '*(59-len(str(len(info['options']))))}│")
                    print(f"├{'─'*78}┤")

                    for opt_idx, (opt_name, opt_info) in enumerate(info['options'].items(), 1):
                        # 选项名称
                        status_icon = "✓" if opt_info.get('is_default', True) else "⚙️"
                        print(f"│{' '*78}│")
                        print(f"│   {opt_idx}. {status_icon} {opt_name:<67}│")

                        # 类型和默认值
                        type_str = f"[{opt_info['type']}]"
                        default_str = repr(opt_info['default']) if opt_info['default'] is not None else 'None'
                        if len(default_str) > 40:
                            default_str = default_str[:37] + '...'
                        print(f"│      类型: {type_str:<35} 默认值: {default_str:<26}│")

                        # 当前值
                        if show_current_values and 'current_value' in opt_info:
                            current_str = repr(opt_info['current_value']) if opt_info['current_value'] is not None else 'None'
                            if len(current_str) > 50:
                                current_str = current_str[:47] + '...'
                            if opt_info['is_default']:
                                print(f"│      当前值: {current_str:<40} (使用默认){' '*16}│")
                            else:
                                print(f"│      当前值: {current_str:<40} (已自定义) 🔧{' '*13}│")

                        # 帮助文本
                        if opt_info['help']:
                            help_text = opt_info['help']
                            help_width = 66
                            if len(help_text) <= help_width:
                                print(f"│      说明: {help_text:<{help_width}}│")
                            else:
                                # 自动换行
                                words = help_text.split()
                                lines = []
                                current_line = ""
                                for word in words:
                                    if len(current_line) + len(word) + 1 <= help_width:
                                        current_line += (word + " ")
                                    else:
                                        lines.append(current_line.rstrip())
                                        current_line = word + " "
                                if current_line:
                                    lines.append(current_line.rstrip())

                                print(f"│      说明: {lines[0]:<{help_width}}│")
                                for line in lines[1:]:
                                    print(f"│            {line:<{help_width}}│")

                        # 特殊标记
                        if not opt_info['track']:
                            print(f"│      ⚠️  此选项不追踪血缘{' '*50}│")

                print(f"└{'─'*78}┘")

            # 底部提示
            print(f"\n╔{'═'*78}╗")
            print(f"║ 💡 使用提示{' '*65}║")
            print(f"╠{'═'*78}╣")
            print(f"║  • 设置全局配置:{' '*61}║")
            print(f"║    ctx.set_config({{'option_name': value}}){' '*39}║")
            print(f"║{' '*78}║")
            print(f"║  • 设置插件特定配置:{' '*57}║")
            print(f"║    ctx.set_config({{'option_name': value}}, plugin_name='plugin_name'){' '*9}║")
            print(f"║{' '*78}║")
            print(f"║  • 查看当前配置值:{' '*59}║")
            print(f"║    ctx.show_config('plugin_name'){' '*43}║")
            print(f"║{' '*78}║")
            print(f"║  • 查看特定插件配置:{' '*57}║")
            print(f"║    ctx.list_plugin_configs(plugin_name='plugin_name'){' '*23}║")
            print(f"╚{'═'*78}╝\n")

        return result

    def show_config(self, data_name: Optional[str] = None, show_usage: bool = True):
        """
        显示当前配置，并标识每个配置项对应的插件

        Args:
            data_name: 可选，指定插件名称以只显示该插件的配置
            show_usage: 是否显示配置项被哪些插件使用（仅在显示全局配置时有效）

        Examples:
            >>> # 显示全局配置，包含配置项使用情况
            >>> ctx.show_config()

            >>> # 显示特定插件的配置
            >>> ctx.show_config('waveforms')

            >>> # 显示全局配置，但不显示使用情况
            >>> ctx.show_config(show_usage=False)
        """
        if data_name and data_name in self._plugins:
            # 显示特定插件的配置
            self._show_plugin_config(data_name)
        else:
            # 显示全局配置
            self._show_global_config(show_usage)

    def _show_plugin_config(self, plugin_name: str):
        """显示特定插件的配置（详细版）"""
        plugin = self._plugins[plugin_name]

        # 获取插件的实际配置值
        cfg = {}
        for key in plugin.config_keys:
            try:
                cfg[key] = self.get_config(plugin, key)
            except (KeyError, ValueError) as e:
                cfg[key] = f"<Error: {e}>"

        # 标题
        print(f"\n╔{'═'*78}╗")
        print(f"║ 插件配置: {plugin_name:<64} ║")
        print(f"╚{'═'*78}╝")

        # 插件基本信息
        print(f"\n┌{'─'*78}┐")
        print(f"│ 插件信息{' '*68}│")
        print(f"├{'─'*78}┤")
        print(f"│   类名:   {plugin.__class__.__name__:<64}│")
        print(f"│   版本:   {getattr(plugin, 'version', '0.0.0'):<64}│")

        desc = getattr(plugin, "description", "")
        if desc:
            # 处理长描述
            desc_width = 64
            if len(desc) <= desc_width:
                print(f"│   描述:   {desc:<{desc_width}}│")
            else:
                words = desc.split()
                lines = []
                current_line = ""
                for word in words:
                    if len(current_line) + len(word) + 1 <= desc_width:
                        current_line += (word + " ")
                    else:
                        lines.append(current_line.rstrip())
                        current_line = word + " "
                if current_line:
                    lines.append(current_line.rstrip())

                print(f"│   描述:   {lines[0]:<{desc_width}}│")
                for line in lines[1:]:
                    print(f"│           {line:<{desc_width}}│")
        print(f"└{'─'*78}┘")

        # 配置值
        if not cfg:
            print(f"\n  ℹ️  此插件无配置项")
        else:
            print(f"\n┌{'─'*78}┐")
            print(f"│ 配置项 ({len(cfg)} 个){' '*64}│")
            print(f"├{'─'*78}┤")

            for idx, (key, value) in enumerate(cfg.items(), 1):
                # 获取选项信息
                option = plugin.options.get(key)
                default_value = option.default if option else None
                is_default = (value == default_value)

                # 状态图标
                status_icon = "✓" if is_default else "⚙️"

                print(f"│{' '*78}│")
                print(f"│   {idx}. {status_icon} {key:<67}│")

                # 值显示
                value_str = repr(value) if value is not None else 'None'
                if len(value_str) > 60:
                    value_str = value_str[:57] + '...'

                if is_default:
                    print(f"│      值: {value_str:<40} (默认值){' '*20}│")
                else:
                    print(f"│      值: {value_str:<40} (已自定义) 🔧{' '*17}│")

                # 类型信息
                if option:
                    type_str = option.type.__name__ if hasattr(option.type, '__name__') else str(option.type) if option.type else 'Any'
                    print(f"│      类型: [{type_str}]{' '*63}│"[:78] + '│')

                    if option.help:
                        help_text = option.help
                        help_width = 66
                        if len(help_text) <= help_width:
                            print(f"│      说明: {help_text:<{help_width}}│")
                        else:
                            words = help_text.split()
                            lines = []
                            current_line = ""
                            for word in words:
                                if len(current_line) + len(word) + 1 <= help_width:
                                    current_line += (word + " ")
                                else:
                                    lines.append(current_line.rstrip())
                                    current_line = word + " "
                            if current_line:
                                lines.append(current_line.rstrip())

                            print(f"│      说明: {lines[0]:<{help_width}}│")
                            for line in lines[1:]:
                                print(f"│            {line:<{help_width}}│")

            print(f"└{'─'*78}┘")

        print()  # 空行

    def _show_global_config(self, show_usage: bool = True):
        """显示全局配置（增强版）"""
        # 分析配置项使用情况
        config_usage = {}  # config_key -> [plugin_names]
        plugin_specific_configs = {}  # plugin_name -> {config_key: value}
        global_configs = {}  # 纯全局配置

        # 遍历所有插件，收集配置使用情况
        for plugin_name, plugin in self._plugins.items():
            for option_name in plugin.config_keys:
                # 检查是否是插件特定配置
                if plugin_name in self.config and isinstance(self.config[plugin_name], dict):
                    if option_name in self.config[plugin_name]:
                        # 插件特定配置（嵌套字典）
                        if plugin_name not in plugin_specific_configs:
                            plugin_specific_configs[plugin_name] = {}
                        plugin_specific_configs[plugin_name][option_name] = self.config[plugin_name][option_name]
                        continue

                # 检查点分隔配置
                dotted_key = f"{plugin_name}.{option_name}"
                if dotted_key in self.config:
                    # 插件特定配置（点分隔）
                    if plugin_name not in plugin_specific_configs:
                        plugin_specific_configs[plugin_name] = {}
                    plugin_specific_configs[plugin_name][option_name] = self.config[dotted_key]
                    continue

                # 全局配置
                if option_name in self.config:
                    if option_name not in config_usage:
                        config_usage[option_name] = []
                        global_configs[option_name] = self.config[option_name]
                    config_usage[option_name].append(plugin_name)

        # 收集未被任何插件使用的配置项
        unused_configs = {}
        for key, value in self.config.items():
            # 跳过插件特定配置（嵌套字典）
            if isinstance(value, dict) and key in self._plugins:
                continue
            # 跳过点分隔配置
            if '.' in key:
                continue
            # 如果不在 config_usage 中，说明未被使用
            if key not in config_usage:
                unused_configs[key] = value

        # 统计信息
        total_configs = len(global_configs) + len(unused_configs) + sum(len(v) for v in plugin_specific_configs.values())

        # 标题
        print(f"\n╔{'═'*78}╗")
        print(f"║ 全局配置概览{' '*64}║")
        print(f"║ • 全局配置项: {len(global_configs):<3}  • 插件特定配置: {len(plugin_specific_configs):<3}  • 未使用配置: {len(unused_configs):<3}    ║")
        print(f"╚{'═'*78}╝")

        # 1. 显示全局配置（被插件使用的）
        if global_configs:
            print(f"\n┌{'─'*78}┐")
            print(f"│ 全局配置项 ({len(global_configs)} 个){' '*59}│")
            print(f"├{'─'*78}┤")

            for idx, (key, value) in enumerate(global_configs.items(), 1):
                value_str = repr(value) if value is not None else 'None'
                if len(value_str) > 50:
                    value_str = value_str[:47] + '...'

                print(f"│{' '*78}│")
                print(f"│   {idx}. {key:<71}│")
                print(f"│      值: {value_str:<67}│")

                if show_usage and key in config_usage:
                    plugins_using = config_usage[key]
                    plugins_str = ', '.join(plugins_using)

                    if len(plugins_str) <= 60:
                        print(f"│      使用插件: {plugins_str:<61}│")
                    else:
                        # 换行显示
                        words = plugins_str.split(', ')
                        lines = []
                        current_line = ""
                        for word in words:
                            test_line = current_line + (', ' if current_line else '') + word
                            if len(test_line) <= 60:
                                current_line = test_line
                            else:
                                if current_line:
                                    lines.append(current_line)
                                current_line = word
                        if current_line:
                            lines.append(current_line)

                        print(f"│      使用插件: {lines[0]:<61}│")
                        for line in lines[1:]:
                            print(f"│                {line:<61}│")

            print(f"└{'─'*78}┘")

        # 2. 显示插件特定配置
        if plugin_specific_configs:
            print(f"\n┌{'─'*78}┐")
            print(f"│ 插件特定配置 ({len(plugin_specific_configs)} 个插件){' '*48}│")
            print(f"├{'─'*78}┤")

            for plugin_idx, (plugin_name, configs) in enumerate(plugin_specific_configs.items(), 1):
                plugin = self._plugins.get(plugin_name)
                print(f"│{' '*78}│")
                print(f"│   {plugin_idx}. 📦 {plugin_name}{' '*65}│"[:78] + '│')

                for config_idx, (key, value) in enumerate(configs.items(), 1):
                    value_str = repr(value) if value is not None else 'None'
                    if len(value_str) > 55:
                        value_str = value_str[:52] + '...'

                    print(f"│      {config_idx}. {key}: {value_str:<60}│"[:78] + '│')

            print(f"└{'─'*78}┘")

        # 3. 显示未使用的配置项
        if unused_configs:
            print(f"\n┌{'─'*78}┐")
            print(f"│ ⚠️  未使用的配置项 ({len(unused_configs)} 个){' '*50}│")
            print(f"├{'─'*78}┤")

            for idx, (key, value) in enumerate(unused_configs.items(), 1):
                value_str = repr(value) if value is not None else 'None'
                if len(value_str) > 55:
                    value_str = value_str[:52] + '...'

                print(f"│{' '*78}│")
                print(f"│   {idx}. {key}: {value_str:<68}│"[:78] + '│')
                print(f"│      💡 此配置项未被任何已注册插件使用{' '*38}│")

            print(f"└{'─'*78}┘")

        # 4. 底部提示
        print(f"\n╔{'═'*78}╗")
        print(f"║ 💡 提示{' '*71}║")
        print(f"╠{'═'*78}╣")
        print(f"║  • 查看特定插件配置:{' '*57}║")
        print(f"║    ctx.show_config('plugin_name'){' '*43}║")
        print(f"║{' '*78}║")
        print(f"║  • 查看所有插件的配置选项:{' '*51}║")
        print(f"║    ctx.list_plugin_configs(){' '*48}║")
        print(f"║{' '*78}║")
        print(f"║  • 设置配置:{' '*65}║")
        print(f"║    ctx.set_config({{'key': value}}){' '*45}║")
        print(f"║    ctx.set_config({{'key': value}}, plugin_name='plugin'){' '*19}║")
        print(f"╚{'═'*78}╝\n")

    def plot_lineage(self, data_name: str, kind: str = "labview", **kwargs):
        """
        Visualize the lineage of a data type.

        Args:
            data_name: Name of the target data.
            kind: Visualization style ('labview', 'mermaid', or 'plotly').
            **kwargs: Additional arguments passed to the visualizer.
        """
        from .foundation.model import build_lineage_graph

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
        elif kind == "plotly":
            return plot_lineage_plotly(model, data_name, context=self, **kwargs)
        else:
            raise ValueError(f"Unsupported visualization kind: {kind}. Supported: 'labview', 'mermaid', 'plotly'")

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
        clear_disk: bool = True,
        verbose: bool = True
    ) -> int:
        """
        清理指定运行和步骤的缓存。
        
        参数:
            run_id: 运行 ID
            data_name: 数据名称（步骤名称），如果为 None 则清理所有步骤
            clear_memory: 是否清理内存缓存
            clear_disk: 是否清理磁盘缓存
            verbose: 是否显示详细的清理信息
        
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
        memory_count = 0
        disk_count = 0
        
        # 确定要清理的数据名称列表
        if data_name is None:
            # 清理所有已注册插件提供的数据
            data_names = list(self._plugins.keys())
            if verbose:
                print(f"[清理缓存] 运行: {run_id}, 清理所有数据类型的缓存 ({len(data_names)} 个)")
        else:
            data_names = [data_name]
            if verbose:
                print(f"[清理缓存] 运行: {run_id}, 数据类型: {data_name}")
        
        for name in data_names:
            # 清理内存缓存
            if clear_memory:
                key = (run_id, name)
                if key in self._results:
                    del self._results[key]
                    memory_count += 1
                    count += 1
                    if verbose:
                        print(f"  ✓ 已清理内存缓存: ({run_id}, {name})")
                    self.logger.debug(f"Cleared memory cache for ({run_id}, {name})")
                elif verbose:
                    print(f"  - 内存缓存不存在: ({run_id}, {name})")
            
            # 清理磁盘缓存
            if clear_disk:
                try:
                    cache_key = self.key_for(run_id, name)
                    deleted = self._delete_disk_cache(cache_key, run_id)
                    disk_count += deleted
                    count += deleted
                    if deleted > 0:
                        if verbose:
                            print(f"  ✓ 已清理磁盘缓存: {cache_key} ({deleted} 个文件)")
                        self.logger.debug(f"Cleared disk cache for ({run_id}, {name})")
                    elif verbose:
                        print(f"  - 磁盘缓存不存在: {cache_key}")
                except Exception as e:
                    if verbose:
                        print(f"  ✗ 清理磁盘缓存失败: ({run_id}, {name}) - {e}")
                    self.logger.warning(f"Failed to clear disk cache for ({run_id}, {name}): {e}")
        
        # 总结信息
        if verbose:
            print(f"[清理完成] 总计: {count} 个缓存项 (内存: {memory_count}, 磁盘: {disk_count})")
            if count == 0:
                print("  ⚠️  没有找到需要清理的缓存")
            else:
                print("  ✓ 缓存清理成功")
        
        return count
    
    def _delete_disk_cache(self, key: str, run_id: Optional[str] = None) -> int:
        """
        删除磁盘缓存（包括多通道数据和 DataFrame）。

        参数:
            key: 缓存键
            run_id: 运行标识符（用于分层存储模式）

        返回:
            删除的缓存项数量
        """
        count = 0

        # 删除主缓存文件
        if self.storage.exists(key, run_id):
            try:
                self.storage.delete(key, run_id)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to delete cache key {key}: {e}")

        # 删除多通道数据（{key}_ch0, {key}_ch1, ...）
        ch_idx = 0
        while True:
            ch_key = f"{key}_ch{ch_idx}"
            if self.storage.exists(ch_key, run_id):
                try:
                    self.storage.delete(ch_key, run_id)
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to delete multi-channel cache {ch_key}: {e}")
                ch_idx += 1
            else:
                break

        # 删除 DataFrame 缓存（{key}.parquet）
        # 检查 storage 是否支持 DataFrame 存储（有 save_dataframe 方法）
        if hasattr(self.storage, 'save_dataframe'):
            # 对于 MemmapStorage，获取正确的 parquet 路径
            if hasattr(self.storage, 'use_run_subdirs') and self.storage.use_run_subdirs and run_id:
                # 新模式：parquet 在 run 的 data 目录下
                parquet_path = os.path.join(
                    self.storage.work_dir, run_id, self.storage.data_subdir, f"{key}.parquet"
                )
            elif hasattr(self.storage, 'base_dir'):
                # 旧模式：parquet 在 base_dir 中
                parquet_path = os.path.join(self.storage.base_dir, f"{key}.parquet")
            elif hasattr(self.storage, 'db_path'):
                # 对于其他存储后端，如果 db_path 存在，可能在同目录下
                base_dir = os.path.dirname(self.storage.db_path)
                parquet_path = os.path.join(base_dir, f"{key}.parquet")
            else:
                parquet_path = None

            if parquet_path and os.path.exists(parquet_path):
                try:
                    os.remove(parquet_path)
                    count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to delete parquet file {parquet_path}: {e}")

        return count

    # ===========================
    # 时间范围查询 (Phase 2.2)
    # ===========================

    def get_data_time_range(
        self,
        run_id: str,
        data_name: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_field: str = 'time',
        endtime_field: Optional[str] = None,
        auto_build_index: bool = True
    ) -> np.ndarray:
        """
        查询数据的时间范围

        Args:
            run_id: 运行ID
            data_name: 数据名称
            start_time: 起始时间(包含)
            end_time: 结束时间(不包含)
            time_field: 时间字段名
            endtime_field: 结束时间字段名('computed'表示计算endtime)
            auto_build_index: 自动构建时间索引

        Returns:
            符合条件的数据子集

        Examples:
            >>> # 查询特定时间范围的波形数据
            >>> data = ctx.get_data_time_range('run_001', 'st_waveforms',
            ...                                 start_time=1000000, end_time=2000000)
            >>>
            >>> # 查询所有数据后特定时间的记录
            >>> data = ctx.get_data_time_range('run_001', 'st_waveforms', start_time=1000000)
        """
        from waveform_analysis.core.data.query import TimeRangeQueryEngine

        # 懒加载查询引擎
        if not hasattr(self, '_time_query_engine'):
            self._time_query_engine = TimeRangeQueryEngine()

        engine = self._time_query_engine

        # 获取完整数据
        data = self.get_data(run_id, data_name)

        if data is None or len(data) == 0:
            return np.array([], dtype=data.dtype if data is not None else np.float64)

        # 如果不是结构化数组,返回完整数据
        if not isinstance(data, np.ndarray) or data.dtype.names is None:
            self.logger.warning(f"Data '{data_name}' is not a structured array, returning full data")
            return data

        # 如果没有时间字段,返回完整数据
        if time_field not in data.dtype.names:
            self.logger.warning(f"Time field '{time_field}' not found in {data_name}, returning full data")
            return data

        # 构建索引(如果需要)
        if auto_build_index and not engine.has_index(run_id, data_name):
            engine.build_index(run_id, data_name, data, time_field, endtime_field)

        # 查询
        if engine.has_index(run_id, data_name):
            indices = engine.query(run_id, data_name, start_time, end_time)
            if indices is not None and len(indices) > 0:
                return data[indices]
            else:
                return np.array([], dtype=data.dtype)
        else:
            # 回退到直接过滤
            self.logger.warning(f"No index for {data_name}, using direct filtering")
            times = data[time_field]

            if start_time is None:
                start_time = times.min()
            if end_time is None:
                end_time = times.max() + 1

            mask = (times >= start_time) & (times < end_time)
            return data[mask]

    def build_time_index(
        self,
        run_id: str,
        data_name: str,
        time_field: str = 'time',
        endtime_field: Optional[str] = None,
        force_rebuild: bool = False
    ):
        """
        为数据构建时间索引

        Args:
            run_id: 运行ID
            data_name: 数据名称
            time_field: 时间字段名
            endtime_field: 结束时间字段名('computed'表示计算endtime)
            force_rebuild: 强制重建索引

        Examples:
            >>> # 预先构建索引以提高查询性能
            >>> ctx.build_time_index('run_001', 'st_waveforms', endtime_field='computed')
        """
        from waveform_analysis.core.data.query import TimeRangeQueryEngine

        # 懒加载查询引擎
        if not hasattr(self, '_time_query_engine'):
            self._time_query_engine = TimeRangeQueryEngine()

        engine = self._time_query_engine

        # 获取数据
        data = self.get_data(run_id, data_name)

        if data is None or len(data) == 0:
            self.logger.warning(f"No data found for {data_name}, cannot build index")
            return

        # 构建索引
        engine.build_index(run_id, data_name, data, time_field, endtime_field, force_rebuild)

    def clear_time_index(self, run_id: Optional[str] = None, data_name: Optional[str] = None):
        """
        清除时间索引

        Args:
            run_id: 运行ID,None则清除所有
            data_name: 数据名称,None则清除指定run_id的所有索引

        Examples:
            >>> # 清除特定数据的索引
            >>> ctx.clear_time_index('run_001', 'st_waveforms')
            >>>
            >>> # 清除特定run的所有索引
            >>> ctx.clear_time_index('run_001')
            >>>
            >>> # 清除所有索引
            >>> ctx.clear_time_index()
        """
        if hasattr(self, '_time_query_engine'):
            self._time_query_engine.clear_index(run_id, data_name)

    def get_time_index_stats(self) -> Dict[str, Any]:
        """
        获取时间索引统计信息

        Returns:
            统计信息字典

        Examples:
            >>> stats = ctx.get_time_index_stats()
            >>> print(f"Total indices: {stats['total_indices']}")
        """
        if hasattr(self, '_time_query_engine'):
            return self._time_query_engine.get_stats()
        return {'total_indices': 0, 'indices': {}}

    def preview_execution(
        self,
        run_id: str,
        data_name: str,
        show_tree: bool = True,
        show_config: bool = True,
        show_cache: bool = True,
        verbose: int = 1,
    ) -> Dict[str, Any]:
        """
        预览数据获取的执行计划（不实际执行计算）

        在调用 get_data() 之前查看将要执行的操作，包括：
        - 执行计划（插件执行顺序）
        - 依赖关系树
        - 配置参数（仅显示非默认值）
        - 缓存状态（哪些数据已缓存，哪些需要计算）

        Args:
            run_id: 运行标识符
            data_name: 要获取的数据名称
            show_tree: 是否显示依赖关系树
            show_config: 是否显示配置参数
            show_cache: 是否显示缓存状态
            verbose: 显示详细程度 (0=简洁, 1=标准, 2=详细)

        Returns:
            包含执行计划详情的字典

        Examples:
            >>> # 基本预览
            >>> ctx.preview_execution('run_001', 'signal_peaks')

            >>> # 详细预览
            >>> ctx.preview_execution('run_001', 'signal_peaks', verbose=2)

            >>> # 仅显示执行计划
            >>> info = ctx.preview_execution('run_001', 'signal_peaks',
            ...                              show_tree=False, show_config=False)
            >>> print(info['execution_plan'])

            >>> # 在实际执行前确认
            >>> ctx.preview_execution('run_001', 'signal_peaks')
            >>> # 确认后再执行
            >>> data = ctx.get_data('run_001', 'signal_peaks')
        """
        # 检查数据名称是否存在
        if data_name not in self._plugins:
            raise ValueError(
                f"数据类型 '{data_name}' 未注册。"
                f"可用数据: {', '.join(self.list_provided_data())}"
            )

        # 1. 解析执行计划
        try:
            execution_plan = self.resolve_dependencies(data_name)
        except Exception as e:
            print(f"✗ 无法解析依赖关系: {e}")
            return {'error': str(e)}

        # 2. 检查缓存状态
        cache_status = {}
        if show_cache:
            for plugin_name in execution_plan:
                # 检查内存缓存
                in_memory = (run_id, plugin_name) in self._results

                # 检查磁盘缓存
                on_disk = False
                if plugin_name in self._plugins:
                    try:
                        key = self.key_for(run_id, plugin_name)
                        on_disk = self.storage.exists(key, run_id)
                    except Exception:
                        pass

                cache_status[plugin_name] = {
                    'in_memory': in_memory,
                    'on_disk': on_disk,
                    'needs_compute': not (in_memory or on_disk)
                }

        # 3. 收集配置信息
        configs = {}
        if show_config:
            for plugin_name in execution_plan:
                if plugin_name in self._plugins:
                    plugin = self._plugins[plugin_name]
                    plugin_config = {}

                    # 只收集非默认值的配置
                    if hasattr(plugin, 'options'):
                        for opt_name, opt_obj in plugin.options.items():
                            value = self.get_config(plugin, opt_name)
                            if value != opt_obj.default:
                                plugin_config[opt_name] = {
                                    'value': value,
                                    'default': opt_obj.default,
                                    'type': opt_obj.type.__name__ if opt_obj.type else 'Any'
                                }

                    if plugin_config:
                        configs[plugin_name] = plugin_config

        # 4. 构建结果字典
        result = {
            'target': data_name,
            'run_id': run_id,
            'execution_plan': execution_plan,
            'cache_status': cache_status,
            'configs': configs,
        }

        # 5. 打印格式化输出
        self._print_preview(
            result,
            show_tree=show_tree,
            show_config=show_config,
            show_cache=show_cache,
            verbose=verbose
        )

        return result

    def _print_preview(
        self,
        info: Dict[str, Any],
        show_tree: bool,
        show_config: bool,
        show_cache: bool,
        verbose: int
    ):
        """打印格式化的预览信息"""
        import textwrap

        # 标题
        print("\n" + "=" * 70)
        print(f"执行计划预览: {info['target']} (run_id: {info['run_id']})")
        print("=" * 70)

        # 1. 执行计划
        print(f"\n{'📋 执行计划' if verbose > 0 else '执行计划'}:")
        print(f"  {'共 ' + str(len(info['execution_plan'])) + ' 个步骤' if verbose > 0 else ''}")

        for i, plugin_name in enumerate(info['execution_plan'], 1):
            # 获取缓存状态标记
            status_mark = ""
            if show_cache and plugin_name in info['cache_status']:
                status = info['cache_status'][plugin_name]
                if status['in_memory']:
                    status_mark = " ✓ [内存]"
                elif status['on_disk']:
                    status_mark = " ✓ [磁盘]"
                else:
                    status_mark = " ⚙️ [需计算]"

            arrow = "  └─→" if i == len(info['execution_plan']) else "  ├─→"
            print(f"{arrow} {i}. {plugin_name}{status_mark}")

        # 2. 依赖关系树
        if show_tree:
            print(f"\n{'🌳 依赖关系树' if verbose > 0 else '依赖关系树'}:")
            self._print_dependency_tree(info['target'], prefix="  ")

        # 3. 配置参数
        if show_config and info['configs']:
            print(f"\n{'⚙️ 自定义配置' if verbose > 0 else '自定义配置'}:")
            for plugin_name, plugin_config in info['configs'].items():
                print(f"  • {plugin_name}:")
                for opt_name, opt_info in plugin_config.items():
                    default_str = f" (默认: {opt_info['default']})" if verbose > 1 else ""
                    print(f"      {opt_name} = {opt_info['value']}{default_str}")
        elif show_config:
            print(f"\n{'⚙️ 自定义配置' if verbose > 0 else '自定义配置'}: 无（使用所有默认值）")

        # 4. 缓存状态汇总
        if show_cache:
            cache_summary = {
                'in_memory': 0,
                'on_disk': 0,
                'needs_compute': 0
            }
            for status in info['cache_status'].values():
                if status['in_memory']:
                    cache_summary['in_memory'] += 1
                elif status['on_disk']:
                    cache_summary['on_disk'] += 1
                else:
                    cache_summary['needs_compute'] += 1

            print(f"\n{'💾 缓存状态汇总' if verbose > 0 else '缓存汇总'}:")
            print(f"  • 内存缓存: {cache_summary['in_memory']} 个")
            print(f"  • 磁盘缓存: {cache_summary['on_disk']} 个")
            print(f"  • 需要计算: {cache_summary['needs_compute']} 个")

        print("\n" + "=" * 70 + "\n")

    def _print_dependency_tree(self, data_name: str, prefix: str = "", is_last: bool = True, visited: Optional[set] = None):
        """递归打印依赖关系树"""
        if visited is None:
            visited = set()

        if data_name in visited:
            print(f"{prefix}{'└─' if is_last else '├─'} {data_name} [循环引用]")
            return

        visited.add(data_name)

        # 打印当前节点
        connector = "└─" if is_last else "├─"
        print(f"{prefix}{connector} {data_name}")

        # 获取依赖
        if data_name not in self._plugins:
            return

        plugin = self._plugins[data_name]
        dependencies = plugin.depends_on if hasattr(plugin, 'depends_on') else []

        if not dependencies:
            return

        # 打印子节点
        extension = "   " if is_last else "│  "
        for i, dep in enumerate(dependencies):
            is_last_dep = (i == len(dependencies) - 1)
            self._print_dependency_tree(dep, prefix + extension, is_last_dep, visited.copy())

    def help(
        self,
        topic: Optional[str] = None,
        search: Optional[str] = None,
        verbose: bool = False
    ) -> str:
        """
        显示帮助信息

        Args:
            topic: 帮助主题 ('quickstart', 'config', 'plugins', 'performance', 'examples')
            search: 搜索关键词（在方法名、插件名、配置项中搜索）
            verbose: 显示详细信息（新手模式）

        Returns:
            帮助文本

        Examples:
            >>> ctx.help()  # 显示快速参考
            >>> ctx.help('quickstart')  # 快速开始指南
            >>> ctx.help('config')  # 配置管理帮助
            >>> ctx.help(search='time_range')  # 搜索相关方法
            >>> ctx.help('quickstart', verbose=True)  # 详细模式
        """
        # 延迟加载 help 系统
        if self._help_system is None:
            from .foundation.help import HelpSystem
            self._help_system = HelpSystem(self)

        result = self._help_system.show(topic, search, verbose)
        print(result)
        return result

    def quickstart(self, template: str = 'basic', **params) -> str:
        """
        生成快速开始代码模板

        Args:
            template: 模板名称 ('basic', 'basic_analysis', 'memory_efficient')
            **params: 模板参数（如 run_id, n_channels）

        Returns:
            可执行的 Python 代码字符串

        Examples:
            >>> code = ctx.quickstart('basic')
            >>> print(code)  # 或保存到文件
            >>>
            >>> # 自定义参数
            >>> code = ctx.quickstart('basic', run_id='run_002', n_channels=4)
            >>>
            >>> # 保存到文件
            >>> with open('my_analysis.py', 'w') as f:
            ...     f.write(ctx.quickstart('basic'))
        """
        from .foundation.quickstart_templates import TEMPLATES

        if template not in TEMPLATES:
            available = ', '.join(TEMPLATES.keys())
            raise ValueError(f"未知模板 '{template}'。可用模板: {available}")

        code = TEMPLATES[template].generate(self, **params)
        print(code)
        return code

    def __repr__(self):
        return f"Context(storage='{self.storage_dir}', plugins={self.list_provided_data()})"
