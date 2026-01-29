# -*- coding: utf-8 -*-
"""
兼容层管理器

CompatManager 负责集中管理参数别名和弃用信息，
确保配置系统的向后兼容性。
"""

import warnings
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


def _parse_version(version: str) -> Tuple[int, ...]:
    """解析版本字符串为元组

    Args:
        version: 版本字符串，如 "1.2.3"

    Returns:
        版本元组，如 (1, 2, 3)
    """
    parts = []
    for part in version.split("."):
        # 处理可能的预发布标识，如 "1.0.0a1"
        numeric = ""
        for char in part:
            if char.isdigit():
                numeric += char
            else:
                break
        parts.append(int(numeric) if numeric else 0)
    return tuple(parts)


def _compare_versions(v1: str, v2: str) -> int:
    """比较两个版本字符串

    Args:
        v1: 第一个版本
        v2: 第二个版本

    Returns:
        -1 如果 v1 < v2
         0 如果 v1 == v2
         1 如果 v1 > v2
    """
    t1 = _parse_version(v1)
    t2 = _parse_version(v2)

    # 补齐长度
    max_len = max(len(t1), len(t2))
    t1 = t1 + (0,) * (max_len - len(t1))
    t2 = t2 + (0,) * (max_len - len(t2))

    if t1 < t2:
        return -1
    elif t1 > t2:
        return 1
    return 0


@export
def get_current_version() -> str:
    """获取当前 waveform_analysis 版本

    Returns:
        版本字符串
    """
    from waveform_analysis import __version__
    return __version__


@export
@dataclass
class DeprecationInfo:
    """弃用信息

    Attributes:
        old_name: 旧名称（已弃用）
        new_name: 新名称（推荐使用）
        deprecated_in: 弃用版本
        removed_in: 计划移除版本
        message: 自定义弃用消息（可选）
    """
    old_name: str
    new_name: str
    deprecated_in: str
    removed_in: str
    message: Optional[str] = None

    def get_warning_message(self) -> str:
        """生成弃用警告消息"""
        if self.message:
            return self.message
        return (
            f"'{self.old_name}' is deprecated since version {self.deprecated_in} "
            f"and will be removed in version {self.removed_in}. "
            f"Use '{self.new_name}' instead."
        )


