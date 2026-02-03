# DOC: docs/features/context/DATA_ACCESS.md
# DOC: docs/features/context/CONFIGURATION.md
# DOC: docs/features/context/PLUGIN_MANAGEMENT.md
"""
Context 模块 - 插件系统的核心调度器。

负责管理插件注册、依赖解析、配置分发以及数据缓存的生命周期。
它是整个分析框架的"大脑"，通过 DAG（有向无环图）确保数据按需、有序地计算。
支持多级缓存校验和血缘追踪，是实现高效、可重复分析的基础。
"""

# 1. Standard library imports
import copy
from datetime import datetime
import functools
import hashlib
import importlib
import inspect
import json
import logging
import os
import re
import threading
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Type, Union, cast
import warnings

# 2. Third-party imports
import numpy as np
import pandas as pd

# 3. Local imports (使用相对导入)
from ..utils.visualization.lineage_visualizer import (
    plot_lineage_labview,
    plot_lineage_plotly,
)
from .config import (
    AdapterInfo,
    CompatManager,
    ConfigResolver,
    ConfigSource,
    ConfigValue,
    ResolvedConfig,
    get_adapter_info,
)
from .execution.validation import ValidationManager
from .foundation.error import ErrorManager
from .foundation.exceptions import ErrorSeverity
from .foundation.mixins import CacheMixin, PluginMixin
from .foundation.utils import OneTimeGenerator, Profiler
from .plugins.core.base import Plugin
from .storage.cache_manager import RuntimeCacheManager
from .storage.memmap import MemmapStorage


