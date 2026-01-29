# -*- coding: utf-8 -*-
"""
配置系统类型定义

定义配置解析过程中使用的核心类型：
- ConfigSource: 配置值来源枚举
- ConfigValue: 单个配置值及其元信息
- ResolvedConfig: 插件完整配置集合
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ConfigSource(Enum):
    """配置值来源枚举

    标识配置值的来源，用于调试和追踪配置解析过程。

    Attributes:
        EXPLICIT: 用户显式设置的配置值
        PLUGIN_DEFAULT: 插件选项的默认值
        ADAPTER_INFERRED: 从 DAQ adapter 推断的值
        GLOBAL_DEFAULT: 全局默认值
    """
    EXPLICIT = "explicit"
    PLUGIN_DEFAULT = "plugin_default"
    ADAPTER_INFERRED = "adapter_inferred"
    GLOBAL_DEFAULT = "global_default"


@dataclass
class ConfigValue:
    """单个配置值及其元信息

    封装配置值及其来源信息，用于追踪配置解析过程。

    Attributes:
        value: 配置值
        source: 配置来源
        original_key: 原始配置键名（可能是别名）
        canonical_key: 规范化的配置键名
        inferred_from: 如果是推断值，记录推断来源（如 "vx2730.sampling_rate_hz"）

    Examples:
        >>> cv = ConfigValue(
        ...     value=500e6,
        ...     source=ConfigSource.ADAPTER_INFERRED,
        ...     original_key="sampling_rate_hz",
        ...     canonical_key="sampling_rate_hz",
        ...     inferred_from="vx2730.sampling_rate_hz"
        ... )
        >>> print(cv.summary())
        500000000.0 (inferred from vx2730.sampling_rate_hz)
    """
    value: Any
    source: ConfigSource
    original_key: str
    canonical_key: str
    inferred_from: Optional[str] = None

    def summary(self) -> str:
        """生成配置值摘要字符串"""
        value_str = repr(self.value)
        if len(value_str) > 50:
            value_str = value_str[:47] + "..."

        if self.source == ConfigSource.EXPLICIT:
            return f"{value_str} (explicit)"
        elif self.source == ConfigSource.PLUGIN_DEFAULT:
            return f"{value_str} (default)"
        elif self.source == ConfigSource.ADAPTER_INFERRED:
            if self.inferred_from:
                return f"{value_str} (inferred from {self.inferred_from})"
            return f"{value_str} (inferred)"
        elif self.source == ConfigSource.GLOBAL_DEFAULT:
            return f"{value_str} (global default)"
        return value_str

    def is_explicit(self) -> bool:
        """检查是否为显式设置的值"""
        return self.source == ConfigSource.EXPLICIT

    def is_inferred(self) -> bool:
        """检查是否为推断的值"""
        return self.source == ConfigSource.ADAPTER_INFERRED


@dataclass
class ResolvedConfig:
    """插件完整配置集合

    封装插件的所有配置值及其元信息，提供便捷的访问和展示方法。

    Attributes:
        plugin_name: 插件名称
        values: 配置值字典 {key: ConfigValue}
        adapter_name: 使用的 DAQ adapter 名称（可选）

    Examples:
        >>> resolved = resolver.resolve(plugin, adapter_name="vx2730")
        >>> print(resolved.get("sampling_rate_hz"))
        500000000.0
        >>> print(resolved.summary(verbose=True))
    """
    plugin_name: str
    values: Dict[str, ConfigValue] = field(default_factory=dict)
    adapter_name: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值

        Args:
            key: 配置键名
            default: 默认值（当键不存在时返回）

        Returns:
            配置值
        """
        if key in self.values:
            return self.values[key].value
        return default

    def get_value(self, key: str) -> Optional[ConfigValue]:
        """获取完整的 ConfigValue 对象

        Args:
            key: 配置键名

        Returns:
            ConfigValue 对象或 None
        """
        return self.values.get(key)

    def __getitem__(self, key: str) -> Any:
        """支持字典式访问"""
        if key not in self.values:
            raise KeyError(f"Config key '{key}' not found in resolved config for '{self.plugin_name}'")
        return self.values[key].value

    def __contains__(self, key: str) -> bool:
        """支持 in 操作符"""
        return key in self.values

    def keys(self) -> List[str]:
        """返回所有配置键"""
        return list(self.values.keys())

    def items(self):
        """返回 (key, value) 迭代器"""
        for key, cv in self.values.items():
            yield key, cv.value

    def to_dict(self) -> Dict[str, Any]:
        """转换为普通字典（仅包含值）

        Returns:
            配置值字典
        """
        return {key: cv.value for key, cv in self.values.items()}

    def to_lineage_dict(self, include_non_tracked: bool = False) -> Dict[str, Any]:
        """转换为 lineage 格式的字典

        用于生成数据血缘信息，默认只包含 tracked 的配置项。

        Args:
            include_non_tracked: 是否包含非追踪的配置项

        Returns:
            适用于 lineage 的配置字典
        """
        result = {}
        for key, cv in self.values.items():
            # 默认包含所有显式设置和推断的值
            if cv.source in (ConfigSource.EXPLICIT, ConfigSource.ADAPTER_INFERRED):
                result[key] = cv.value
            elif include_non_tracked:
                result[key] = cv.value
        return result

    def get_explicit_values(self) -> Dict[str, Any]:
        """获取所有显式设置的配置值

        Returns:
            显式配置值字典
        """
        return {
            key: cv.value
            for key, cv in self.values.items()
            if cv.source == ConfigSource.EXPLICIT
        }

    def get_inferred_values(self) -> Dict[str, Any]:
        """获取所有推断的配置值

        Returns:
            推断配置值字典
        """
        return {
            key: cv.value
            for key, cv in self.values.items()
            if cv.source == ConfigSource.ADAPTER_INFERRED
        }

    def get_default_values(self) -> Dict[str, Any]:
        """获取所有使用默认值的配置

        Returns:
            默认配置值字典
        """
        return {
            key: cv.value
            for key, cv in self.values.items()
            if cv.source == ConfigSource.PLUGIN_DEFAULT
        }

    def summary(self, verbose: bool = False) -> str:
        """生成配置摘要

        Args:
            verbose: 是否显示详细信息（包含来源）

        Returns:
            配置摘要字符串
        """
        lines = [f"ResolvedConfig for '{self.plugin_name}'"]
        if self.adapter_name:
            lines.append(f"  Adapter: {self.adapter_name}")
        lines.append("")

        # 按来源分组
        explicit = []
        inferred = []
        defaults = []

        for key, cv in sorted(self.values.items()):
            if cv.source == ConfigSource.EXPLICIT:
                explicit.append((key, cv))
            elif cv.source == ConfigSource.ADAPTER_INFERRED:
                inferred.append((key, cv))
            else:
                defaults.append((key, cv))

        if explicit:
            lines.append("  Explicit:")
            for key, cv in explicit:
                if verbose:
                    lines.append(f"    {key}: {cv.summary()}")
                else:
                    lines.append(f"    {key}: {cv.value!r}")

        if inferred:
            lines.append("  Inferred from adapter:")
            for key, cv in inferred:
                if verbose:
                    lines.append(f"    {key}: {cv.summary()}")
                else:
                    lines.append(f"    {key}: {cv.value!r}")

        if defaults and verbose:
            lines.append("  Defaults:")
            for key, cv in defaults:
                lines.append(f"    {key}: {cv.summary()}")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"ResolvedConfig(plugin='{self.plugin_name}', keys={list(self.values.keys())})"