@export
class CompatManager:
    """兼容层管理器

    集中管理参数别名和弃用信息，提供统一的兼容性处理接口。

    Attributes:
        PARAM_ALIASES: 参数别名注册表
        DEPRECATIONS: 弃用信息列表

    Examples:
        >>> manager = CompatManager()
        >>> canonical, alias_used = manager.resolve_alias("peaks", "break_threshold_ns")
        >>> if alias_used:
        ...     manager.warn_deprecation("break_threshold_ns", "peaks")
    """

    # 参数别名注册表
    # 格式: {plugin_name: {old_name: new_name}, "__global__": {old_name: new_name}}
    PARAM_ALIASES: Dict[str, Dict[str, str]] = {
        "__global__": {
            "break_threshold_ns": "break_threshold_ps",
        },
    }

    # 弃用信息列表
    DEPRECATIONS: List[DeprecationInfo] = [
        DeprecationInfo(
            old_name="break_threshold_ns",
            new_name="break_threshold_ps",
            deprecated_in="1.1.0",
            removed_in="2.0.0",
        ),
        DeprecationInfo(
            old_name="builtin.signal_processing",
            new_name="builtin.cpu",
            deprecated_in="1.2.0",
            removed_in="2.0.0",
            message="Plugin module 'builtin.signal_processing' has been renamed to 'builtin.cpu'.",
        ),
    ]

    def __init__(self):
        """初始化兼容层管理器

        Note:
            弃用信息直接从类属性 DEPRECATIONS 读取，
            因此 register_deprecation() 可在实例化后调用。
        """
        pass

    def _get_deprecation_index(self) -> Dict[str, DeprecationInfo]:
        """获取弃用信息索引（动态构建）

        Returns:
            {old_name: DeprecationInfo} 字典
        """
        return {d.old_name: d for d in self.DEPRECATIONS}

    def resolve_alias(
        self,
        plugin_name: str,
        param_name: str,
    ) -> Tuple[str, bool]:
        """解析参数别名

        Args:
            plugin_name: 插件名称
            param_name: 参数名称

        Returns:
            (canonical_name, alias_used) 元组
            - canonical_name: 规范化的参数名
            - alias_used: 是否使用了别名

        Examples:
            >>> manager = CompatManager()
            >>> name, used = manager.resolve_alias("peaks", "break_threshold_ns")
            >>> print(name, used)
            break_threshold_ps True
        """
        # 1. 检查插件特定别名
        if plugin_name in self.PARAM_ALIASES:
            plugin_aliases = self.PARAM_ALIASES[plugin_name]
            if param_name in plugin_aliases:
                return (plugin_aliases[param_name], True)

        # 2. 检查全局别名
        global_aliases = self.PARAM_ALIASES.get("__global__", {})
        if param_name in global_aliases:
            return (global_aliases[param_name], True)

        # 3. 无别名，返回原名
        return (param_name, False)

    def get_aliases_for(self, plugin_name: str, canonical_name: str) -> List[str]:
        """列出某个规范名对应的旧别名

        Args:
            plugin_name: 插件名称
            canonical_name: 规范化参数名

        Returns:
            旧参数名列表
        """
        aliases: List[str] = []

        # 插件级别别名
        plugin_aliases = self.PARAM_ALIASES.get(plugin_name, {})
        for old_name, new_name in plugin_aliases.items():
            if new_name == canonical_name:
                aliases.append(old_name)

        # 全局别名
        global_aliases = self.PARAM_ALIASES.get("__global__", {})
        for old_name, new_name in global_aliases.items():
            if new_name == canonical_name:
                aliases.append(old_name)

        return aliases

    def warn_deprecation(
        self,
        old_name: str,
        context: Optional[str] = None,
        stacklevel: int = 2,
    ) -> None:
        """发出弃用警告或抛出错误

        当前版本 < removed_in 时发出 DeprecationWarning，
        当前版本 >= removed_in 时抛出 ValueError。

        Args:
            old_name: 已弃用的名称
            context: 上下文信息（如插件名）
            stacklevel: 警告堆栈级别

        Raises:
            ValueError: 当前版本已超过 removed_in 版本

        Examples:
            >>> manager = CompatManager()
            >>> manager.warn_deprecation("break_threshold_ns", "peaks")
        """
        deprecation_index = self._get_deprecation_index()
        if old_name not in deprecation_index:
            return

        info = deprecation_index[old_name]
        current_version = get_current_version()

        # 版本已过期，抛出错误
        if _compare_versions(current_version, info.removed_in) >= 0:
            ctx_prefix = f"[{context}] " if context else ""
            raise ValueError(
                f"{ctx_prefix}'{old_name}' was removed in version {info.removed_in}. "
                f"Use '{info.new_name}' instead."
            )

        # 版本未过期，发出警告
        message = info.get_warning_message()

        if context:
            message = f"[{context}] {message}"

        warnings.warn(message, DeprecationWarning, stacklevel=stacklevel + 1)

    def is_deprecated(self, name: str) -> bool:
        """检查名称是否已弃用

        Args:
            name: 要检查的名称

        Returns:
            是否已弃用
        """
        return name in self._get_deprecation_index()

    def get_deprecation_info(self, name: str) -> Optional[DeprecationInfo]:
        """获取弃用信息

        Args:
            name: 已弃用的名称

        Returns:
            DeprecationInfo 或 None
        """
        return self._get_deprecation_index().get(name)

    @classmethod
    def register_alias(
        cls,
        old_name: str,
        new_name: str,
        plugin_name: str = "__global__",
    ) -> None:
        """注册参数别名

        Args:
            old_name: 旧名称
            new_name: 新名称
            plugin_name: 插件名称（默认为全局）

        Examples:
            >>> CompatManager.register_alias("old_param", "new_param", "my_plugin")
        """
        if plugin_name not in cls.PARAM_ALIASES:
            cls.PARAM_ALIASES[plugin_name] = {}
        cls.PARAM_ALIASES[plugin_name][old_name] = new_name

    @classmethod
    def register_deprecation(cls, info: DeprecationInfo) -> None:
        """注册弃用信息

        Args:
            info: DeprecationInfo 实例

        Examples:
            >>> CompatManager.register_deprecation(DeprecationInfo(
            ...     old_name="old_func",
            ...     new_name="new_func",
            ...     deprecated_in="1.0.0",
            ...     removed_in="2.0.0"
            ... ))
        """
        # 避免重复
        for existing in cls.DEPRECATIONS:
            if existing.old_name == info.old_name:
                return
        cls.DEPRECATIONS.append(info)

    @classmethod
    def unregister_alias(cls, old_name: str, plugin_name: str = "__global__") -> bool:
        """注销参数别名

        Args:
            old_name: 旧名称
            plugin_name: 插件名称

        Returns:
            是否成功注销
        """
        if plugin_name in cls.PARAM_ALIASES:
            if old_name in cls.PARAM_ALIASES[plugin_name]:
                del cls.PARAM_ALIASES[plugin_name][old_name]
                return True
        return False

    def list_aliases(self, plugin_name: Optional[str] = None) -> Dict[str, str]:
        """列出别名

        Args:
            plugin_name: 插件名称（None 表示全局）

        Returns:
            别名字典 {old_name: new_name}
        """
        if plugin_name:
            return dict(self.PARAM_ALIASES.get(plugin_name, {}))
        return dict(self.PARAM_ALIASES.get("__global__", {}))

    def list_deprecations(self) -> List[DeprecationInfo]:
        """列出所有弃用信息

        Returns:
            DeprecationInfo 列表
        """
        return list(self.DEPRECATIONS)

    def summary(self) -> str:
        """生成兼容层摘要

        Returns:
            摘要字符串
        """
        lines = ["CompatManager Summary", "=" * 40]

        # 别名
        lines.append("\nParameter Aliases:")
        for plugin, aliases in self.PARAM_ALIASES.items():
            if aliases:
                lines.append(f"  [{plugin}]")
                for old, new in aliases.items():
                    lines.append(f"    {old} -> {new}")

        # 弃用
        lines.append("\nDeprecations:")
        for info in self.DEPRECATIONS:
            lines.append(
                f"  {info.old_name} -> {info.new_name} "
                f"(deprecated in {info.deprecated_in}, removed in {info.removed_in})"
            )

        return "\n".join(lines)


# 全局单例（可选使用）
_default_compat_manager: Optional[CompatManager] = None


@export
def get_default_compat_manager() -> CompatManager:
    """获取默认的兼容层管理器（单例）

    Returns:
        CompatManager 实例
    """
    global _default_compat_manager
    if _default_compat_manager is None:
        _default_compat_manager = CompatManager()
    return _default_compat_manager