def _safe_copy_config(config: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return copy.deepcopy(config)
    except Exception:
        return config.copy()


def _apply_memmap_settings(storage: MemmapStorage, spec: Dict[str, Any]) -> None:
    storage.enable_checksum = spec.get("enable_checksum", storage.enable_checksum)
    storage.checksum_algorithm = spec.get("checksum_algorithm", storage.checksum_algorithm)
    storage.verify_on_load = spec.get("verify_on_load", storage.verify_on_load)
    storage.data_subdir = spec.get("data_subdir", storage.data_subdir)
    storage.side_effects_subdir = spec.get("side_effects_subdir", storage.side_effects_subdir)
    compression = spec.get("compression")
    if compression:
        storage._setup_compression(compression, {})


def _import_plugin_class(module_name: str, class_name: str) -> Any:
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def _create_context_from_spec(spec: Dict[str, Any]) -> "Context":
    config = _safe_copy_config(spec.get("config", {}))
    ctx = Context(
        config=config,
        storage_dir=spec.get("storage_dir"),
        external_plugin_dirs=spec.get("plugin_dirs"),
        auto_discover_plugins=False,
        stats_mode=spec.get("stats_mode", "off"),
        stats_log_file=spec.get("stats_log_file"),
    )

    storage_spec = spec.get("storage")
    if storage_spec and isinstance(ctx.storage, MemmapStorage):
        _apply_memmap_settings(ctx.storage, storage_spec)

    for plugin_spec in spec.get("plugins", []):
        plugin_cls = _import_plugin_class(plugin_spec["module"], plugin_spec["class"])
        try:
            plugin = plugin_cls()
        except Exception as exc:
            raise RuntimeError(
                f"Failed to instantiate {plugin_spec['module']}.{plugin_spec['class']} without arguments. "
                "Please provide context_factory for custom plugin initialization."
            ) from exc
        ctx.register(plugin, allow_override=True)

    return ctx


class Context(CacheMixin, PluginMixin):
    """
    The Context orchestrates plugins and manages data storage/caching.
    Inspired by strax, it is the main entry point for data analysis.
    """

    # 保留名称集合：这些名称不能用作数据名，因为它们是 Context 的方法或属性
    _RESERVED_NAMES = frozenset(
        {
            "analyze_dependencies",
            "build_time_index",
            "clear_cache",
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
        }
    )

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        storage_backend: Optional[Any] = None,
        storage_dir: Optional[str] = None,
        external_plugin_dirs: Optional[List[str]] = None,
        auto_discover_plugins: bool = False,
        stats_mode: str = "off",
        stats_log_file: Optional[str] = None,
    ) -> None:
        """
        Initialize Context.

        Args:
            config: 全局配置字典
                    可选配置: config['plugin_backends'] = {'peaks': SQLiteBackend(...), ...}
            storage_dir: (Old:run_name)存储目录 (默认的 memmap 后端), 数据按 run_id 分目录存储。
                        如果为 None，将使用 config['data_root'] 作为存储目录。
            storage_backend: 自定义存储后端（必须实现 StorageBackend 接口）
                    如果为 None，使用默认的 MemmapStorage
            external_plugin_dirs: 插件搜索目录列表
            auto_discover_plugins: 是否自动发现并注册插件
            stats_mode: 统计模式 ('off', 'basic', 'detailed')，'off' 表示禁用统计
            stats_log_file: 统计日志文件路径

        Storage Structure:
            数据按 run_id 分目录存储：storage_dir/{run_id}/_cache/*.bin

        Examples:
            >>> # 使用 data_root 作为存储目录（推荐）
            >>> ctx = Context(config={"data_root": "DAQ"})
            >>> # 缓存将存储在 DAQ/{run_id}/_cache/

            >>> # 显式指定存储目录 (不推荐, 容易和 run_id 混淆)
            >>> ctx = Context(storage_dir="./strax_data")

            >>> # 使用 SQLite 存储
            >>> from waveform_analysis.core.storage.backends import SQLiteBackend
            >>> ctx = Context(storage=SQLiteBackend("./data.db"))

            >>> # 启用详细统计和日志
            >>> ctx = Context(stats_mode='detailed', stats_log_file='./logs/plugins.log')
        """
        CacheMixin.__init__(self)
        PluginMixin.__init__(self)

        self.profiler = Profiler()
        self.config = config or {}

        # 确定存储目录：优先使用显式指定的 storage_dir，否则使用 data_root
        if storage_dir is None:
            storage_dir = self.config.get("data_root", "DAQ")

        self.storage_dir = storage_dir

        # Extensibility: Allow custom storage backend
        if storage_backend is not None:
            # 验证存储后端接口（可选，记录警告）
            self._validate_storage_backend(storage_backend)
            self.storage = storage_backend
        else:
            compression = self.config.get("compression")
            compression_kwargs = self.config.get("compression_kwargs")
            enable_checksum = self.config.get("enable_checksum", False)
            verify_on_load = self.config.get("verify_on_load", False)
            checksum_algorithm = self.config.get("checksum_algorithm", "xxhash64")
            self.storage = MemmapStorage(
                work_dir=storage_dir,
                profiler=self.profiler,
                compression=compression,
                compression_kwargs=compression_kwargs,
                enable_checksum=enable_checksum,
                checksum_algorithm=checksum_algorithm,
                verify_on_load=verify_on_load,
            )

        # Setup logger

        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        # Optional per-plugin storage backends (fallback to self.storage)
        self._plugin_backends: Dict[str, Any] = {}
        plugin_backends = self.config.get("plugin_backends")
        if plugin_backends:
            if isinstance(plugin_backends, dict):
                self._plugin_backends = plugin_backends
                for backend in self._plugin_backends.values():
                    self._validate_storage_backend(backend)
            else:
                self.logger.warning(
                    "config['plugin_backends'] must be a dict of {plugin_name: backend}."
                )

        # Initialize ErrorManager
        self._error_manager = ErrorManager(self.logger)

        # Initialize RuntimeCacheManager
        self._cache_manager = RuntimeCacheManager(self)

        # Initialize ValidationManager
        self._validation_manager = ValidationManager(self)

        # Setup plugin statistics collector
        self.enable_stats = stats_mode != "off"
        self.stats_collector = None
        if self.enable_stats:
            from waveform_analysis.core.plugins.core.stats import PluginStatsCollector

            # Create dedicated collector for this context (not global singleton)
            self.stats_collector = PluginStatsCollector(mode=stats_mode, log_file=stats_log_file)

        # Dedicated storage for results to avoid namespace pollution
        self._results: Dict[tuple, Any] = {}
        # Lineage hash for each cached result (for config change detection)
        self._results_lineage: Dict[tuple, str] = {}  # (run_id, data_name) -> lineage_hash
        # Re-entrancy guard: track (run_id, data_name) currently being computed
        self._in_progress: Dict[tuple, Any] = {}
        self._in_progress_lock = threading.Lock()  # Protect concurrent access
        # Cache of validated configs per plugin signature
        self._resolved_config_cache: Dict[tuple, Dict[str, Any]] = {}

        # Performance optimization caches
        self._execution_plan_cache: Dict[str, List[str]] = {}  # data_name -> execution plan
        self._lineage_cache: Dict[str, Dict[str, Any]] = {}  # data_name -> lineage dict
        self._lineage_hash_cache: Dict[str, str] = {}  # data_name -> lineage hash
        self._key_cache: Dict[tuple, str] = {}  # (run_id, data_name) -> key

        # Plugin discovery
        self.plugin_dirs = external_plugin_dirs or []
        if auto_discover_plugins:
            self.discover_and_register_plugins()

        # Ensure storage directory exists if using default
        if not storage_backend and not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)

        # Epoch management (per-run time reference)
        self._epoch_cache: Dict[str, Any] = {}  # run_id -> EpochInfo

        # Epoch configuration defaults
        self.config.setdefault("auto_extract_epoch", True)
        self.config.setdefault(
            "epoch_extraction_strategy", "auto"
        )  # "auto", "filename", "csv_header", "first_event"
        self.config.setdefault("epoch_filename_patterns", None)  # None = use defaults

        # Initialize ConfigResolver and CompatManager for unified config handling
        self._compat_manager = CompatManager()
        self._config_resolver = ConfigResolver(compat_manager=self._compat_manager)

    def clone(self) -> "Context":
        """
        Create a new Context with the same config and plugin registrations.

        The clone has empty caches/results and is safe for threaded batch execution.
        For process-based parallelism, prefer create_context_factory().
        """
        config = _safe_copy_config(self.config)
        stats_mode = "off"
        stats_log_file = None
        if self.stats_collector is not None:
            stats_mode = getattr(self.stats_collector, "mode", "basic")
            stats_log_file = getattr(self.stats_collector, "log_file", None)

        new_ctx = Context(
            config=config,
            storage_dir=self.storage_dir,
            external_plugin_dirs=list(self.plugin_dirs),
            auto_discover_plugins=False,
            stats_mode=stats_mode if self.enable_stats else "off",
            stats_log_file=stats_log_file,
        )

        if isinstance(self.storage, MemmapStorage) and isinstance(new_ctx.storage, MemmapStorage):
            _apply_memmap_settings(new_ctx.storage, self._build_memmap_storage_spec())
        elif hasattr(self.storage, "clone"):
            try:
                new_ctx.storage = self.storage.clone()
            except Exception as exc:
                self.logger.warning("Failed to clone storage backend, sharing instance: %s", exc)
                new_ctx.storage = self.storage
        else:
            if self.storage is not new_ctx.storage:
                self.logger.warning(
                    "Context.clone is sharing a non-MemmapStorage backend across contexts."
                )
                new_ctx.storage = self.storage

        if self._plugin_backends:
            new_ctx._plugin_backends = self._plugin_backends.copy()

        for plugin in self._plugins.values():
            plugin_copy = None
            if hasattr(plugin, "clone"):
                try:
                    plugin_copy = plugin.clone()
                except Exception:
                    plugin_copy = None
            if plugin_copy is None:
                try:
                    plugin_copy = copy.deepcopy(plugin)
                except Exception:
                    try:
                        plugin_copy = plugin.__class__()
                    except Exception as exc:
                        self.logger.warning(
                            "Failed to clone plugin %s: %s", plugin.__class__.__name__, exc
                        )
                        continue
            new_ctx.register(plugin_copy, allow_override=True)

        return new_ctx

    def _build_memmap_storage_spec(self) -> Dict[str, Any]:
        return {
            "type": "memmap",
            "compression": getattr(self.storage, "compression", None),
            "enable_checksum": getattr(self.storage, "enable_checksum", False),
            "checksum_algorithm": getattr(self.storage, "checksum_algorithm", "xxhash64"),
            "verify_on_load": getattr(self.storage, "verify_on_load", False),
            "data_subdir": getattr(self.storage, "data_subdir", "_cache"),
            "side_effects_subdir": getattr(self.storage, "side_effects_subdir", "side_effects"),
        }

    def _build_context_factory_spec(self) -> Dict[str, Any]:
        if not isinstance(self.storage, MemmapStorage):
            raise ValueError(
                "Auto context factory requires MemmapStorage; provide context_factory instead."
            )

        plugins = []
        for plugin in self._plugins.values():
            module_name = plugin._registered_from_module or plugin.__class__.__module__
            class_name = plugin._registered_class or plugin.__class__.__name__
            if module_name in ("__main__", "__mp_main__"):
                raise ValueError(
                    f"Plugin {class_name} is defined in {module_name}; provide context_factory explicitly."
                )
            plugins.append({"module": module_name, "class": class_name})

        stats_mode = "off"
        stats_log_file = None
        if self.stats_collector is not None:
            stats_mode = getattr(self.stats_collector, "mode", "basic")
            stats_log_file = getattr(self.stats_collector, "log_file", None)

        return {
            "config": _safe_copy_config(self.config),
            "storage_dir": self.storage_dir,
            "plugin_dirs": list(self.plugin_dirs),
            "stats_mode": stats_mode if self.enable_stats else "off",
            "stats_log_file": stats_log_file,
            "storage": self._build_memmap_storage_spec(),
            "plugins": plugins,
        }

    def create_context_factory(self) -> Callable[[], "Context"]:
        """
        Build a picklable context_factory for process-based executors.

        Requires importable plugin classes and MemmapStorage; otherwise provide
        a custom context_factory.
        """
        spec = self._build_context_factory_spec()
        return functools.partial(_create_context_from_spec, spec)

    # ===========================
    # Registers & Config plugins in the  Context. and get data
    # ===========================

    def register(
        self,
        *plugins: Union[Plugin, Type[Plugin], Any],
        allow_override: bool = False,
        require_spec: bool = False,
    ):
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
                - 插件序列：list/tuple/set，内部元素会被展开注册
            allow_override: 如果为 True，允许覆盖已注册的同名插件（基于 `provides` 属性）
                          如果为 False（默认），注册同名插件会抛出 RuntimeError
            require_spec: 如果为 True，要求插件必须提供有效的 spec() 方法或 SPEC 属性
                         如果为 False（默认），spec 校验仅产生警告

        Raises:
            RuntimeError: 当尝试注册已存在的插件且 `allow_override=False` 时
            ValueError: 当插件验证失败时（通过 `plugin.validate()` 方法）
                       或当 `require_spec=True` 且插件缺少有效 spec 时
            TypeError: 当插件依赖版本不兼容时

        Examples:
            >>> from waveform_analysis.core.context import Context
            >>> from waveform_analysis.core.plugins.builtin.cpu import (
            ...     RawFileNamesPlugin, WaveformsPlugin, StWaveformsPlugin
            ... )
            >>>
            >>> ctx = Context(storage_dir="./strax_data")
            >>>
            >>> # 方式1: 注册插件实例
            >>> ctx.register(RawFileNamesPlugin())
            >>>
            >>> # 方式2: 注册插件类（会自动实例化）
            >>> ctx.register(WaveformsPlugin)
            >>>
            >>> # 方式3: 一次注册多个插件
            >>> ctx.register(
            ...     RawFileNamesPlugin(),
            ...     WaveformsPlugin(),
            ...     StWaveformsPlugin()
            ... )
            >>>
            >>> # 方式4: 注册模块中的所有插件
            >>> from waveform_analysis.core.plugins import profiles
            >>> ctx.register(*profiles.cpu_default())
            >>>
            >>> # 方式5: 允许覆盖已注册的插件
            >>> ctx.register(RawFileNamesPlugin(), allow_override=True)
            >>>
            >>> # 方式6: 要求插件必须有 spec（严格模式）
            >>> ctx.register(MyPlugin(), require_spec=True)
            >>>
            >>> # 注册后可以通过数据名称访问
            >>> raw_files = ctx.get_data("run_001", "raw_files")

        Notes:
            - 插件注册时会自动调用 `plugin.validate()` 进行验证
            - 注册插件会清除相关的执行计划缓存，确保依赖关系正确
            - 如果插件类需要参数，请先实例化再传入，不要直接传入类
            - 模块注册会递归查找所有 Plugin 子类，但会跳过 Plugin 基类本身
            - 当 require_spec=True 时，会校验 PluginSpec 的完整性和一致性
        """
        for p in plugins:
            if isinstance(p, (list, tuple, set)):
                for item in p:
                    self.register(item, allow_override=allow_override, require_spec=require_spec)
                continue
            if isinstance(p, type) and issubclass(p, Plugin):
                self.register_plugin_(p(), allow_override=allow_override, require_spec=require_spec)
            elif isinstance(p, Plugin):
                self.register_plugin_(p, allow_override=allow_override, require_spec=require_spec)
            elif hasattr(p, "__path__") or hasattr(p, "__file__"):  # It's a module
                self._register_from_module(
                    p, allow_override=allow_override, require_spec=require_spec
                )
            else:
                # Fallback for other types if needed
                self.register_plugin_(p, allow_override=allow_override, require_spec=require_spec)

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
                self.register_plugin_(plugin_class(), allow_override=allow_override)
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

        自动迁移旧配置名：如果配置中包含已弃用的配置名，会自动替换为新名称并发出警告。

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
        # 迁移旧配置名（自动发出弃用警告）
        from waveform_analysis.core.compat import migrate_config

        config = migrate_config(config, warn=True)

        if plugin_name is not None:
            # 按插件名称设置配置，自动使用命名空间
            if plugin_name not in self._plugins:
                self.logger.warning(
                    f"Plugin '{plugin_name}' is not registered. Config will be set but may not be used by any plugin."
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
        self.clear_performance_caches()  # 配置变了，必须让 lineage/hash/key 失效

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
        return self.get_config_value(plugin, name).value

    def get_config_value(
        self,
        plugin: Plugin,
        name: str,
        adapter_name: Optional[str] = None,
    ) -> ConfigValue:
        """获取插件配置值及其来源信息。

        Args:
            plugin: 目标插件实例
            name: 配置选项名称
            adapter_name: DAQ adapter 名称（可选）

        Returns:
            ConfigValue 实例
        """
        if adapter_name is None:
            adapter_name = self._resolve_adapter_name_for_plugin(plugin)
        return self._config_resolver.resolve_value(
            plugin=plugin,
            name=name,
            config=self.config,
            adapter_name=adapter_name,
        )

    def has_explicit_config(
        self,
        plugin: Plugin,
        name: str,
        adapter_name: Optional[str] = None,
    ) -> bool:
        """检查配置是否显式设置（包含别名输入）。"""
        try:
            cv = self.get_config_value(plugin, name, adapter_name=adapter_name)
        except KeyError:
            return False
        return cv.source == ConfigSource.EXPLICIT

    def _resolve_adapter_name_for_plugin(
        self,
        plugin: Plugin,
        adapter_name: Optional[str] = None,
    ) -> Optional[str]:
        """Resolve adapter name with plugin-specific override."""
        resolved_adapter = (
            adapter_name if adapter_name is not None else self.config.get("daq_adapter")
        )
        if "daq_adapter" not in plugin.options:
            return resolved_adapter
        try:
            cv = self._config_resolver.resolve_value(
                plugin=plugin,
                name="daq_adapter",
                config=self.config,
                adapter_name=None,
            )
        except KeyError:
            return resolved_adapter
        if cv.value is not None:
            return cv.value
        return resolved_adapter

    def get_resolved_config(
        self,
        plugin: Union[Plugin, str],
        adapter_name: Optional[str] = None,
    ) -> ResolvedConfig:
        """获取插件的完整解析配置（带来源追踪）

        使用 ConfigResolver 解析插件的所有配置值，并追踪每个值的来源。
        支持从 DAQ adapter 自动推断配置值（如采样率、时间间隔等）。

        Args:
            plugin: 插件实例或插件名称
            adapter_name: DAQ adapter 名称（可选，用于推断配置值）
                         如果未指定，会尝试从 config['daq_adapter'] 获取

        Returns:
            ResolvedConfig 实例，包含所有配置值及其来源信息

        Examples:
            >>> resolved = ctx.get_resolved_config("waveforms", adapter_name="vx2730")
            >>> print(resolved.get("sampling_rate_hz"))
            500000000.0

            >>> # 查看配置来源
            >>> print(resolved.summary(verbose=True))

            >>> # 获取所有推断的值
            >>> print(resolved.get_inferred_values())
        """
        # 获取插件实例
        if isinstance(plugin, str):
            if plugin not in self._plugins:
                raise KeyError(f"Plugin '{plugin}' is not registered")
            plugin = self._plugins[plugin]

        # 确定 adapter 名称
        if adapter_name is None:
            adapter_name = self._resolve_adapter_name_for_plugin(plugin)

        return self._config_resolver.resolve(
            plugin=plugin,
            config=self.config,
            adapter_name=adapter_name,
        )

    def show_resolved_config(
        self,
        plugin: Union[Plugin, str, None] = None,
        verbose: bool = True,
        adapter_name: Optional[str] = None,
    ) -> None:
        """显示插件的解析配置（带来源信息）

        以友好的格式显示插件配置的解析结果，包括每个配置值的来源。

        Args:
            plugin: 插件实例、插件名称或 None（显示所有插件）
            verbose: 是否显示详细信息（包含来源）
            adapter_name: DAQ adapter 名称（可选）

        Examples:
            >>> # 显示单个插件的配置
            >>> ctx.show_resolved_config("waveforms", verbose=True)

            >>> # 显示所有插件的配置
            >>> ctx.show_resolved_config()
        """
        if adapter_name is None:
            adapter_name = self.config.get("daq_adapter")

        if plugin is None:
            # 显示所有插件
            plugins_to_show = list(self._plugins.values())
        elif isinstance(plugin, str):
            if plugin not in self._plugins:
                print(f"Plugin '{plugin}' is not registered")
                return
            plugins_to_show = [self._plugins[plugin]]
        else:
            plugins_to_show = [plugin]

        for p in plugins_to_show:
            resolved = self.get_resolved_config(p, adapter_name=adapter_name)
            print(resolved.summary(verbose=verbose))
            print()

    def get_adapter_info(self, adapter_name: Optional[str] = None) -> Optional[AdapterInfo]:
        """获取 DAQ adapter 信息

        Args:
            adapter_name: adapter 名称（可选，默认从 config['daq_adapter'] 获取）

        Returns:
            AdapterInfo 实例或 None
        """
        if adapter_name is None:
            adapter_name = self.config.get("daq_adapter")
        if adapter_name is None:
            return None
        return get_adapter_info(adapter_name)

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
            available = ", ".join(self._plugins.keys())
            raise KeyError(
                f"Plugin '{plugin_name}' is not registered. Available plugins: {available}"
            )
        return self._plugins[plugin_name]

    def show_config(
        self,
        data_name: Optional[str] = None,
        show_usage: bool = True,
        show_full_help: bool = False,
        run_name: Optional[str] = None,
    ):
        """
        显示当前配置，并标识每个配置项对应的插件

        Args:
            data_name: 可选，指定插件名称以只显示该插件的配置
            show_usage: 是否显示配置项被哪些插件使用（仅在显示全局配置时有效）
            show_full_help: 是否显示完整 help 文本（默认截断）
            run_name: 可选，显示缓存目录时使用的运行名（仅全局配置视图）

        Examples:
            >>> # 显示全局配置，包含配置项使用情况
            >>> ctx.show_config()

            >>> # 显示特定插件的配置
            >>> ctx.show_config('waveforms')

            >>> # 显示全局配置，但不显示使用情况
            >>> ctx.show_config(show_usage=False)

            >>> # 指定运行名，显示实际缓存目录
            >>> ctx.show_config(run_name='run_001')

            >>> # 自动使用最近一次 get_data(run_id=...) 的 run_id
            >>> ctx.show_config()

        关联说明：
            - 若 data_name 指定为插件名，会直接调用 list_plugin_configs 来展示该插件的“配置项清单”。
            - 若 data_name 未指定，则展示“当前配置汇总”（全局/插件特定/未使用）。
        """
        if data_name and data_name in self._plugins:
            # 显示特定插件的配置
            self._show_plugin_config(data_name, show_full_help=show_full_help)
        else:
            # 显示全局配置
            self._show_global_config(show_usage, show_full_help=show_full_help, run_name=run_name)

    def _register_from_module(
        self, module, allow_override: bool = False, require_spec: bool = False
    ):
        """Helper to register all Plugin classes found in a module."""
        import inspect

        for _name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, Plugin) and obj != Plugin:
                self.register_plugin_(
                    obj(), allow_override=allow_override, require_spec=require_spec
                )

    # ===========================
    # Get Data
    # 1. Cache & Storage backend validation and retrieval
    # 2. Analysis of dependencies --> Execution plan --> Run Plugin
    # ===========================

    def get_data(
        self,
        run_id: str,
        data_name: str,
        show_progress: bool = False,
        progress_desc: Optional[str] = None,
        **kwargs,
    ) -> Any:
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
        # Remember the most recent run_id for display purposes (e.g., show_config()).
        self._last_run_id = run_id

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

        # 3. Resolve plan and compute needed steps (cache-aware)
        plan = self._resolve_execution_plan(run_id, data_name)
        if not plan:
            return self._get_data_from_memory(run_id, data_name)
        needed_set = self._compute_needed_set(run_id, data_name, plan)

        # 4. Execute plan
        return self._run_plugin(
            run_id,
            data_name,
            show_progress=show_progress,
            progress_desc=progress_desc,
            plan=plan,
            needed_set=needed_set,
            **kwargs,
        )

    def list_provided_data(self) -> List[str]:
        """List all data types provided by registered plugins."""
        return list(self._plugins.keys())

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
        verbose: bool = True,
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
                    # Also clean up lineage record
                    if key in self._results_lineage:
                        del self._results_lineage[key]
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
                    deleted = self._delete_disk_cache(cache_key, run_id, data_name=name)
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

    def clear_config_cache(self):
        """Clear cached validated configurations."""
        self._resolved_config_cache.clear()

    def _validate_storage_backend(self, storage: Any) -> None:
        """
        验证存储后端是否实现了必需的接口

        如果后端缺少必需方法，记录警告但不阻止使用。
        """
        required_methods = [
            "exists",
            "save_memmap",
            "load_memmap",
            "save_metadata",
            "get_metadata",
            "delete",
            "list_keys",
            "get_size",
            "save_stream",
            "finalize_save",
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

    def _get_storage_for_data_name(self, data_name: str) -> Any:
        """Return storage backend for a plugin data name (fallback to default)."""
        return self._plugin_backends.get(data_name, self.storage)

    def _storage_supports_run_id(self, storage: Any, method_name: str) -> bool:
        """Check whether a storage method accepts run_id."""
        method = getattr(storage, method_name, None)
        if method is None:
            return False
        try:
            params = inspect.signature(method).parameters
        except (TypeError, ValueError):
            return False
        if "run_id" in params:
            return True
        return any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())

    def _storage_call(
        self,
        storage: Any,
        method_name: str,
        key: str,
        run_id: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Call a storage method with run_id when supported."""
        method = getattr(storage, method_name)
        if run_id is not None and self._storage_supports_run_id(storage, method_name):
            return method(key, *args, run_id=run_id, **kwargs)
        return method(key, *args, **kwargs)

    def _storage_exists(self, storage: Any, key: str, run_id: Optional[str]) -> bool:
        return bool(self._storage_call(storage, "exists", key, run_id))

    def _storage_get_metadata(
        self, storage: Any, key: str, run_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        return self._storage_call(storage, "get_metadata", key, run_id)

    def _storage_load_memmap(
        self, storage: Any, key: str, run_id: Optional[str]
    ) -> Optional[np.ndarray]:
        return self._storage_call(storage, "load_memmap", key, run_id)

    def _storage_load_dataframe(
        self, storage: Any, key: str, run_id: Optional[str]
    ) -> Optional[pd.DataFrame]:
        return self._storage_call(storage, "load_dataframe", key, run_id)

    def _storage_save_memmap(
        self,
        storage: Any,
        key: str,
        data: np.ndarray,
        extra_metadata: Optional[Dict[str, Any]],
        run_id: Optional[str],
    ) -> None:
        self._storage_call(storage, "save_memmap", key, run_id, data, extra_metadata=extra_metadata)

    def _storage_save_metadata(
        self,
        storage: Any,
        key: str,
        metadata: Dict[str, Any],
        run_id: Optional[str],
    ) -> None:
        self._storage_call(storage, "save_metadata", key, run_id, metadata)

    def _storage_save_dataframe(
        self,
        storage: Any,
        key: str,
        data: pd.DataFrame,
        run_id: Optional[str],
    ) -> None:
        self._storage_call(storage, "save_dataframe", key, run_id, data)

    def _storage_delete(self, storage: Any, key: str, run_id: Optional[str]) -> None:
        self._storage_call(storage, "delete", key, run_id)

    def _storage_list_keys(self, storage: Any, run_id: Optional[str]) -> List[str]:
        """List keys from storage, filtering by run_id when needed."""
        method = getattr(storage, "list_keys", None)
        if method is None:
            return []
        try:
            if run_id is not None and self._storage_supports_run_id(storage, "list_keys"):
                return method(run_id=run_id)
            keys = method()
        except Exception:
            return []
        if run_id is None:
            return keys
        prefix = f"{run_id}-"
        return [k for k in keys if k.startswith(prefix)]

    def _list_channel_keys(self, storage: Any, run_id: Optional[str], key: str) -> List[str]:
        """List multi-channel cache keys (key_ch*) for a base key."""
        prefix = f"{key}_ch"
        keys = [k for k in self._storage_list_keys(storage, run_id) if k.startswith(prefix)]
        if keys:

            def _ch_index(k: str) -> float:
                suffix = k[len(prefix) :]
                try:
                    return float(int(suffix))
                except ValueError:
                    return float("inf")

            return sorted(keys, key=_ch_index)

        # Fallback to contiguous scan if list_keys is unavailable.
        keys = []
        ch_idx = 0
        while self._storage_exists(storage, f"{key}_ch{ch_idx}", run_id):
            keys.append(f"{key}_ch{ch_idx}")
            ch_idx += 1
        return keys

    def _resolve_config_value(self, plugin: Plugin, name: str) -> Any:
        """计算插件配置选项的值（统一走 ConfigResolver）。

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
        return self.get_config(plugin, name)

    def _make_config_signature(self, raw_config: Dict[str, Any]) -> str:
        """Generate a stable signature for a plugin's raw config dict."""

        def default(o: Any) -> str:
            if isinstance(o, np.ndarray):
                return o.tobytes().hex()
            return repr(o)

        normalized = {name: raw_config[name] for name in sorted(raw_config)}
        payload = json.dumps(normalized, sort_keys=True, default=default)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _make_resolved_config_signature(self, resolved: ResolvedConfig) -> str:
        """Generate a stable signature for a plugin's resolved config."""
        payload = {"__adapter__": resolved.adapter_name}
        payload.update(resolved.to_dict())
        return self._make_config_signature(payload)

    def _ensure_plugin_config_validated(self, plugin: Plugin) -> Dict[str, Any]:
        """Validate and cache plugin configuration for reuse."""
        resolved = self.get_resolved_config(plugin)
        signature = self._make_resolved_config_signature(resolved)
        cache_key = (plugin.provides, signature)
        if cache_key in self._resolved_config_cache:
            return self._resolved_config_cache[cache_key]

        validated = resolved.to_dict()
        self._resolved_config_cache[cache_key] = validated
        return validated

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

        # Record lineage hash for config change detection
        if name in self._plugins:
            key = self.key_for(run_id, name)  # Contains lineage hash
            self._results_lineage[(run_id, name)] = key

        is_generator = isinstance(value, (Iterator, OneTimeGenerator)) or hasattr(value, "__next__")

        # Safe attribute access: whitelist and conflict check
        # Whitelist: valid python identifier
        if re.match(r"^[a-zA-Z_]\w*$", name):
            # Check if it's a property on the class
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
            # Validate lineage hash (config consistency check)
            if name in self._plugins:
                cached_key = self._results_lineage.get((run_id, name))
                current_key = self.key_for(run_id, name)
                if cached_key != current_key:
                    # Config has changed, invalidate cache
                    self.logger.debug(
                        f"Memory cache invalidated for ({run_id}, {name}): "
                        f"config changed (cached_key={cached_key}, current_key={current_key})"
                    )
                    # Clean up stale cache entries
                    del self._results[(run_id, name)]
                    if (run_id, name) in self._results_lineage:
                        del self._results_lineage[(run_id, name)]
                    return None

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
        storage = self._get_storage_for_data_name(name)
        channel_keys = self._list_channel_keys(storage, run_id, key)
        has_base = self._storage_exists(storage, key, run_id)
        if not has_base and not channel_keys:
            return None

        meta_key = channel_keys[0] if channel_keys else key
        meta = self._storage_get_metadata(storage, meta_key, run_id)
        if meta is None and has_base and meta_key != key:
            meta = self._storage_get_metadata(storage, key, run_id)
        if meta and "lineage" in meta:
            current_lineage = self.get_lineage(name)
            import json

            s1 = json.dumps(meta["lineage"], sort_keys=True, default=str)
            s2 = json.dumps(current_lineage, sort_keys=True, default=str)
            if s1 != s2:
                warnings.warn(f"Lineage mismatch for '{name}' in cache. Recomputing.", UserWarning)
                return None

        # Determine how to load
        meta = meta or {}
        if meta.get("type") == "dataframe":
            data = self._storage_load_dataframe(storage, key, run_id)
        elif channel_keys:
            # Load multi-channel data
            data = [self._storage_load_memmap(storage, ch_key, run_id) for ch_key in channel_keys]
        else:
            data = self._storage_load_memmap(storage, key, run_id)

        if data is not None:
            if self.config.get("show_progress", True):
                print(f"[cache] Loaded '{name}' from disk (run_id: {run_id})")
            self._set_data(run_id, name, data)
        return data

    def _is_disk_cache_valid(self, run_id: str, name: str, key: str) -> bool:
        """Check whether disk cache exists and lineage matches without loading data."""
        storage = self._get_storage_for_data_name(name)
        channel_keys = self._list_channel_keys(storage, run_id, key)
        has_base = self._storage_exists(storage, key, run_id)
        if not has_base and not channel_keys:
            return False
        meta_key = channel_keys[0] if channel_keys else key

        try:
            meta = self._storage_get_metadata(storage, meta_key, run_id)
        except Exception:
            return False

        if meta and "lineage" in meta:
            current_lineage = self.get_lineage(name)
            s1 = json.dumps(meta["lineage"], sort_keys=True, default=str)
            s2 = json.dumps(current_lineage, sort_keys=True, default=str)
            return s1 == s2

        # No lineage metadata: treat as valid (consistent with _load_from_disk_with_check)
        return True

    def _is_cache_hit(self, run_id: str, name: str, load: bool = False) -> bool:
        """Check memory/disk cache status. Optionally loads disk cache into memory."""
        if self._get_data_from_memory(run_id, name) is not None:
            return True

        if name not in self._plugins:
            return False

        key = self.key_for(run_id, name)
        if load:
            _data, cache_hit = self._cache_manager.check_cache(run_id, name, key)
            return cache_hit

        return self._is_disk_cache_valid(run_id, name, key)

    def _compute_needed_set(self, run_id: str, data_name: str, plan: List[str]) -> Set[str]:
        """Compute the set of steps that actually need execution for this run."""
        needed: Set[str] = set()
        visited: Set[str] = set()

        def dfs(name: str) -> None:
            if name in visited:
                return
            visited.add(name)

            if self._is_cache_hit(run_id, name, load=False):
                return

            if name not in self._plugins:
                return

            plugin = self._plugins[name]
            for dep_name in self._get_plugin_dependency_names(plugin, run_id=run_id):
                dfs(dep_name)
            needed.add(name)

        dfs(data_name)

        # Keep order consistent with the execution plan
        return {name for name in plan if name in needed}

    def _run_plugin(
        self,
        run_id: str,
        data_name: str,
        show_progress: bool = False,
        progress_desc: Optional[str] = None,
        plan: Optional[List[str]] = None,
        needed_set: Optional[Set[str]] = None,
        **kwargs,
    ) -> Any:
        """
        Override run_plugin to add saving logic and config resolution.
        运行插件, 包括依赖解析和进度追踪,
        注意：run_plugin 假定需要执行并跳过缓存判断，直接触发计算。

        参数:
            run_id: Run identifier
            data_name: Name of the data to produce
            show_progress: Whether to show progress bar during plugin execution
            progress_desc: Custom description for progress bar (default: auto-generated)
            plan: 可选，预先解析好的执行计划
            needed_set: 可选，需要执行的插件集合（由外部计算）
            **kwargs: Additional arguments passed to plugins
        """
        with self.profiler.timeit("context.run_plugin"):
            # 1. Check re-entrancy and mark as in-progress
            self._check_reentrancy(run_id, data_name)

            # Initialize variables for finally block
            tracker = None
            bar_name = None

            try:
                # 2. Resolve execution plan
                if plan is None:
                    plan = self._resolve_execution_plan(run_id, data_name)

                # Early return if data already in memory
                if not plan:
                    return self._get_data_from_memory(run_id, data_name)

                if needed_set is None:
                    needed_set = set(plan)

                # 3. Initialize progress tracking
                tracker, bar_name = self._init_progress_tracking(
                    show_progress, plan, run_id, data_name, progress_desc
                )

                # 4. Execute plan in order
                for name in plan:
                    if name not in needed_set:
                        key = self.key_for(run_id, name)
                        _data, cache_hit = self._cache_manager.check_cache(run_id, name, key)
                        if tracker and bar_name:
                            tracker.update(bar_name, n=1)
                        continue

                    self._execute_single_plugin(
                        name, run_id, data_name, kwargs, tracker, bar_name, skip_cache_check=True
                    )

                return self._get_data_from_memory(run_id, data_name)
            finally:
                # 5. Cleanup execution state
                if tracker and bar_name:
                    tracker.close(bar_name)
                with self._in_progress_lock:
                    self._in_progress.pop((run_id, data_name), None)

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
                    plan = self.resolve_dependencies(data_name, run_id=run_id)
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
        progress_desc: Optional[str],
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

    def _calculate_input_size(self, plugin: Plugin, run_id: str) -> Optional[float]:
        """计算插件输入数据大小（MB）

        Args:
            plugin: 插件实例
            run_id: 运行标识符

        Returns:
            输入数据大小（MB），如果无法计算则返回 None


        """
        if not (self.stats_collector and self.stats_collector.mode == "detailed"):
            return None

        try:
            total_bytes = 0
            for dep_name in self._get_plugin_dependency_names(plugin, run_id=run_id):
                dep_data = self._get_data_from_memory(run_id, dep_name)
                if dep_data is not None:
                    if isinstance(dep_data, np.ndarray):
                        total_bytes += dep_data.nbytes
                    elif isinstance(dep_data, list):
                        total_bytes += sum(
                            arr.nbytes for arr in dep_data if isinstance(arr, np.ndarray)
                        )
            return total_bytes / (1024 * 1024) if total_bytes > 0 else None
        except (AttributeError, TypeError) as e:
            # 某些数据类型可能没有 nbytes 属性
            self.logger.debug(f"Could not calculate input size for {plugin.provides}: {e}")
            return None
        except Exception as e:
            # 其他未预期的错误
            self.logger.warning(
                f"Unexpected error calculating input size for {plugin.provides}: {e}"
            )
            return None

    def _prepare_side_effect_isolation(self, plugin: Plugin, run_id: str, kwargs: dict) -> dict:
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
            if hasattr(self.storage, "get_run_side_effects_dir"):
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
        if not (self.stats_collector and self.stats_collector.mode == "detailed"):
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
        self, plugin: Plugin, name: str, run_id: str, input_size_mb: Optional[float], kwargs: dict
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
            severity = getattr(e, "severity", ErrorSeverity.FATAL)
            recoverable = getattr(e, "recoverable", False)

            # 收集错误上下文
            error_context = self._error_manager.collect_context(
                plugin,
                run_id,
                context=self,
                get_config_fn=self.get_config,
                get_data_fn=self._get_data_from_memory,
            )

            # 根据严重程度处理
            if severity == ErrorSeverity.FATAL:
                # 致命错误：记录并抛出
                self._error_manager.log_error(
                    name, e, run_id, plugin, error_context, get_config_fn=self.get_config
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
                    name, e, run_id, plugin, error_context, get_config_fn=self.get_config
                )
                raise RuntimeError(f"Plugin '{name}' failed: {str(e)}") from e
        finally:
            # Cleanup hook
            try:
                plugin.cleanup(self)
            except Exception as cleanup_error:
                # 记录清理错误，但不掩盖原始错误
                self.logger.warning(
                    f"Plugin '{name}' cleanup failed: {cleanup_error}", exc_info=True
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
        target_dtype: Optional[np.dtype],
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
        storage = self._get_storage_for_data_name(name)
        if isinstance(result, pd.DataFrame):
            # Save DataFrame as Parquet
            if hasattr(storage, "save_dataframe"):
                self._storage_save_dataframe(storage, key, result, run_id)
                self._storage_save_metadata(
                    storage, key, {"lineage": lineage, "type": "dataframe"}, run_id
                )
            else:
                raise RuntimeError(
                    f"Storage backend {storage.__class__.__name__} does not support DataFrame."
                )
            self._set_data(run_id, name, result)
        elif isinstance(result, list) and all(isinstance(x, np.ndarray) for x in result):
            # Save list of arrays (e.g. per-channel data)
            for i, arr in enumerate(result):
                ch_key = f"{key}_ch{i}"
                self._storage_save_memmap(storage, ch_key, arr, {"lineage": lineage}, run_id)
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
                self._storage_save_memmap(storage, key, result, {"lineage": lineage}, run_id)
                data = self._storage_load_memmap(storage, key, run_id)
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
        bar_name: Optional[str],
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
        result, effective_output_kind = self._validation_manager.validate_output_contract(
            plugin, result
        )
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
                name, success=True, cache_hit=False, output_size_mb=output_size_mb
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
        bar_name: Optional[str],
        skip_cache_check: bool = False,
    ) -> None:
        """执行单个插件的完整流程

        协调单个插件的完整执行，包括：
        1. 可选缓存检查
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
            skip_cache_check: 是否跳过缓存检查并强制执行

        Raises:
            RuntimeError: 当插件不存在或执行失败时
        """
        key = self.key_for(run_id, name)
        if not skip_cache_check:
            # Check cache (memory + disk)
            _data, cache_hit = self._cache_manager.check_cache(run_id, name, key)
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

        Notes:
            - Writes to a temporary file and atomically renames on completion.
            - Uses storage locks to avoid concurrent writes.
            - If lock acquisition fails, the generator is yielded without caching.
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
                self.storage.finalize_save(
                    key, total_count, dtype, extra_metadata={"lineage": lineage}
                )

                if total_count > 0:
                    self.logger.info(
                        f"Saved {total_count} items to cache for {data_name} ({run_id})"
                    )

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
                            exc_info=True,
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

    # ===========================
    # Lineage and dependence analysis
    # ===========================

    def plot_lineage(self, data_name: str, kind: str = "labview", **kwargs):
        """
        Visualize the lineage of a data type.

        Args:
            data_name: Name of the target data.
            kind: Visualization style ('labview', 'mermaid', or 'plotly').
            **kwargs: Additional arguments passed to the visualizer (e.g., save_path).
        """
        from .foundation.model import build_lineage_graph

        lineage = self.get_lineage(data_name)
        if not lineage:
            print(f"No lineage found for '{data_name}'")
            return

        # 统一构建模型
        model = build_lineage_graph(lineage, data_name, plugins=getattr(self, "_plugins", {}))

        # 验证模型是否正确构建
        if model is None:
            raise ValueError(
                f"build_lineage_graph returned None for data_name '{data_name}'. This may indicate an issue with the lineage data."
            )

        from .foundation.model import LineageGraphModel

        if not isinstance(model, LineageGraphModel):
            raise ValueError(
                f"build_lineage_graph returned unexpected type: {type(model).__name__}, "
                f"expected LineageGraphModel for data_name '{data_name}'."
            )

        if kind == "labview":
            return plot_lineage_labview(model, data_name, context=self, **kwargs)
        elif kind == "mermaid":
            mermaid_str = model.to_mermaid()
            print(mermaid_str)
            return mermaid_str
        elif kind == "plotly":
            return plot_lineage_plotly(model, data_name, context=self, **kwargs)
        else:
            raise ValueError(
                f"Unsupported visualization kind: {kind}. Supported: 'labview', 'mermaid', 'plotly'"
            )

    @property
    def profiling_summary(self) -> str:
        """Return a summary of the profiling data."""
        return self.profiler.summary()

    def get_performance_report(
        self, plugin_name: Optional[str] = None, format: str = "text"
    ) -> Any:
        """
        获取插件性能统计报告

        Args:
            plugin_name: 插件名称,None返回所有插件的统计
            format: 报告格式 ('text' 或 'dict')

        Returns:
            性能报告(文本或字典格式)

        Example:
            >>> ctx = Context(stats_mode='detailed')
            >>> # ... 执行一些插件 ...
            >>> print(ctx.get_performance_report())
            >>> # 或获取特定插件的统计
            >>> stats = ctx.get_performance_report(plugin_name='my_plugin', format='dict')
        """
        if not self.stats_collector or not self.stats_collector.is_enabled():
            return (
                "Performance statistics are disabled. Enable with stats_mode='basic' or 'detailed'"
            )

        if plugin_name:
            stats = self.stats_collector.get_statistics(plugin_name)
            if format == "dict":
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
                if self.stats_collector.mode == "detailed":
                    lines.append(
                        f"  Memory: peak={s.peak_memory_mb:.2f}MB, avg={s.avg_memory_mb:.2f}MB"
                    )
                if s.recent_errors:
                    lines.append(f"  Recent errors: {len(s.recent_errors)}")
                return "\n".join(lines)
        else:
            return self.stats_collector.generate_report(format=format)

    def analyze_dependencies(
        self, target_name: str, include_performance: bool = True, run_id: Optional[str] = None
    ):
        """
        分析插件依赖关系，识别关键路径、并行机会和性能瓶颈

        Args:
            target_name: 目标数据名称
            include_performance: 是否包含性能数据分析（需要stats_mode='basic'或'detailed'）
            run_id: 可选的run_id，用于获取特定运行的性能数据（暂未使用，为未来扩展预留）

        Returns:
            DependencyAnalysisResult: 分析结果对象

        Example:
            >>> ctx = Context(stats_mode='basic')
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
            target_name=target_name, include_performance=include_performance, run_id=run_id
        )

    def get_lineage(self, data_name: str, _visited: Optional[set] = None) -> Dict[str, Any]:
        """
        Get the lineage (recipe) for a data type. Uses caching for performance optimization.

        Args:
            data_name: The name of the data type for which to retrieve the lineage.
            _visited: Internal parameter used to track visited data names during recursion to detect and handle circular dependencies. Defaults to None.

        Returns:
            A dictionary representing the lineage of the specified data type.

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
        resolved = self.get_resolved_config(plugin)
        for k in plugin.config_keys:
            opt = plugin.options.get(k)
            if opt and getattr(opt, "track", True):
                cv = resolved.get_value(k)
                if cv is not None:
                    config[k] = cv.value

        dep_names = self._get_plugin_dependency_names(plugin)
        lineage = {
            "plugin_class": plugin.__class__.__name__,
            "plugin_version": getattr(plugin, "version", "0.0.0"),
            "description": getattr(plugin, "description", ""),
            "config": config,
            "depends_on": {
                dep: self.get_lineage(dep, _visited=_visited.copy()) for dep in dep_names
            },
        }

        # Add spec_hash if plugin has validated spec
        if hasattr(plugin, "_validated_spec") and plugin._validated_spec is not None:
            import hashlib
            import json

            spec_dict = plugin._validated_spec.to_dict()
            spec_json = json.dumps(spec_dict, sort_keys=True, default=str)
            lineage["spec_hash"] = hashlib.sha1(spec_json.encode()).hexdigest()[:8]

        if plugin.output_dtype is not None:
            # Standardize dtype to avoid version differences in str(dtype)
            try:
                lineage["dtype"] = np.dtype(plugin.output_dtype).descr
            except (TypeError, ValueError):
                # If dtype is not a valid numpy dtype (e.g., "List[str]"), store as string
                lineage["dtype"] = str(plugin.output_dtype)

        # Add adapter_info for top-level calls
        if len(_visited) == 1:
            adapter_name = self.config.get("daq_adapter")
            if adapter_name:
                adapter_info = get_adapter_info(adapter_name)
                if adapter_info:
                    lineage["adapter_info"] = adapter_info.to_dict()

        # Cache the lineage (only for top-level calls)
        if len(_visited) == 1:  # Top-level call
            self._lineage_cache[data_name] = lineage

        return lineage

    @staticmethod
    def _format_display_value(value: Any, width: int) -> str:
        value_str = repr(value) if value is not None else "None"
        if len(value_str) > width:
            return value_str[: max(0, width - 3)] + "..."
        return value_str

    def _style_options_table(self, df_display, show_current_values: bool):
        def _highlight_modified(row):
            styles = [""] * len(row)
            if show_current_values and row.get("track") is False:
                styles = [
                    "background-color: var(--jp-error-color2, rgba(255, 120, 120, 0.2));"
                ] * len(row)
            elif show_current_values and row.get("status") == "已修改":
                styles = [
                    "background-color: var(--jp-warn-color2, rgba(255, 210, 90, 0.2));"
                ] * len(row)
            if show_current_values and row.get("status") == "已修改":
                if "current" in df_display.columns:
                    idx = df_display.columns.get_loc("current")
                    styles[idx] = (
                        styles[idx] + " color: var(--jp-error-color1, #c00000); font-weight: 600;"
                    )
            return styles

        styler = df_display.style
        if show_current_values:
            styler = styler.apply(_highlight_modified, axis=1)
        return styler

    def list_plugin_configs(
        self,
        plugin_name: Optional[str] = None,
        show_current_values: bool = True,
        verbose: bool = True,
        as_dataframe: bool = True,  # 新增：是否用 DataFrame 展示
        show_full_help: bool = False,
    ):
        """
        列出插件配置选项（支持 DataFrame 展示）

        与 show_config 的关系：
        - list_plugin_configs 面向“配置选项清单”，展示插件有哪些可配置项、默认值/当前值、修改状态。
        - show_config 在指定 plugin_name 时会直接复用本方法，以确保展示样式一致。
        - show_config 在未指定 plugin_name 时展示“当前配置汇总”（全局/插件特定/未使用）。

        Returns:
            默认仍返回 result dict；
            如果 as_dataframe=True 且 verbose=True，会额外显示 DataFrame；
            如果你想拿到 DataFrame 对象，可以把最后两行的 return 改成 return result, df_plugins, df_options
        """

        result: Dict[str, Any] = {}

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
                "class": plugin.__class__.__name__,
                "description": getattr(plugin, "description", ""),
                "version": getattr(plugin, "version", "0.0.0"),
                "options": {},
            }

            for opt_name, option in plugin.options.items():
                opt_info = {
                    "default": option.default,
                    "type": (
                        option.type.__name__
                        if hasattr(option.type, "__name__")
                        else str(option.type) if option.type else "Any"
                    ),
                    "help": option.help,
                    "track": option.track,
                }

                # 获取当前配置值
                if show_current_values:
                    try:
                        current_value = self._resolve_config_value(plugin, opt_name)
                        opt_info["current_value"] = current_value
                        opt_info["is_default"] = current_value == option.default
                    except KeyError:
                        opt_info["current_value"] = None
                        opt_info["is_default"] = True

                plugin_info["options"][opt_name] = opt_info

            result[name] = plugin_info

        # DataFrame 展示
        if verbose and as_dataframe:
            import pandas as pd

            # 在 notebook 中 display（若不可用则 fallback）
            try:
                from IPython.display import display
            except Exception:
                display = None

            # 1) 插件概览表
            plugin_rows = []
            for pname, info in result.items():
                options_count = len(info["options"])
                modified_count = 0
                if show_current_values:
                    for opt in info["options"].values():
                        if not opt.get("is_default", True):
                            modified_count += 1
                plugin_rows.append(
                    {
                        "plugin": pname,
                        "class": info["class"],
                        "version": info["version"],
                        "description": info["description"],
                        "options": options_count,
                        "modified": modified_count if show_current_values else None,
                    }
                )

            df_plugins = pd.DataFrame(plugin_rows)
            if show_current_values:
                df_plugins = df_plugins.sort_values(
                    by=["modified", "plugin"], ascending=[False, True]
                )
            else:
                df_plugins = df_plugins.sort_values(by=["plugin"])
            df_plugins = df_plugins.set_index("plugin")

            # 2) 选项明细表（MultiIndex：plugin / option）
            option_rows = []
            for pname, info in result.items():
                for opt_name, opt in info["options"].items():
                    default_raw = opt.get("default", None)
                    current_raw = opt.get("current_value", None) if show_current_values else None
                    is_default = opt.get("is_default", True) if show_current_values else None
                    status = "默认" if is_default or is_default is None else "已修改"
                    option_rows.append(
                        {
                            "plugin": pname,
                            "option": opt_name,
                            "type": opt.get("type", "Any"),
                            "default": self._format_display_value(default_raw, 60),
                            "current": (
                                self._format_display_value(current_raw, 60)
                                if show_current_values
                                else None
                            ),
                            "status": status if show_current_values else None,
                            "help": (
                                opt.get("help", "")
                                if show_full_help
                                else self._format_display_value(opt.get("help", ""), 80)
                            ),
                            "track": opt.get("track", True),
                            "_is_default": is_default,
                            "_default_raw": default_raw,
                            "_current_raw": current_raw,
                        }
                    )

            df_options = pd.DataFrame(option_rows)
            if show_current_values:
                df_options = df_options.sort_values(
                    by=["_is_default", "plugin", "option"], ascending=[True, True, True]
                )
            else:
                df_options = df_options.sort_values(by=["plugin", "option"])
            df_options = df_options.set_index(["plugin", "option"])

            # 展示
            if display is not None:
                print("\n📦 插件概览")
                display(df_plugins)

                print("\n⚙️ 配置选项明细")
                df_display = df_options.drop(
                    columns=["_is_default", "_default_raw", "_current_raw"]
                )

                styler = self._style_options_table(df_display, show_current_values)
                display(styler)
            else:
                print("\n📦 插件概览")
                print(df_plugins.to_string())

                print("\n⚙️ 配置选项明细")
                fallback = df_options.drop(columns=["_is_default", "_default_raw", "_current_raw"])
                print(fallback.to_string())

            # 如果你希望函数直接把 DF 返回出去，把下面这行改成：
            # return result, df_plugins, df_options

        return result

    def _show_plugin_config(self, plugin_name: str, show_full_help: bool = False):
        """显示特定插件的配置（表格版）"""
        self.list_plugin_configs(
            plugin_name=plugin_name,
            show_current_values=True,
            verbose=True,
            as_dataframe=True,
            show_full_help=show_full_help,
        )

    def _show_global_config(
        self,
        show_usage: bool = True,
        show_full_help: bool = False,
        run_name: Optional[str] = None,
    ):
        """显示全局配置（表格版）"""
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
                        plugin_specific_configs[plugin_name][option_name] = self.config[
                            plugin_name
                        ][option_name]
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
            if "." in key:
                continue
            # 如果不在 config_usage 中，说明未被使用
            if key not in config_usage:
                unused_configs[key] = value

        # 统计信息
        cache_root = os.path.abspath(self.storage_dir)
        data_subdir = getattr(self.storage, "data_subdir", "_cache")
        run_name_value = run_name
        if run_name_value is None:
            run_name_value = (
                getattr(self, "run_name", None)
                or self.config.get("run_name")
                or self.config.get("run_id")
            )
        if run_name_value is None:
            run_name_value = getattr(self, "_last_run_id", None)
        run_name_display = str(run_name_value) if run_name_value is not None else "<run_id>"
        cache_dir = os.path.join(cache_root, run_name_display, data_subdir)
        print("\n配置概览")
        if run_name_value is None:
            print(f"缓存目录: {cache_dir} (run_id 在 get_data 时传入)")
        else:
            print(f"缓存目录: {cache_dir}")
        print(
            f"全局配置项: {len(global_configs)}  插件特定配置: {len(plugin_specific_configs)}  "
            f"未使用配置: {len(unused_configs)}"
        )

        import pandas as pd

        try:
            from IPython.display import display
        except Exception:
            display = None

        # 1. 全局配置表
        if global_configs:
            rows = []
            for key in sorted(global_configs.keys()):
                used_by = config_usage.get(key, [])
                used_by_str = ", ".join(used_by) if show_usage else None
                rows.append(
                    {
                        "key": key,
                        "value": self._format_display_value(global_configs[key], 80),
                        "used_by": (
                            self._format_display_value(used_by_str, 80) if show_usage else None
                        ),
                    }
                )
            df_global = pd.DataFrame(rows).set_index("key")

            print("\n📦 全局配置项")
            if display is not None:
                display(df_global if show_usage else df_global.drop(columns=["used_by"]))
            else:
                fallback = df_global if show_usage else df_global.drop(columns=["used_by"])
                print(fallback.to_string())

        # 2. 插件特定配置表
        if plugin_specific_configs:
            option_rows = []
            for plugin_name, configs in plugin_specific_configs.items():
                plugin = self._plugins.get(plugin_name)
                for key, value in configs.items():
                    option = plugin.options.get(key) if plugin else None
                    default_raw = option.default if option else None
                    is_default = value == default_raw if option else False
                    status = "默认" if is_default else "已修改"
                    option_rows.append(
                        {
                            "plugin": plugin_name,
                            "option": key,
                            "type": (
                                option.type.__name__
                                if option and hasattr(option.type, "__name__")
                                else str(option.type) if option and option.type else "Any"
                            ),
                            "default": self._format_display_value(default_raw, 60),
                            "current": self._format_display_value(value, 60),
                            "status": status,
                            "help": (
                                option.help
                                if (option and show_full_help)
                                else self._format_display_value(option.help, 80) if option else ""
                            ),
                            "track": option.track if option else True,
                            "_is_default": is_default,
                        }
                    )

            df_plugin = pd.DataFrame(option_rows)
            df_plugin = df_plugin.sort_values(
                by=["_is_default", "plugin", "option"], ascending=[True, True, True]
            )
            df_plugin = df_plugin.set_index(["plugin", "option"])
            df_display = df_plugin.drop(columns=["_is_default"])

            print("\n⚙️ 插件特定配置")
            if display is not None:
                display(self._style_options_table(df_display, show_current_values=True))
            else:
                print(df_display.to_string())

        # 3. 未使用配置表
        if unused_configs:
            rows = []
            for key in sorted(unused_configs.keys()):
                rows.append(
                    {
                        "key": key,
                        "value": self._format_display_value(unused_configs[key], 80),
                        "note": "未被任何已注册插件使用",
                    }
                )
            df_unused = pd.DataFrame(rows).set_index("key")

            print("\n⚠️ 未使用配置")
            if display is not None:
                display(
                    df_unused.style.apply(
                        lambda _: (
                            ["background-color: var(--jp-error-color2, rgba(255, 120, 120, 0.2));"]
                            * len(df_unused.columns)
                        ),
                        axis=1,
                    )
                )
            else:
                print(df_unused.to_string())

    def _delete_disk_cache(
        self, key: str, run_id: Optional[str] = None, data_name: Optional[str] = None
    ) -> int:
        """
        删除磁盘缓存（包括多通道数据和 DataFrame）。

        参数:
            key: 缓存键
            run_id: 运行标识符（用于分层存储模式）
            data_name: 数据名称（用于选择插件存储后端）

        返回:
            删除的缓存项数量
        """
        count = 0
        storage = self._get_storage_for_data_name(data_name) if data_name else self.storage

        # 删除主缓存文件
        if self._storage_exists(storage, key, run_id):
            try:
                self._storage_delete(storage, key, run_id)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to delete cache key {key}: {e}")

        # 删除多通道数据（{key}_ch*）
        for ch_key in self._list_channel_keys(storage, run_id, key):
            try:
                self._storage_delete(storage, ch_key, run_id)
                count += 1
            except Exception as e:
                self.logger.warning(f"Failed to delete multi-channel cache {ch_key}: {e}")

        # 删除 DataFrame 缓存（{key}.parquet）
        # 检查 storage 是否支持 DataFrame 存储（有 save_dataframe 方法）
        if hasattr(storage, "save_dataframe"):
            # 对于 MemmapStorage，获取正确的 parquet 路径
            if hasattr(storage, "work_dir") and run_id:
                # 分层模式：parquet 在 run 的 data 目录下
                parquet_path = os.path.join(
                    storage.work_dir, run_id, storage.data_subdir, f"{key}.parquet"
                )
            elif hasattr(storage, "db_path"):
                # 对于其他存储后端，如果 db_path 存在，可能在同目录下
                base_dir = os.path.dirname(storage.db_path)
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
    # 时间范围查询
    # ===========================

    def build_time_index(
        self,
        run_id: str,
        data_name: str,
        time_field: str = "time",
        endtime_field: Optional[str] = None,
        force_rebuild: bool = False,
    ) -> Dict[str, Any]:
        """
        为数据构建时间索引

        支持两种数据类型：
        - 单个结构化数组: 构建单个索引
        - List[np.ndarray]: 为每个通道分别构建索引

        Args:
            run_id: 运行ID
            data_name: 数据名称
            time_field: 时间字段名
            endtime_field: 结束时间字段名('computed'表示计算endtime)
            force_rebuild: 强制重建索引

        Returns:
            索引构建结果字典，包含：
            - 'type': 'single' 或 'multi_channel'
            - 'indices': 索引名称列表
            - 'stats': 各索引的统计信息

        Examples:
            >>> # 为 st_waveforms (List[np.ndarray]) 构建多通道索引
            >>> result = ctx.build_time_index('run_001', 'st_waveforms', endtime_field='computed')
            >>> print(result['type'])  # 'multi_channel'
            >>> print(result['indices'])  # ['st_waveforms_ch0', 'st_waveforms_ch1']
            >>>
            >>> # 为单个结构化数组构建索引
            >>> ctx.build_time_index('run_001', 'peaks')
        """
        from waveform_analysis.core.data.query import TimeRangeQueryEngine

        # 懒加载查询引擎
        if not hasattr(self, "_time_query_engine"):
            self._time_query_engine = TimeRangeQueryEngine()

        engine = self._time_query_engine

        # 获取数据
        data = self.get_data(run_id, data_name)

        if data is None or (hasattr(data, "__len__") and len(data) == 0):
            self.logger.warning(f"No data found for {data_name}, cannot build index")
            return {"type": "empty", "indices": [], "stats": {}}

        # 检测数据类型
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], np.ndarray):
            # List[np.ndarray] 类型 - 多通道数据
            return self._build_multi_channel_time_index(
                engine, run_id, data_name, data, time_field, endtime_field, force_rebuild
            )
        elif isinstance(data, np.ndarray) and data.dtype.names is not None:
            # 单个结构化数组
            engine.build_index(run_id, data_name, data, time_field, endtime_field, force_rebuild)
            index = engine.get_index(run_id, data_name)
            return {
                "type": "single",
                "indices": [data_name],
                "stats": {
                    data_name: {
                        "n_records": index.n_records if index else 0,
                        "time_range": (index.min_time, index.max_time) if index else (0, 0),
                        "build_time": index.build_time if index else 0.0,
                    }
                },
            }
        else:
            self.logger.warning(f"Data '{data_name}' is not a supported type for time indexing")
            return {"type": "unsupported", "indices": [], "stats": {}}

    def get_data_time_range(
        self,
        run_id: str,
        data_name: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        time_field: str = "time",
        endtime_field: Optional[str] = None,
        auto_build_index: bool = True,
        channel: Optional[int] = None,
    ) -> Union[np.ndarray, List[np.ndarray]]:
        """
        查询数据的时间范围

        支持两种数据类型：
        - 单个结构化数组: 返回过滤后的数组
        - List[np.ndarray]: 返回过滤后的列表（或指定通道的数组）

        Args:
            run_id: 运行ID
            data_name: 数据名称
            start_time: 起始时间(包含)
            end_time: 结束时间(不包含)
            time_field: 时间字段名
            endtime_field: 结束时间字段名('computed'表示计算endtime)
            auto_build_index: 自动构建时间索引
            channel: 指定通道号（仅用于多通道数据），None 表示返回所有通道

        Returns:
            符合条件的数据子集：
            - 单个数组数据: 返回 np.ndarray
            - 多通道数据: 返回 List[np.ndarray] 或指定通道的 np.ndarray

        Examples:
            >>> # 查询特定时间范围的波形数据（多通道）
            >>> data = ctx.get_data_time_range('run_001', 'st_waveforms',
            ...                                 start_time=1000000, end_time=2000000)
            >>> len(data)  # 返回列表，长度为通道数
            2
            >>>
            >>> # 只查询特定通道
            >>> ch0_data = ctx.get_data_time_range('run_001', 'st_waveforms',
            ...                                     start_time=1000000, end_time=2000000,
            ...                                     channel=0)
        """
        from waveform_analysis.core.data.query import TimeRangeQueryEngine

        # 懒加载查询引擎
        if not hasattr(self, "_time_query_engine"):
            self._time_query_engine = TimeRangeQueryEngine()

        engine = self._time_query_engine

        # 获取完整数据
        data = self.get_data(run_id, data_name)

        if data is None:
            return np.array([], dtype=np.float64)

        # 检测数据类型
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], np.ndarray):
            # List[np.ndarray] 类型 - 多通道数据
            return self._query_multi_channel_time_range(
                engine,
                run_id,
                data_name,
                data,
                start_time,
                end_time,
                time_field,
                endtime_field,
                auto_build_index,
                channel,
            )
        elif isinstance(data, np.ndarray):
            if len(data) == 0:
                return np.array([], dtype=data.dtype)
            if data.dtype.names is None:
                self.logger.warning(
                    f"Data '{data_name}' is not a structured array, returning full data"
                )
                return data
            return self._query_single_array_time_range(
                engine,
                run_id,
                data_name,
                data,
                start_time,
                end_time,
                time_field,
                endtime_field,
                auto_build_index,
            )
        else:
            self.logger.warning(f"Data '{data_name}' is not a supported type, returning as-is")
            return data

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
        if hasattr(self, "_time_query_engine"):
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
        if hasattr(self, "_time_query_engine"):
            return self._time_query_engine.get_stats()
        return {"total_indices": 0, "indices": {}}

    def _query_single_array_time_range(
        self,
        engine: Any,
        run_id: str,
        data_name: str,
        data: np.ndarray,
        start_time: Optional[int],
        end_time: Optional[int],
        time_field: str,
        endtime_field: Optional[str],
        auto_build_index: bool,
    ) -> np.ndarray:
        """查询单个结构化数组的时间范围"""
        # 如果没有时间字段,返回完整数据
        if time_field not in data.dtype.names:
            self.logger.warning(
                f"Time field '{time_field}' not found in {data_name}, returning full data"
            )
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

            filter_start = start_time if start_time is not None else int(times.min())
            filter_end = end_time if end_time is not None else int(times.max()) + 1

            mask = (times >= filter_start) & (times < filter_end)
            return data[mask]

    def _query_multi_channel_time_range(
        self,
        engine: Any,
        run_id: str,
        data_name: str,
        data: List[np.ndarray],
        start_time: Optional[int],
        end_time: Optional[int],
        time_field: str,
        endtime_field: Optional[str],
        auto_build_index: bool,
        channel: Optional[int],
    ) -> Union[np.ndarray, List[np.ndarray]]:
        """
        查询多通道数据的时间范围

        Args:
            engine: TimeRangeQueryEngine 实例
            run_id: 运行ID
            data_name: 数据名称
            data: 多通道数据列表
            start_time: 起始时间
            end_time: 结束时间
            time_field: 时间字段名
            endtime_field: 结束时间字段名
            auto_build_index: 自动构建索引
            channel: 指定通道，None 表示所有通道

        Returns:
            过滤后的数据（列表或单个数组）
        """
        n_channels = len(data)

        # 自动构建索引（如果需要）
        if auto_build_index:
            # 检查是否已有多通道索引元数据
            has_indices = (
                hasattr(self, "_multi_channel_indices")
                and (run_id, data_name) in self._multi_channel_indices
            )

            if not has_indices:
                self.build_time_index(run_id, data_name, time_field, endtime_field)

        # 如果指定了通道，只查询该通道
        if channel is not None:
            if channel < 0 or channel >= n_channels:
                self.logger.warning(
                    f"Channel {channel} out of range [0, {n_channels}), returning empty array"
                )
                return np.array([], dtype=data[0].dtype if n_channels > 0 else np.float64)

            return self._query_channel_time_range(
                engine, run_id, data_name, data[channel], channel, start_time, end_time, time_field
            )

        # 查询所有通道
        results = []
        for ch_idx, ch_data in enumerate(data):
            result = self._query_channel_time_range(
                engine, run_id, data_name, ch_data, ch_idx, start_time, end_time, time_field
            )
            results.append(result)

        return results

    def _query_channel_time_range(
        self,
        engine: Any,
        run_id: str,
        data_name: str,
        ch_data: np.ndarray,
        ch_idx: int,
        start_time: Optional[int],
        end_time: Optional[int],
        time_field: str,
    ) -> np.ndarray:
        """
        查询单个通道的时间范围

        Args:
            engine: TimeRangeQueryEngine 实例
            run_id: 运行ID
            data_name: 数据名称
            ch_data: 通道数据
            ch_idx: 通道索引
            start_time: 起始时间
            end_time: 结束时间
            time_field: 时间字段名

        Returns:
            过滤后的数据
        """
        if ch_data is None or len(ch_data) == 0:
            return np.array([], dtype=ch_data.dtype if ch_data is not None else np.float64)

        index_name = f"{data_name}_ch{ch_idx}"

        # 尝试使用索引
        if engine.has_index(run_id, index_name):
            indices = engine.query(run_id, index_name, start_time, end_time)
            if indices is not None and len(indices) > 0:
                return ch_data[indices]
            else:
                return np.array([], dtype=ch_data.dtype)
        else:
            # 回退到直接过滤, 通过
            if time_field not in ch_data.dtype.names:
                self.logger.warning(f"Time field '{time_field}' not found in channel {ch_idx}")
                return ch_data

            times = ch_data[time_field]
            if len(times) == 0:
                return np.array([], dtype=ch_data.dtype)

            filter_start = start_time if start_time is not None else int(times.min())
            filter_end = end_time if end_time is not None else int(times.max()) + 1

            mask = (times >= filter_start) & (times < filter_end)
            return ch_data[mask]

    def _build_multi_channel_time_index(
        self,
        engine: Any,
        run_id: str,
        data_name: str,
        data: List[np.ndarray],
        time_field: str,
        endtime_field: Optional[str],
        force_rebuild: bool,
    ) -> Dict[str, Any]:
        """
        为多通道数据构建时间索引

        Args:
            engine: TimeRangeQueryEngine 实例
            run_id: 运行ID
            data_name: 数据名称
            data: 多通道数据列表
            time_field: 时间字段名
            endtime_field: 结束时间字段名
            force_rebuild: 强制重建索引

        Returns:
            索引构建结果字典
        """
        indices = []
        stats = {}
        n_channels = len(data)

        self.logger.info(f"Building time index for {data_name} with {n_channels} channels")

        for ch_idx, ch_data in enumerate(data):
            if ch_data is None or len(ch_data) == 0:
                self.logger.warning(f"Channel {ch_idx} is empty, skipping")
                continue

            # 检查是否为结构化数组
            if not isinstance(ch_data, np.ndarray) or ch_data.dtype.names is None:
                self.logger.warning(f"Channel {ch_idx} is not a structured array, skipping")
                continue

            # 检查时间字段是否存在
            if time_field not in ch_data.dtype.names:
                self.logger.warning(
                    f"Time field '{time_field}' not found in channel {ch_idx}, skipping"
                )
                continue

            # 为每个通道构建索引，key 格式为 {data_name}_ch{i}
            index_name = f"{data_name}_ch{ch_idx}"
            engine.build_index(
                run_id, index_name, ch_data, time_field, endtime_field, force_rebuild
            )

            index = engine.get_index(run_id, index_name)
            if index:
                indices.append(index_name)
                stats[index_name] = {
                    "channel": ch_idx,
                    "n_records": index.n_records,
                    "time_range": (index.min_time, index.max_time),
                    "build_time": index.build_time,
                }

        # 同时记录一个元数据索引，标记这是多通道数据
        if not hasattr(self, "_multi_channel_indices"):
            self._multi_channel_indices = {}
        self._multi_channel_indices[(run_id, data_name)] = {
            "n_channels": n_channels,
            "channel_indices": indices,
        }

        self.logger.info(
            f"Built {len(indices)} channel indices for {data_name}, "
            f"total records: {sum(s['n_records'] for s in stats.values())}"
        )

        return {
            "type": "multi_channel",
            "n_channels": n_channels,
            "indices": indices,
            "stats": stats,
        }

    # ===========================
    # Epoch 管理 API（绝对时间支持）
    # ===========================

    def set_epoch(
        self,
        run_id: str,
        epoch: Union[datetime, float, str],
        time_unit: str = "ns",
    ) -> None:
        """
        手动设置 run 的 epoch（时间基准）

        Args:
            run_id: 运行标识符
            epoch: Epoch 值，支持多种格式：
                - datetime: Python datetime 对象
                - float: Unix 时间戳（秒）
                - str: ISO 8601 格式字符串（如 "2024-01-01T12:00:00Z"）
            time_unit: 相对时间单位（"ps", "ns", "us", "ms", "s"）

        Examples:
            >>> from datetime import datetime, timezone
            >>>
            >>> # 使用 datetime 对象
            >>> epoch = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            >>> ctx.set_epoch('run_001', epoch)
            >>>
            >>> # 使用 Unix 时间戳
            >>> ctx.set_epoch('run_001', 1704110400.0)
            >>>
            >>> # 使用 ISO 字符串
            >>> ctx.set_epoch('run_001', "2024-01-01T12:00:00Z")
        """
        from waveform_analysis.core.foundation.time_conversion import EpochInfo
        from waveform_analysis.utils.formats.base import TimestampUnit

        # 转换时间单位
        unit_map = {
            "ps": TimestampUnit.PICOSECONDS,
            "ns": TimestampUnit.NANOSECONDS,
            "us": TimestampUnit.MICROSECONDS,
            "ms": TimestampUnit.MILLISECONDS,
            "s": TimestampUnit.SECONDS,
        }
        ts_unit = unit_map.get(time_unit.lower(), TimestampUnit.NANOSECONDS)

        # 解析 epoch
        if isinstance(epoch, datetime):
            epoch_info = EpochInfo.from_datetime(epoch, source="manual", time_unit=ts_unit)
        elif isinstance(epoch, (int, float)):
            epoch_info = EpochInfo.from_timestamp(float(epoch), source="manual", time_unit=ts_unit)
        elif isinstance(epoch, str):
            # 解析 ISO 8601 字符串
            dt = datetime.fromisoformat(epoch.replace("Z", "+00:00"))
            epoch_info = EpochInfo.from_datetime(dt, source="manual", time_unit=ts_unit)
        else:
            raise TypeError(f"不支持的 epoch 类型: {type(epoch)}")

        self._epoch_cache[run_id] = epoch_info
        self.logger.info(f"Set epoch for {run_id}: {epoch_info}")

    def get_epoch(self, run_id: str) -> Optional[Any]:
        """
        获取 run 的 epoch 元数据

        Args:
            run_id: 运行标识符

        Returns:
            EpochInfo 实例，如果未设置则返回 None

        Examples:
            >>> epoch_info = ctx.get_epoch('run_001')
            >>> if epoch_info:
            ...     print(f"Epoch: {epoch_info.epoch_datetime}")
            ...     print(f"Source: {epoch_info.epoch_source}")
        """
        return self._epoch_cache.get(run_id)

    def auto_extract_epoch(
        self,
        run_id: str,
        strategy: str = "auto",
        file_paths: Optional[List[str]] = None,
    ) -> Any:
        """
        自动从数据文件提取 epoch

        Args:
            run_id: 运行标识符
            strategy: 提取策略（"auto", "filename", "csv_header", "first_event"）
            file_paths: 数据文件路径列表（如果为 None，从 raw_files 获取）

        Returns:
            提取的 EpochInfo 实例

        Raises:
            ValueError: 如果无法提取 epoch

        Examples:
            >>> # 自动提取（优先从文件名）
            >>> epoch_info = ctx.auto_extract_epoch('run_001')
            >>>
            >>> # 指定策略
            >>> epoch_info = ctx.auto_extract_epoch('run_001', strategy='filename')
        """
        from waveform_analysis.core.foundation.time_conversion import EpochExtractor

        # 如果没有提供文件路径，尝试从 raw_files 获取
        if file_paths is None:
            try:
                raw_files = self.get_data(run_id, "raw_files")
                if raw_files is not None and len(raw_files) > 0:
                    # raw_files 可能是 List[List[str]]（按通道分组）
                    if isinstance(raw_files[0], list):
                        file_paths = [f for ch_files in raw_files for f in ch_files]
                    else:
                        file_paths = list(raw_files)
            except Exception as e:
                self.logger.warning(f"无法获取 raw_files: {e}")

        if not file_paths:
            raise ValueError(
                f"无法提取 epoch：未找到数据文件。请确保 run '{run_id}' 有 raw_files 数据，或手动提供 file_paths 参数。"
            )

        # 创建提取器并提取 epoch
        extractor = EpochExtractor(filename_patterns=self.config.get("epoch_filename_patterns"))
        epoch_info = extractor.auto_extract(
            file_paths=file_paths,
            strategy=strategy,
        )

        # 缓存 epoch
        self._epoch_cache[run_id] = epoch_info
        self.logger.info(f"Auto-extracted epoch for {run_id}: {epoch_info}")

        return epoch_info

    def get_data_time_range_absolute(
        self,
        run_id: str,
        data_name: str,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
        time_field: str = "time",
        endtime_field: Optional[str] = None,
        auto_build_index: bool = True,
        channel: Optional[int] = None,
        auto_extract_epoch: bool = True,
    ) -> Union[np.ndarray, List[np.ndarray]]:
        """
        使用绝对时间（datetime）查询数据

        与 get_data_time_range() 功能相同，但使用 datetime 对象指定时间范围。

        Args:
            run_id: 运行标识符
            data_name: 数据名称
            start_dt: 起始时间（datetime，包含）
            end_dt: 结束时间（datetime，不包含）
            time_field: 时间字段名
            endtime_field: 结束时间字段名
            auto_build_index: 自动构建时间索引
            channel: 指定通道号（仅用于多通道数据）
            auto_extract_epoch: 如果未设置 epoch，是否自动提取

        Returns:
            符合条件的数据子集

        Raises:
            ValueError: 如果未设置 epoch 且无法自动提取

        Examples:
            >>> from datetime import datetime, timezone
            >>>
            >>> start = datetime(2024, 1, 1, 12, 0, 10, tzinfo=timezone.utc)
            >>> end = datetime(2024, 1, 1, 12, 0, 20, tzinfo=timezone.utc)
            >>>
            >>> data = ctx.get_data_time_range_absolute(
            ...     'run_001', 'peaks',
            ...     start_dt=start, end_dt=end
            ... )
        """
        from waveform_analysis.core.foundation.time_conversion import TimeConverter

        # 获取或提取 epoch
        epoch_info = self.get_epoch(run_id)
        if epoch_info is None:
            if auto_extract_epoch and self.config.get("auto_extract_epoch", True):
                try:
                    epoch_info = self.auto_extract_epoch(run_id)
                except ValueError as e:
                    raise ValueError(
                        f"无法使用绝对时间查询：{e}\n请使用 ctx.set_epoch('{run_id}', epoch) 手动设置 epoch。"
                    ) from e
            else:
                raise ValueError(
                    f"无法使用绝对时间查询：run '{run_id}' 未设置 epoch。\n"
                    f"请使用 ctx.set_epoch() 或 ctx.auto_extract_epoch() 设置 epoch。"
                )

        # 转换时间范围
        converter = TimeConverter(epoch_info)
        start_rel, end_rel = converter.convert_time_range(start_dt, end_dt)

        # 调用原始的相对时间查询方法
        return self.get_data_time_range(
            run_id=run_id,
            data_name=data_name,
            start_time=start_rel,
            end_time=end_rel,
            time_field=time_field,
            endtime_field=endtime_field,
            auto_build_index=auto_build_index,
            channel=channel,
        )

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
                f"数据类型 '{data_name}' 未注册。可用数据: {', '.join(self.list_provided_data())}"
            )

        # 1. 解析执行计划
        try:
            execution_plan = self._resolve_execution_plan(run_id, data_name)
        except Exception as e:
            print(f"✗ 无法解析依赖关系: {e}")
            return {"error": str(e)}

        # 2. 计算本次实际需要执行的步骤（cache-aware）
        needed_set = self._compute_needed_set(run_id, data_name, execution_plan)

        # 3. 检查缓存状态
        cache_status = {}
        if show_cache:
            for plugin_name in execution_plan:
                # 检查内存缓存
                in_memory = self._get_data_from_memory(run_id, plugin_name) is not None

                # 检查磁盘缓存
                on_disk = False
                if plugin_name in self._plugins:
                    try:
                        key = self.key_for(run_id, plugin_name)
                        on_disk = self._is_disk_cache_valid(run_id, plugin_name, key)
                    except Exception:
                        pass

                cache_status[plugin_name] = {
                    "in_memory": in_memory,
                    "on_disk": on_disk,
                    "needs_compute": plugin_name in needed_set,
                    "pruned": (plugin_name not in needed_set) and not (in_memory or on_disk),
                }

        # 4. 收集配置信息
        configs = {}
        if show_config:
            for plugin_name in execution_plan:
                if plugin_name in self._plugins:
                    plugin = self._plugins[plugin_name]
                    plugin_config = {}

                    # 只收集非默认值的配置
                    if hasattr(plugin, "options"):
                        for opt_name, opt_obj in plugin.options.items():
                            value = self.get_config(plugin, opt_name)
                            if value != opt_obj.default:
                                plugin_config[opt_name] = {
                                    "value": value,
                                    "default": opt_obj.default,
                                    "type": opt_obj.type.__name__ if opt_obj.type else "Any",
                                }

                    if plugin_config:
                        configs[plugin_name] = plugin_config

        # 5. 构建结果字典
        resolved_depends_on = {}
        if show_tree or verbose > 1:
            for plugin_name in execution_plan:
                plugin = self._plugins.get(plugin_name)
                if plugin is None:
                    continue
                resolved_depends_on[plugin_name] = self._get_plugin_dependency_names(
                    plugin, run_id=run_id
                )
        result = {
            "target": data_name,
            "run_id": run_id,
            "execution_plan": execution_plan,
            "cache_status": cache_status,
            "configs": configs,
            "resolved_depends_on": resolved_depends_on,
            "needed_set": sorted(needed_set),
        }

        # 6. 打印格式化输出
        self._print_preview(
            result,
            show_tree=show_tree,
            show_config=show_config,
            show_cache=show_cache,
            verbose=verbose,
        )

        return result

    def _print_preview(
        self,
        info: Dict[str, Any],
        show_tree: bool,
        show_config: bool,
        show_cache: bool,
        verbose: int,
    ):
        """打印格式化的预览信息"""

        # 标题
        print("\n" + "=" * 70)
        print(f"执行计划预览: {info['target']} (run_id: {info['run_id']})")
        print("=" * 70)

        # 1. 执行计划
        print(f"\n{'📋 执行计划' if verbose > 0 else '执行计划'}:")
        print(f"  {'共 ' + str(len(info['execution_plan'])) + ' 个步骤' if verbose > 0 else ''}")

        for i, plugin_name in enumerate(info["execution_plan"], 1):
            # 获取缓存状态标记
            status_mark = ""
            if show_cache and plugin_name in info["cache_status"]:
                status = info["cache_status"][plugin_name]
                if status["in_memory"]:
                    status_mark = " ✓ [内存]"
                elif status["on_disk"]:
                    status_mark = " ✓ [磁盘]"
                elif status.get("pruned"):
                    status_mark = " ↳ [剪枝]"
                else:
                    status_mark = " ⚙️ [需计算]"

            arrow = "  └─→" if i == len(info["execution_plan"]) else "  ├─→"
            print(f"{arrow} {i}. {plugin_name}{status_mark}")

        # 2. 依赖关系树
        if show_tree:
            print(f"\n{'🌳 依赖关系树' if verbose > 0 else '依赖关系树'}:")
            self._print_dependency_tree(info["target"], prefix="  ", run_id=info.get("run_id"))

        # 3. 解析后的依赖（verbose > 1）
        if verbose > 1 and info.get("resolved_depends_on"):
            print(f"\n{'🔗 解析后依赖' if verbose > 0 else '解析后依赖'}:")
            for plugin_name in info["execution_plan"]:
                deps = info["resolved_depends_on"].get(plugin_name, [])
                if deps:
                    print(f"  • {plugin_name}: {', '.join(deps)}")

        # 4. 配置参数
        if show_config and info["configs"]:
            print(f"\n{'⚙️ 自定义配置' if verbose > 0 else '自定义配置'}:")
            for plugin_name, plugin_config in info["configs"].items():
                print(f"  • {plugin_name}:")
                for opt_name, opt_info in plugin_config.items():
                    default_str = f" (默认: {opt_info['default']})" if verbose > 1 else ""
                    print(f"      {opt_name} = {opt_info['value']}{default_str}")
        elif show_config:
            print(f"\n{'⚙️ 自定义配置' if verbose > 0 else '自定义配置'}: 无（使用所有默认值）")

        # 5. 缓存状态汇总
        if show_cache:
            cache_summary = {"in_memory": 0, "on_disk": 0, "needs_compute": 0, "pruned": 0}
            for status in info["cache_status"].values():
                if status["in_memory"]:
                    cache_summary["in_memory"] += 1
                elif status["on_disk"]:
                    cache_summary["on_disk"] += 1
                elif status.get("pruned"):
                    cache_summary["pruned"] += 1
                else:
                    cache_summary["needs_compute"] += 1

            print(f"\n{'💾 缓存状态汇总' if verbose > 0 else '缓存汇总'}:")
            print(f"  • 内存缓存: {cache_summary['in_memory']} 个")
            print(f"  • 磁盘缓存: {cache_summary['on_disk']} 个")
            print(f"  • 需要计算: {cache_summary['needs_compute']} 个")
            print(f"  • 已剪枝: {cache_summary['pruned']} 个")

        print("\n" + "=" * 70 + "\n")

    def _print_dependency_tree(
        self,
        data_name: str,
        prefix: str = "",
        is_last: bool = True,
        visited: Optional[set] = None,
        run_id: Optional[str] = None,
    ):
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
        dependencies = self._get_plugin_dependency_names(plugin, run_id=run_id)

        if not dependencies:
            return

        # 打印子节点
        extension = "   " if is_last else "│  "
        for i, dep in enumerate(dependencies):
            is_last_dep = i == len(dependencies) - 1
            self._print_dependency_tree(
                dep, prefix + extension, is_last_dep, visited.copy(), run_id=run_id
            )

    # ==========================
    # 帮助系统和快速开始模板
    # ==========================

    def help(self, topic: Optional[str] = None) -> str:
        """
        显示文档位置和快速参考

        Args:
            topic: 可选的主题名称（用于提示具体文档路径）

        Returns:
            帮助文本

        Examples:
            >>> ctx.help()  # 显示文档位置
            >>> ctx.help('config')  # 提示配置相关文档
        """
        # 主题到文档的映射
        topic_docs = {
            "quickstart": "docs/user-guide/QUICKSTART_GUIDE.md",
            "config": "docs/features/context/CONFIGURATION.md",
            "plugins": "docs/features/plugin/README.md",
            "performance": "docs/features/advanced/EXECUTOR_MANAGER_GUIDE.md",
            "examples": "docs/user-guide/EXAMPLES_GUIDE.md",
        }

        if topic is None:
            # 快速参考
            result = """
╔══════════════════════════════════════════════════════════════════════════════╗
║ WaveformAnalysis - 文档指南                                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

📚 文档位置
  • 项目说明: CLAUDE.md
  • 详细文档: docs/ 目录
  • 快速参考: QUICK_REFERENCE.md

🚀 快速开始
────────────────────────────────────────────────────────────────────────────────
  from waveform_analysis.core.context import Context
  from waveform_analysis.core.plugins import profiles

  ctx = Context(storage_dir='./data')
  ctx.register(*profiles.cpu_default())
  ctx.set_config({'n_channels': 2})
  data = ctx.get_data('run_001', 'basic_features')
────────────────────────────────────────────────────────────────────────────────

📖 主题文档
  ctx.help('quickstart')   - 快速上手指南
  ctx.help('config')       - 配置管理
  ctx.help('plugins')      - 插件系统
  ctx.help('performance')  - 性能优化
  ctx.help('examples')     - 使用示例

🔧 常用方法
  ctx.list_plugin_configs()     - 查看所有配置选项
  ctx.show_config()             - 查看当前配置
  ctx.list_provided_data()      - 查看可用数据类型
  ctx.plot_lineage('peaks')     - 可视化依赖关系
  ctx.preview_execution(...)    - 预览执行计划

💡 提示: 使用 IDE 或编辑器打开 docs/ 目录获得最佳阅读体验
"""
        elif topic in topic_docs:
            doc_path = topic_docs[topic]
            result = f"""
📖 {topic.upper()} 主题文档

文档位置: {doc_path}

💡 查看方式:
  • 命令行: cat {doc_path}
  • 编辑器: code {doc_path}
  • 带高亮: bat {doc_path}

返回主菜单: ctx.help()
"""
        else:
            available = ", ".join(topic_docs.keys())
            result = f"""
❌ 未知主题: '{topic}'

可用主题: {available}

💡 使用 ctx.help() 查看完整帮助
"""

        print(result)
        return result

    def quickstart(self, template: str = "basic") -> str:
        """
        显示快速开始代码示例

        Args:
            template: 模板名称（目前仅支持 'basic'）

        Returns:
            示例代码字符串

        Examples:
            >>> ctx.quickstart()
            >>> ctx.quickstart('basic')
        """
        if template != "basic":
            result = f"""
❌ 未知模板: '{template}'

目前仅支持 'basic' 模板。

💡 更多示例请查看:
  • docs/user-guide/QUICKSTART_GUIDE.md
  • docs/user-guide/EXAMPLES_GUIDE.md
  • examples/ 目录
"""
            print(result)
            return result

        # 基础分析流程示例
        code = '''"""
WaveformAnalysis 基础分析流程

这是一个完整的数据分析示例，展示从原始数据到事件配对的完整流程。
"""

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles

# 1. 创建 Context 并注册插件
ctx = Context(config={
    'data_root': 'DAQ',           # 数据根目录
    'n_channels': 2,              # 通道数
    'daq_adapter': 'vx2730',      # DAQ 适配器
})

# 注册标准 CPU 插件
ctx.register(*profiles.cpu_default())

# 2. 设置运行 ID
run_id = 'run_001'

# 3. 获取数据（自动解析依赖）
peaks = ctx.get_data(run_id, 'peaks')
print(f"找到 {len(peaks)} 个峰值")

# 4. 查看配置和依赖
ctx.show_config()                      # 显示当前配置
ctx.plot_lineage('peaks')              # 可视化依赖关系
ctx.preview_execution(run_id, 'peaks') # 预览执行计划

# 5. 更多数据类型
df = ctx.get_data(run_id, 'df')                    # DataFrame
grouped = ctx.get_data(run_id, 'df_grouped')       # 分组事件
paired = ctx.get_data(run_id, 'df_paired')         # 配对事件

# 6. 时间范围查询
peaks_subset = ctx.get_data_time_range(
    run_id, 'peaks',
    start_time=1000000,
    end_time=2000000
)

# 7. 缓存管理
ctx.cache_stats()                      # 查看缓存统计
ctx.diagnose_cache(run_id)             # 诊断缓存问题

print("✅ 分析完成！")

# 💡 更多示例请查看:
#   • docs/user-guide/QUICKSTART_GUIDE.md
#   • docs/user-guide/EXAMPLES_GUIDE.md
#   • examples/ 目录
'''

        print(code)
        return code

    # ===========================
    # 缓存管理工具 (Cache Management)
    # ===========================
    from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer
    from waveform_analysis.core.storage.cache_diagnostics import CacheDiagnostics, DiagnosticIssue
    from waveform_analysis.core.storage.cache_statistics import CacheStatistics

    def analyze_cache(self, run_id: Optional[str] = None, verbose: bool = True) -> CacheAnalyzer:
        """获取缓存分析器实例并执行扫描

        创建一个 CacheAnalyzer 实例来分析缓存状态，支持按 run_id 过滤。

        Args:
            run_id: 仅分析指定运行的缓存，None 则分析所有
            verbose: 是否显示扫描进度

        Returns:
            CacheAnalyzer 实例（已完成扫描）

        Examples:
            >>> # 获取缓存分析器
            >>> analyzer = ctx.analyze_cache()
            >>>
            >>> # 查看所有条目
            >>> entries = analyzer.get_entries()
            >>> print(f"共 {len(entries)} 个缓存条目")
            >>>
            >>> # 按条件过滤
            >>> large = analyzer.get_entries(min_size=1024*1024)
            >>> old = analyzer.get_entries(max_age_days=30)
            >>>
            >>> # 打印摘要
            >>> analyzer.print_summary(detailed=True)
        """
        from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer

        analyzer = CacheAnalyzer(self)
        run_ids = [run_id] if run_id else None
        analyzer.scan(verbose=verbose, run_ids=run_ids)
        return analyzer

    def diagnose_cache(
        self,
        run_id: Optional[str] = None,
        auto_fix: bool = False,
        dry_run: bool = True,
        verbose: bool = True,
    ) -> List[DiagnosticIssue]:
        """诊断缓存问题

        检查缓存的完整性、版本一致性、孤儿文件等问题。

        Args:
            run_id: 仅诊断指定运行，None 则诊断所有
            auto_fix: 是否自动修复可修复的问题
            dry_run: 如果 auto_fix=True，是否仅预演（不实际执行）
            verbose: 是否显示详细信息

        Returns:
            List[DiagnosticIssue]

        Examples:
            >>> # 诊断所有缓存
            >>> issues = ctx.diagnose_cache()
            >>>
            >>> # 诊断特定运行
            >>> issues = ctx.diagnose_cache(run_id='run_001')
            >>>
            >>> # 自动修复（先 dry-run）
            >>> issues = ctx.diagnose_cache(auto_fix=True, dry_run=True)
            >>>
            >>> # 实际修复
            >>> issues = ctx.diagnose_cache(auto_fix=True, dry_run=False)
        """

        from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer
        from waveform_analysis.core.storage.cache_diagnostics import (
            CacheDiagnostics,
        )

        analyzer = CacheAnalyzer(self)
        analyzer.scan(verbose=False)

        diag = CacheDiagnostics(analyzer)
        issues = diag.diagnose(run_id=run_id, verbose=verbose)

        if verbose:
            diag.print_report(issues)

        if auto_fix and issues:
            fixable = [i for i in issues if i.fixable]
            if fixable:
                result = diag.auto_fix(issues, dry_run=dry_run)
                if verbose:
                    print(
                        f"\n[修复结果] 总计: {result['total']}, "
                        f"可修复: {result['fixable']}, "
                        f"{'将修复' if dry_run else '已修复'}: {result['fixed']}"
                    )

        return issues

    def cache_stats(
        self,
        run_id: Optional[str] = None,
        detailed: bool = False,
        export_path: Optional[str] = None,
    ) -> CacheStatistics:
        """获取缓存统计信息

        收集并显示缓存使用情况的统计信息。

        Args:
            run_id: 仅统计指定运行，None 则统计所有
            detailed: 是否显示详细统计（按运行、按数据类型）
            export_path: 如果指定，导出统计到文件（支持 .json, .csv）

        Returns:
            CacheStatistics 统计数据

        Examples:
            >>> # 获取基本统计
            >>> stats = ctx.cache_stats()
            >>>
            >>> # 详细统计
            >>> stats = ctx.cache_stats(detailed=True)
            >>>
            >>> # 特定运行的统计
            >>> stats = ctx.cache_stats(run_id='run_001', detailed=True)
            >>>
            >>> # 导出统计
            >>> stats = ctx.cache_stats(export_path='cache_stats.json')
        """
        from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer
        from waveform_analysis.core.storage.cache_statistics import CacheStatsCollector

        analyzer = CacheAnalyzer(self)
        analyzer.scan(verbose=False)

        collector = CacheStatsCollector(analyzer)
        stats = collector.collect(run_id=run_id)
        collector.print_summary(stats, detailed=detailed)

        if export_path:
            fmt = "csv" if export_path.endswith(".csv") else "json"
            collector.export_stats(stats, export_path, format=fmt)

        return stats

    def __repr__(self):
        return f"Context(storage='{self.storage_dir}', plugins={self.list_provided_data()})"
