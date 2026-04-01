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
from collections import deque
from collections.abc import Callable, Iterator
import copy
from datetime import datetime, timezone
import functools
import hashlib
import importlib
import inspect
import json
import logging
import os
import re
import threading
from typing import Any, Optional, Union, cast
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
from .context_cache import ContextCacheDomain
from .context_config import ContextConfigDomain
from .context_execution import ContextExecutionDomain
from .context_time import ContextTimeDomain
from .execution.validation import ValidationManager
from .foundation.error import ErrorManager
from .foundation.exceptions import ErrorSeverity
from .foundation.mixins import PluginMixin
from .foundation.utils import OneTimeGenerator, Profiler
from .hardware.channel import HardwareChannel
from .plugins.core.base import Plugin
from .storage.cache_manager import RuntimeCacheManager
from .storage.memmap import MemmapStorage


def _safe_copy_config(config: dict[str, Any]) -> dict[str, Any]:
    try:
        return copy.deepcopy(config)
    except Exception:
        return config.copy()


def _load_json_object(path: str) -> dict[str, Any]:
    """Load a JSON object from disk and validate its top-level type."""
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Config JSON file must contain a JSON object, got {type(payload).__name__}."
        )
    return payload


def _extract_config_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Support both raw config JSON and exported custom-config snapshot JSON."""
    nested = payload.get("custom_config")
    if isinstance(nested, dict):
        return nested
    return payload


def _apply_memmap_settings(storage: MemmapStorage, spec: dict[str, Any]) -> None:
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


def _create_context_from_spec(spec: dict[str, Any]) -> "Context":
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


class Context(PluginMixin):
    """
    The Context orchestrates plugins and manages data storage/caching.
    Inspired by strax, it is the main entry point for data analysis.
    """

    # 保留名称集合：这些名称不能用作数据名，因为它们是 Context 的方法或属性
    _RESERVED_NAMES = frozenset(
        {
            "analyze_dependencies",
            "clear_cache",
            "clear_cache_for",
            "clear_config_cache",
            "clear_performance_caches",
            "clear_time_index",
            "config",
            "get_data",
            "get_config",
            "get_lineage",
            "get_performance_report",
            "get_run_config",
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
            "time_range",
        }
    )
    # Multi-channel structured outputs now use a single array with a channel field.
    # Legacy list-of-arrays caches for these data names should be treated as invalid.
    _FLAT_CHANNEL_OUTPUTS = frozenset(
        {
            "st_waveforms",
            "filtered_waveforms",
            "basic_features",
            "signal_peaks_stream",
            "waveform_width",
            "waveform_width_integral",
            "s1_s2",
        }
    )
    _REMOVED_DATA_NAME_ALIASES = {
        "events_df": "df",
        "events_grouped": "df_events",
    }
    _CONTEXT_CONFIG_KEYS = frozenset(
        {
            "data_root",
            "plugin_backends",
            "compression",
            "compression_kwargs",
            "enable_checksum",
            "verify_on_load",
            "checksum_algorithm",
            "custom_config_json_path",
            "run_config_path",
            "run_config_filename",
            "run_config_path_template",
        }
    )
    _CONTEXT_RUNTIME_KEYS = frozenset(
        {
            "storage_dir",
        }
    )
    _CONTEXT_DISPLAY_DEFAULTS = {
        "custom_config_json_path": None,
        "run_config_path": None,
    }
    _CONTEXT_CONFIG_NOTES = {
        "custom_config_json_path": "分析配置快照 JSON 输出路径",
        "data_root": "原始 DAQ 数据根目录",
        "plugin_backends": "按数据名覆盖存储后端",
        "compression": "缓存压缩算法",
        "compression_kwargs": "缓存压缩参数",
        "enable_checksum": "是否写入缓存校验和",
        "verify_on_load": "读取缓存时是否校验完整性",
        "checksum_algorithm": "缓存校验算法",
        "run_config_path": "run 级配置文件路径模板",
        "run_config_filename": "兼容旧配置的 run 配置文件名",
        "run_config_path_template": "兼容旧配置的 run 配置路径模板",
        "storage_dir": "缓存与处理产物存储目录",
    }
    _LEGACY_CONFIG_KEY_RENAMES = (
        ("events_df", "gain_adc_per_pe", "df", "gain_adc_per_pe"),
        ("events_grouped", "time_window_ns", "df_events", "time_window_ns"),
        ("events_grouped", "use_numba", None, "use_numba"),
        ("events_grouped", "n_processes", None, "n_processes"),
    )
    _LEGACY_CONFIG_KEY_REMOVED = (
        ("events_df", "fixed_baseline"),
        ("events_df", "peaks_range"),
        ("events_df", "charge_range"),
        ("events_df", "include_event_id"),
    )
    _TIME_DOMAIN_SYSTEM_NS = "system_ns"
    _TIME_DOMAIN_RAW_PS = "raw_ps"
    _TIME_DOMAIN_CHOICES = frozenset({_TIME_DOMAIN_SYSTEM_NS, _TIME_DOMAIN_RAW_PS})

    def from_config_json(
        self,
        config_json_path: str,
        plugin_name: str | None = None,
    ) -> None:
        """
        Load config from a JSON file and apply it to the current Context.

        Args:
            config_json_path: JSON file path. Relative paths are resolved from the current cwd.
            plugin_name: Optional plugin namespace passed through to ``set_config``.
        """
        file_config = _extract_config_payload(_load_json_object(str(config_json_path)))
        self.set_config(file_config, plugin_name=plugin_name)

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        storage_backend: Any | None = None,
        storage_dir: str | None = None,
        external_plugin_dirs: list[str] | None = None,
        auto_discover_plugins: bool = False,
        stats_mode: str = "off",
        stats_log_file: str | None = None,
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
        self._plugin_backends: dict[str, Any] = {}
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
        self._results: dict[tuple, Any] = {}
        # Lineage hash for each cached result (for config change detection)
        self._results_lineage: dict[tuple, str] = {}  # (run_id, data_name) -> lineage_hash
        # Re-entrancy guard: track (run_id, data_name) currently being computed
        self._in_progress: dict[tuple, Any] = {}
        self._in_progress_lock = threading.Lock()  # Protect concurrent access
        # Cache of validated configs per plugin signature
        self._resolved_config_cache: dict[tuple, dict[str, Any]] = {}

        # Performance optimization caches
        self._execution_plan_cache: dict[str, list[str]] = {}  # data_name -> execution plan
        self._lineage_cache: dict[str, dict[str, Any]] = {}  # data_name -> lineage dict
        self._lineage_hash_cache: dict[str, str] = {}  # data_name -> lineage hash
        self._key_cache: dict[tuple, str] = {}  # (run_id, data_name) -> key
        # Per-run config cache (loaded from run_config.json) and hash tracking.
        self._run_config_cache: dict[str, dict[str, Any]] = {}
        self._run_config_hash_cache: dict[str, str] = {}
        self._run_config_hash_loaded: set[str] = set()
        self._legacy_config_notices: set[str] = set()

        # Plugin discovery
        self.plugin_dirs = external_plugin_dirs or []
        if auto_discover_plugins:
            self.discover_and_register_plugins()

        # Ensure storage directory exists if using default
        if not storage_backend and not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)

        # Epoch management (per-run time reference)
        self._epoch_cache: dict[str, Any] = {}  # run_id -> EpochInfo

        # Epoch configuration defaults
        self.config.setdefault("auto_extract_epoch", True)
        self.config.setdefault(
            "epoch_extraction_strategy", "auto"
        )  # "auto", "filename", "csv_header", "first_event"
        self.config.setdefault("epoch_filename_patterns", None)  # None = use defaults

        # ConfigResolver handles precedence + adapter inference; validated configs are cached
        # in _resolved_config_cache to avoid repeated validation work.
        self._compat_manager = CompatManager()
        self._config_resolver = ConfigResolver(compat_manager=self._compat_manager)

        self._config_domain = ContextConfigDomain(self)
        self._cache_domain = ContextCacheDomain(self)
        self._execution_domain = ContextExecutionDomain(self)
        self._time_domain = ContextTimeDomain(self)

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

    def _build_memmap_storage_spec(self) -> dict[str, Any]:
        return {
            "type": "memmap",
            "compression": getattr(self.storage, "compression", None),
            "enable_checksum": getattr(self.storage, "enable_checksum", False),
            "checksum_algorithm": getattr(self.storage, "checksum_algorithm", "xxhash64"),
            "verify_on_load": getattr(self.storage, "verify_on_load", False),
            "data_subdir": getattr(self.storage, "data_subdir", "_cache"),
            "side_effects_subdir": getattr(self.storage, "side_effects_subdir", "side_effects"),
        }

    def _build_context_factory_spec(self) -> dict[str, Any]:
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
        *plugins: Plugin | type[Plugin] | Any,
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
            ...     RawFileNamesPlugin, WaveformsPlugin
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
            ...     WaveformsPlugin()
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
            if isinstance(p, list | tuple | set):
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

    # ===========================
    # Config Resolution
    # ===========================

    def set_config(self, config: dict[str, Any], plugin_name: str | None = None):
        self._config_domain.set_config(config, plugin_name=plugin_name)

    def get_config_value(
        self,
        plugin: Plugin,
        name: str,
        adapter_name: str | None = None,
    ) -> ConfigValue:
        return self._config_domain.get_config_value(plugin, name, adapter_name=adapter_name)

    def get_config(self, plugin: Plugin, name: str) -> Any:
        return self._config_domain.get_config(plugin, name)

    def has_explicit_config(
        self,
        plugin: Plugin,
        name: str,
        adapter_name: str | None = None,
    ) -> bool:
        return self._config_domain.has_explicit_config(plugin, name, adapter_name=adapter_name)

    def get_resolved_config(
        self,
        plugin: Plugin | str,
        adapter_name: str | None = None,
    ) -> ResolvedConfig:
        return self._config_domain.get_resolved_config(plugin, adapter_name=adapter_name)

    def get_run_config(self, run_id: str, refresh: bool = False) -> dict[str, Any]:
        return self._config_domain.get_run_config(run_id, refresh=refresh)

    def get_plugin_run_config(self, plugin: Plugin | str, run_id: str) -> dict[str, Any]:
        return self._config_domain.get_plugin_run_config(plugin, run_id)

    def show_resolved_config(
        self,
        plugin: Plugin | str | None = None,
        verbose: bool = True,
        adapter_name: str | None = None,
    ) -> None:
        self._config_domain.show_resolved_config(
            plugin=plugin,
            verbose=verbose,
            adapter_name=adapter_name,
        )

    def get_adapter_info(self, adapter_name: str | None = None) -> AdapterInfo | None:
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
        data_name: str | None = None,
        show_usage: bool = True,
        show_full_help: bool = False,
        run_name: str | None = None,
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
            self.list_plugin_configs(
                plugin_name=data_name,
                show_current_values=True,
                verbose=True,
                as_dataframe=True,
                show_full_help=show_full_help,
            )
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
        progress_desc: str | None = None,
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
        self._config_domain.prepare_request(run_id, data_name)
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
        plan = self._execution_domain.resolve_execution_plan(run_id, data_name)
        if not plan:
            return self._get_data_from_memory(run_id, data_name)
        needed_set = self._execution_domain.compute_needed_set(run_id, data_name, plan)

        # 4. Execute plan
        return self._execution_domain.run_plugin(
            run_id,
            data_name,
            show_progress=show_progress,
            progress_desc=progress_desc,
            plan=plan,
            needed_set=needed_set,
            **kwargs,
        )

    def list_provided_data(self) -> list[str]:
        """List all data types provided by registered plugins."""
        return list(self._plugins.keys())

    def clear_performance_caches(self):
        """
        Clear all performance optimization caches.

        Should be called when plugins are registered/unregistered or
        when plugin configurations change.
        """
        self._cache_domain.clear_performance_caches()

    def key_for(self, run_id: str, data_name: str) -> str:
        """
        Get a unique key (hash) for a data type and run.

        Uses caching for performance optimization.
        """
        return self._cache_domain.key_for(run_id, data_name)

    def clear_cache_for(
        self,
        run_id: str,
        data_name: str | None = None,
        downstream: bool = False,
        clear_memory: bool = True,
        clear_disk: bool = True,
        verbose: bool = True,
    ) -> int:
        """
        清理指定运行和步骤的缓存。

        参数:
            run_id: 运行 ID
            data_name: 数据名称（步骤名称），如果为 None 则清理所有步骤
            downstream: 是否同时清理下游依赖的数据缓存
            clear_memory: 是否清理内存缓存
            clear_disk: 是否清理磁盘缓存
            verbose: 是否显示详细的清理信息

        返回:
            清理的缓存项数量

        示例:
            >>> ctx = Context()
            >>> # 清理单个步骤的缓存
            >>> ctx.clear_cache_for("run_001", "st_waveforms")
            >>> # 清理单个步骤及其下游缓存
            >>> ctx.clear_cache_for("run_001", "st_waveforms", downstream=True)
            >>> # 清理所有步骤的缓存
            >>> ctx.clear_cache_for("run_001")
            >>> # 只清理内存缓存
            >>> ctx.clear_cache_for("run_001", "df", clear_disk=False)
        """
        return self._cache_domain.clear_cache_for(
            run_id,
            data_name=data_name,
            downstream=downstream,
            clear_memory=clear_memory,
            clear_disk=clear_disk,
            verbose=verbose,
        )

    def _collect_downstream_data_names(
        self, data_name: str, run_id: str | None = None
    ) -> list[str]:
        """Collect all downstream data names that depend on a given data_name."""
        reverse_deps: dict[str, list[str]] = {}
        for name, plugin in self._plugins.items():
            deps = self._get_plugin_dependency_names(plugin, run_id=run_id)
            for dep in deps:
                reverse_deps.setdefault(dep, []).append(name)

        seen: set = set()
        queue = deque(reverse_deps.get(data_name, []))
        while queue:
            node = queue.popleft()
            if node in seen:
                continue
            seen.add(node)
            queue.extend(reverse_deps.get(node, []))

        return list(seen)

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
        run_id: str | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Call a storage method with run_id when supported."""
        method = getattr(storage, method_name)
        if run_id is not None and self._storage_supports_run_id(storage, method_name):
            return method(key, *args, run_id=run_id, **kwargs)
        return method(key, *args, **kwargs)

    def _storage_exists(self, storage: Any, key: str, run_id: str | None) -> bool:
        return bool(self._storage_call(storage, "exists", key, run_id))

    def _storage_list_keys(self, storage: Any, run_id: str | None) -> list[str]:
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

    def _list_channel_keys(self, storage: Any, run_id: str | None, key: str) -> list[str]:
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

    def _expects_flat_channel_array(self, name: str) -> bool:
        """Return True if data_name must be a single array with a channel field."""
        return name in self._FLAT_CHANNEL_OUTPUTS

    def _invalidate_caches_for(self, data_name: str):
        self._cache_domain.invalidate_caches_for(data_name)

    def _set_data(self, run_id: str, name: str, value: Any):
        """Internal helper to set data in _results and optionally as attribute."""
        self._results[(run_id, name)] = value

        # Record lineage hash for config change detection
        if name in self._plugins:
            key = self.key_for(run_id, name)  # Contains lineage hash
            self._results_lineage[(run_id, name)] = key

        is_generator = isinstance(value, Iterator | OneTimeGenerator) or hasattr(value, "__next__")

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

    def _load_from_disk_with_check(self, run_id: str, name: str, key: str) -> Any | None:
        return self._cache_domain.load_from_disk_with_check(run_id, name, key)

    def _is_disk_cache_valid(self, run_id: str, name: str, key: str) -> bool:
        return self._cache_domain.is_disk_cache_valid(run_id, name, key)

    def _is_cache_hit(self, run_id: str, name: str, load: bool = False) -> bool:
        return self._cache_domain.is_cache_hit(run_id, name, load=load)

    def _execute_single_plugin(
        self,
        name: str,
        run_id: str,
        data_name: str,
        kwargs: dict,
        tracker: Any | None,
        bar_name: str | None,
        skip_cache_check: bool = False,
    ) -> None:
        self._execution_domain.execute_single_plugin(
            name,
            run_id,
            data_name,
            kwargs,
            tracker,
            bar_name,
            skip_cache_check=skip_cache_check,
        )

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

    def get_performance_report(self, plugin_name: str | None = None, format: str = "text") -> Any:
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
        self, target_name: str, include_performance: bool = True, run_id: str | None = None
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

    def get_lineage(self, data_name: str, _visited: set | None = None) -> dict[str, Any]:
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

    def _get_context_config_note(self, key: str) -> str:
        """Return a human-readable note for Context-owned config entries."""
        base_note = self._CONTEXT_CONFIG_NOTES.get(key, "Context 自身消费的配置项")
        if key in self._CONTEXT_RUNTIME_KEYS:
            return base_note
        if key in self._CONTEXT_DISPLAY_DEFAULTS and key not in self.config:
            return base_note + "（默认值）"
        return base_note

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
        plugin_name: str | None = None,
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

        result: dict[str, Any] = {}

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
                        current_value = self._config_domain.resolve_config_value(plugin, opt_name)
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

    def _show_global_config(
        self,
        show_usage: bool = True,
        show_full_help: bool = False,
        run_name: str | None = None,
    ):
        """显示全局配置（表格版）"""
        # 分析配置项使用情况
        config_usage = {}  # config_key -> [plugin_names]
        plugin_specific_configs = {}  # plugin_name -> {config_key: value}
        global_configs = {}  # 纯全局配置
        context_configs = {}  # Context 自身消费的配置

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
            if key in self._CONTEXT_CONFIG_KEYS:
                context_configs[key] = value
                continue
            # 如果不在 config_usage 中，说明未被使用
            if key not in config_usage:
                unused_configs[key] = value

        context_runtime_configs = {
            "storage_dir": self.storage_dir,
        }
        for key in self._CONTEXT_RUNTIME_KEYS:
            if key in context_configs:
                continue
            value = context_runtime_configs.get(key)
            if value is not None:
                context_configs[key] = value

        for key, value in self._CONTEXT_DISPLAY_DEFAULTS.items():
            if key in context_configs:
                continue
            if key == "run_config_path":
                context_configs[key] = self._config_domain.get_default_run_config_path_template()
            else:
                context_configs[key] = value

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
            f"Context 配置项: {len(context_configs)}  未使用配置: {len(unused_configs)}"
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

        # 3. Context 配置表
        if context_configs:
            rows = []
            for key in sorted(context_configs.keys()):
                rows.append(
                    {
                        "key": key,
                        "value": self._format_display_value(context_configs[key], 80),
                        "note": self._get_context_config_note(key),
                    }
                )
            df_context = pd.DataFrame(rows).set_index("key")

            print("\n🧭 Context 配置项")
            if display is not None:
                display(df_context)
            else:
                print(df_context.to_string())

        # 4. 未使用配置表
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
        self, key: str, run_id: str | None = None, data_name: str | None = None
    ) -> int:
        return self._cache_domain.delete_disk_cache(key, run_id=run_id, data_name=data_name)

    # ===========================
    # 时间范围查询
    # ===========================

    def build_time_index(
        self,
        run_id: str,
        data_name: str,
        time_field: str | None = None,
        endtime_field: str | None = None,
        force_rebuild: bool = False,
        time_domain: str = _TIME_DOMAIN_SYSTEM_NS,
    ) -> dict[str, Any]:
        return self._time_domain.build_time_index(
            run_id,
            data_name,
            time_field=time_field,
            endtime_field=endtime_field,
            force_rebuild=force_rebuild,
            time_domain=time_domain,
        )

    def time_range(
        self,
        run_id: str,
        data_name: str,
        start_time: int | None = None,
        end_time: int | None = None,
        time_field: str | None = None,
        endtime_field: str | None = None,
        auto_build_index: bool = True,
        channel: int | HardwareChannel | tuple[int, int] | str | None = None,
        time_domain: str = _TIME_DOMAIN_SYSTEM_NS,
    ) -> np.ndarray | list[np.ndarray]:
        return self._time_domain.time_range(
            run_id,
            data_name,
            start_time=start_time,
            end_time=end_time,
            time_field=time_field,
            endtime_field=endtime_field,
            auto_build_index=auto_build_index,
            channel=channel,
            time_domain=time_domain,
        )

    def clear_time_index(self, run_id: str | None = None, data_name: str | None = None):
        self._time_domain.clear_time_index(run_id, data_name)

    def get_time_index_stats(self) -> dict[str, Any]:
        return self._time_domain.get_time_index_stats()

    def set_epoch(
        self,
        run_id: str,
        epoch: datetime | float | str,
        time_unit: str = "ns",
    ) -> None:
        self._time_domain.set_epoch(run_id, epoch, time_unit=time_unit)

    def get_epoch(self, run_id: str) -> Any | None:
        return self._time_domain.get_epoch(run_id)

    def auto_extract_epoch(
        self,
        run_id: str,
        strategy: str | None = None,
        file_paths: list[str] | None = None,
    ) -> Any:
        return self._time_domain.auto_extract_epoch(
            run_id, strategy=strategy, file_paths=file_paths
        )

    def get_data_time_range_absolute(
        self,
        run_id: str,
        data_name: str,
        start_dt: datetime | None = None,
        end_dt: datetime | None = None,
        time_field: str | None = None,
        endtime_field: str | None = None,
        auto_build_index: bool = True,
        channel: int | HardwareChannel | tuple[int, int] | str | None = None,
        auto_extract_epoch: bool = True,
        time_domain: str = _TIME_DOMAIN_SYSTEM_NS,
    ) -> np.ndarray | list[np.ndarray]:
        return self._time_domain.get_data_time_range_absolute(
            run_id,
            data_name,
            start_dt=start_dt,
            end_dt=end_dt,
            time_field=time_field,
            endtime_field=endtime_field,
            auto_build_index=auto_build_index,
            channel=channel,
            auto_extract_epoch=auto_extract_epoch,
            time_domain=time_domain,
        )

    def preview_execution(
        self,
        run_id: str,
        data_name: str,
        show_tree: bool = True,
        show_config: bool = True,
        show_cache: bool = True,
        verbose: int = 1,
    ) -> dict[str, Any]:
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
        self._config_domain.prepare_request(run_id, data_name)
        # 检查数据名称是否存在
        if data_name not in self._plugins:
            raise ValueError(
                f"数据类型 '{data_name}' 未注册。可用数据: {', '.join(self.list_provided_data())}"
            )

        # 1. 解析执行计划
        try:
            execution_plan = self._execution_domain.resolve_execution_plan(run_id, data_name)
        except Exception as e:
            print(f"✗ 无法解析依赖关系: {e}")
            return {"error": str(e)}

        # 2. 计算本次实际需要执行的步骤（cache-aware）
        needed_set = self._execution_domain.compute_needed_set(run_id, data_name, execution_plan)

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
        info: dict[str, Any],
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
        visited: set | None = None,
        run_id: str | None = None,
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

    def help(self, topic: str | None = None) -> str:
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
  • 主入口: AGENTS.md
  • 详细文档: docs/ 目录
  • 专题导航(兼容): docs/agents/INDEX.md
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
peaks_subset = ctx.time_range(
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

    def analyze_cache(self, run_id: str | None = None, verbose: bool = True) -> CacheAnalyzer:
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
        run_id: str | None = None,
        auto_fix: bool = False,
        dry_run: bool = True,
        verbose: bool = True,
    ) -> list[DiagnosticIssue]:
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
        run_id: str | None = None,
        detailed: bool = False,
        export_path: str | None = None,
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
