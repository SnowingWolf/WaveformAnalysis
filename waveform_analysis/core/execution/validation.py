# -*- coding: utf-8 -*-
"""
验证管理模块 - 提供插件配置、输入输出验证功能。

从 Context 中提取，统一管理插件的配置验证、输入 dtype 验证、
输出契约验证和 dtype 转换逻辑。
"""

# 1. Standard library imports
from typing import TYPE_CHECKING, Any, Iterator, Optional, Tuple

# 2. Third-party imports
import numpy as np

# 3. Local imports
from ..foundation.utils import OneTimeGenerator, exporter

if TYPE_CHECKING:
    from ..context import Context
    from ..plugins.core.base import Plugin

export, __all__ = exporter()


@export
class ValidationManager:
    """验证管理器

    统一管理插件的配置验证、输入输出验证和 dtype 转换。

    职责：
    - 插件配置验证（使用缓存）
    - 输入 dtype 验证
    - 输出契约验证
    - dtype 转换和验证

    Examples:
        >>> validation_manager = ValidationManager(ctx)
        >>>
        >>> # 验证插件配置
        >>> validation_manager.validate_plugin_config(plugin)
        >>>
        >>> # 验证输入 dtype
        >>> validation_manager.validate_input_dtypes(plugin, run_id)
        >>>
        >>> # 验证输出契约
        >>> result, output_kind = validation_manager.validate_output_contract(plugin, result)
        >>>
        >>> # 转换 dtype
        >>> result = validation_manager.convert_to_dtype(
        ...     result, target_dtype, plugin.provides, is_generator=False
        ... )
    """

    def __init__(self, context: 'Context'):
        """初始化 ValidationManager

        Args:
            context: Context 实例，用于访问配置和数据
        """
        self.ctx = context
        self.logger = context.logger

    def validate_plugin_config(self, plugin: 'Plugin') -> None:
        """验证插件配置（使用缓存）

        Args:
            plugin: 插件实例

        Raises:
            ValueError: 配置验证失败时
        """
        self.ctx._ensure_plugin_config_validated(plugin)

    def validate_input_dtypes(self, plugin: 'Plugin', run_id: str) -> None:
        """验证插件输入 dtype

        检查插件依赖数据的 dtype 是否与预期一致。

        Args:
            plugin: 插件实例
            run_id: 运行标识符

        Raises:
            TypeError: dtype 不匹配时
        """
        for dep_name, expected_dtype in plugin.input_dtype.items():
            dep_data = self.ctx.get_data(run_id, dep_name)
            actual_dtype = self._extract_dtype(dep_data)

            if actual_dtype is not None and actual_dtype != expected_dtype:
                raise TypeError(
                    f"Plugin '{plugin.provides}' input compatibility check failed for dependency '{dep_name}': "
                    f"Expected dtype {expected_dtype}, but got {actual_dtype}."
                )

    def validate_output_contract(
        self,
        plugin: 'Plugin',
        result: Any
    ) -> Tuple[Any, str]:
        """验证输出契约

        验证插件输出是否符合声明的 output_kind（static 或 stream）。

        Args:
            plugin: 插件实例
            result: 插件计算结果

        Returns:
            元组 (result, effective_output_kind):
            - result: 验证后的结果
            - effective_output_kind: 实际的输出类型

        Raises:
            TypeError: 输出契约违反时
        """
        is_generator = isinstance(result, (Iterator, OneTimeGenerator)) or hasattr(result, "__next__")
        effective_output_kind = plugin.output_kind

        # 自动调整：如果是 generator 但声明为 static，调整为 stream
        if is_generator and effective_output_kind == "static":
            effective_output_kind = "stream"

        # 验证契约
        if effective_output_kind == "stream" and not is_generator:
            raise TypeError(
                f"Plugin '{plugin.provides}' output contract violation: "
                f"output_kind is 'stream' but compute() returned {type(result).__name__} (not an iterator)."
            )
        if effective_output_kind == "static" and is_generator:
            raise TypeError(
                f"Plugin '{plugin.provides}' output contract violation: "
                f"output_kind is 'static' but compute() returned an iterator."
            )

        return result, effective_output_kind

    def convert_to_dtype(
        self,
        result: Any,
        target_dtype: Optional[np.dtype],
        plugin_name: str,
        is_generator: bool = False
    ) -> Any:
        """将结果转换为目标 dtype

        Args:
            result: 待转换的结果
            target_dtype: 目标 dtype
            plugin_name: 插件名称（用于错误消息）
            is_generator: 是否为 generator

        Returns:
            转换后的结果

        Raises:
            TypeError: 转换失败时
        """
        # 对于 generator 或特殊情况，跳过转换
        if is_generator:
            return result

        skip_dtype_conversion = (
            isinstance(result, list)
            and len(result) > 0
            and all(isinstance(item, np.ndarray) for item in result)
        )
        if skip_dtype_conversion:
            return result

        # 检查 target_dtype 是否为有效的 numpy dtype
        is_valid_numpy_dtype = False
        if target_dtype is not None:
            try:
                np.dtype(target_dtype)
                is_valid_numpy_dtype = True
            except (TypeError, ValueError):
                # target_dtype 不是有效的 numpy dtype (例如 "List[str]")
                # 跳过 dtype 转换
                pass

        # 执行转换
        if is_valid_numpy_dtype:
            try:
                result = np.asarray(result, dtype=target_dtype)
            except (ValueError, TypeError) as e:
                raise TypeError(
                    f"Plugin '{plugin_name}' output contract violation: "
                    f"Expected dtype {target_dtype}, but got {type(result).__name__} "
                    f"which cannot be converted. Error: {str(e)}"
                ) from e

        return result

    def _extract_dtype(self, data: Any) -> Optional[np.dtype]:
        """从数据中提取 dtype

        Args:
            data: 数据对象

        Returns:
            提取的 dtype，如果无法提取则返回 None
        """
        if isinstance(data, np.ndarray):
            return data.dtype
        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], np.ndarray):
            return data[0].dtype
        return None
