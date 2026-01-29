# -*- coding: utf-8 -*-
"""
配置解析器

ConfigResolver 负责将配置从"入口 → 生效值"的过程统一实现。
支持多级配置来源：显式配置 > adapter 推断 > 插件默认。
"""

import logging
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

from waveform_analysis.core.foundation.utils import exporter

from .adapter_info import AdapterInfo, get_adapter_info
from .types import ConfigSource, ConfigValue, ResolvedConfig

if TYPE_CHECKING:
    from waveform_analysis.core.plugins.core.base import Plugin
    from .compat import CompatManager

export, __all__ = exporter()

logger = logging.getLogger(__name__)


@export
class ConfigResolver:
    """配置解析器

    统一处理配置值的解析过程，支持多级配置来源和 adapter 推断。

    配置合并优先级（从高到低）：
    1. 显式配置（用户通过 set_config 设置）
    2. Adapter 推断值（从 DAQ adapter 推断）
    3. 插件默认值（plugin.options[key].default）

    Attributes:
        ADAPTER_INFERRED_OPTIONS: 可从 adapter 推断的配置项映射

    Examples:
        >>> resolver = ConfigResolver()
        >>> resolved = resolver.resolve(plugin, config, adapter_name="vx2730")
        >>> print(resolved.get("sampling_rate_hz"))
        500000000.0
    """

    # 可从 adapter 推断的配置项
    # 格式: {config_key: lambda adapter_info: value}
    ADAPTER_INFERRED_OPTIONS: Dict[str, Callable[[AdapterInfo], Any]] = {
        "sampling_rate_hz": lambda info: info.sampling_rate_hz,
        # sampling_rate / fs 默认按 GHz 约定
        "sampling_rate": lambda info: (info.sampling_rate_hz / 1e9) if info.sampling_rate_hz else None,
        "fs": lambda info: (info.sampling_rate_hz / 1e9) if info.sampling_rate_hz else None,
        # 采样间隔（ns/ps）
        "sampling_interval_ns": lambda info: info.dt_ns,
        "dt_ns": lambda info: info.dt_ns,
        "dt_ps": lambda info: info.dt_ps,
        "dt": lambda info: info.dt_ns,
        "records_dt_ns": lambda info: info.dt_ns,
        "events_dt_ns": lambda info: info.dt_ns,
        "timestamp_unit": lambda info: info.timestamp_unit,
        "expected_samples": lambda info: info.expected_samples,
    }

    def __init__(self, compat_manager: Optional["CompatManager"] = None):
        """初始化配置解析器

        Args:
            compat_manager: 兼容层管理器（可选）
        """
        self._compat_manager = compat_manager

    def resolve(
        self,
        plugin: "Plugin",
        config: Dict[str, Any],
        adapter_name: Optional[str] = None,
        adapter_info: Optional[AdapterInfo] = None,
    ) -> ResolvedConfig:
        """解析插件配置

        Args:
            plugin: 目标插件实例
            config: 全局配置字典
            adapter_name: DAQ adapter 名称（可选）
            adapter_info: 预先获取的 AdapterInfo（可选，优先使用）

        Returns:
            ResolvedConfig 实例，包含所有解析后的配置值

        Examples:
            >>> resolved = resolver.resolve(plugin, ctx.config, adapter_name="vx2730")
            >>> print(resolved.summary(verbose=True))
        """
        plugin_name = plugin.provides
        values: Dict[str, ConfigValue] = {}

        # 获取 adapter 信息
        if adapter_info is None and adapter_name:
            adapter_info = get_adapter_info(adapter_name)

        # 解析每个配置选项
        for opt_name, option in plugin.options.items():
            # 处理别名（插件 option 的 canonical 化）
            canonical_name = opt_name
            if self._compat_manager:
                mapped_name, _ = self._compat_manager.resolve_alias(plugin_name, opt_name)
                if mapped_name in plugin.options:
                    canonical_name = mapped_name

            # 按优先级查找配置值（支持 alias 输入）
            value, source, inferred_from, original_name = self._resolve_single_value(
                plugin_name=plugin_name,
                opt_name=canonical_name,
                option=option,
                config=config,
                adapter_info=adapter_info,
            )

            # 验证并转换值
            validated_value = option.validate_value(
                canonical_name, value, plugin_name=plugin_name
            )

            # 如果使用别名且已弃用，发出警告
            if (
                self._compat_manager
                and original_name != canonical_name
                and self._compat_manager.is_deprecated(original_name)
            ):
                self._compat_manager.warn_deprecation(original_name, plugin_name)

            values[canonical_name] = ConfigValue(
                value=validated_value,
                source=source,
                original_key=original_name,
                canonical_key=canonical_name,
                inferred_from=inferred_from,
            )

        return ResolvedConfig(
            plugin_name=plugin_name,
            values=values,
            adapter_name=adapter_name or (adapter_info.name if adapter_info else None),
        )

    def _resolve_single_value(
        self,
        plugin_name: str,
        opt_name: str,
        option: Any,
        config: Dict[str, Any],
        adapter_info: Optional[AdapterInfo],
    ) -> tuple:
        """解析单个配置值

        Args:
            plugin_name: 插件名称
            opt_name: 配置选项名称
            option: Option 对象
            config: 全局配置字典
            adapter_info: Adapter 信息

        Returns:
            (value, source, inferred_from, original_key) 元组
        """
        # 1. 检查显式配置（支持 alias 输入）
        names_to_check = [opt_name]
        if self._compat_manager:
            aliases = self._compat_manager.get_aliases_for(plugin_name, opt_name)
            for alias in aliases:
                if alias not in names_to_check:
                    names_to_check.append(alias)

        if plugin_name in config and isinstance(config[plugin_name], dict):
            for name in names_to_check:
                if name in config[plugin_name]:
                    return (
                        config[plugin_name][name],
                        ConfigSource.EXPLICIT,
                        None,
                        name,
                    )

        for name in names_to_check:
            dotted_key = f"{plugin_name}.{name}"
            if dotted_key in config:
                return (config[dotted_key], ConfigSource.EXPLICIT, None, name)

        for name in names_to_check:
            if name in config:
                return (config[name], ConfigSource.EXPLICIT, None, name)

        # 2. 检查 adapter 推断
        if adapter_info and opt_name in self.ADAPTER_INFERRED_OPTIONS:
            infer_func = self.ADAPTER_INFERRED_OPTIONS[opt_name]
            inferred_value = infer_func(adapter_info)
            if inferred_value is not None:
                return (
                    inferred_value,
                    ConfigSource.ADAPTER_INFERRED,
                    f"{adapter_info.name}.{opt_name}",
                    opt_name,
                )

        # 3. 使用插件默认值
        return (option.default, ConfigSource.PLUGIN_DEFAULT, None, opt_name)

    def resolve_value(
        self,
        plugin: "Plugin",
        name: str,
        config: Dict[str, Any],
        adapter_name: Optional[str] = None,
    ) -> ConfigValue:
        """解析单个配置值（便捷方法）

        Args:
            plugin: 目标插件
            name: 配置选项名称
            config: 全局配置字典
            adapter_name: DAQ adapter 名称

        Returns:
            ConfigValue 实例
        """
        canonical_name = name
        if self._compat_manager:
            canonical_name, _ = self._compat_manager.resolve_alias(plugin.provides, name)

        if canonical_name not in plugin.options:
            if name in plugin.options:
                canonical_name = name
            else:
                raise KeyError(f"Plugin '{plugin.provides}' does not have option '{name}'")

        adapter_info = get_adapter_info(adapter_name) if adapter_name else None
        option = plugin.options[canonical_name]

        value, source, inferred_from, original_name = self._resolve_single_value(
            plugin_name=plugin.provides,
            opt_name=canonical_name,
            option=option,
            config=config,
            adapter_info=adapter_info,
        )

        validated_value = option.validate_value(canonical_name, value, plugin_name=plugin.provides)

        if (
            self._compat_manager
            and original_name != canonical_name
            and self._compat_manager.is_deprecated(original_name)
        ):
            self._compat_manager.warn_deprecation(original_name, plugin.provides)

        return ConfigValue(
            value=validated_value,
            source=source,
            original_key=original_name,
            canonical_key=canonical_name,
            inferred_from=inferred_from,
        )

    @classmethod
    def register_inferred_option(
        cls,
        key: str,
        extractor: Callable[[AdapterInfo], Any],
    ) -> None:
        """注册可推断的配置项

        Args:
            key: 配置键名
            extractor: 从 AdapterInfo 提取值的函数

        Examples:
            >>> ConfigResolver.register_inferred_option(
            ...     "my_rate",
            ...     lambda info: info.sampling_rate_hz / 2
            ... )
        """
        cls.ADAPTER_INFERRED_OPTIONS[key] = extractor

    @classmethod
    def unregister_inferred_option(cls, key: str) -> bool:
        """注销可推断的配置项

        Args:
            key: 配置键名

        Returns:
            是否成功注销
        """
        if key in cls.ADAPTER_INFERRED_OPTIONS:
            del cls.ADAPTER_INFERRED_OPTIONS[key]
            return True
        return False

    @classmethod
    def list_inferred_options(cls) -> list:
        """列出所有可推断的配置项

        Returns:
            配置键名列表
        """
        return list(cls.ADAPTER_INFERRED_OPTIONS.keys())

