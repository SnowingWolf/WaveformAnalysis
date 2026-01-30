"""
Strax Plugin适配器 (Phase 2.3)

提供对strax框架插件的兼容支持:
- 包装strax Plugin类
- 转换数据格式和接口
- 处理配置和依赖映射
- 支持strax的dtype和时间处理
"""

import logging
from typing import Any, Dict, List, Tuple, Type, Union

import numpy as np

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.core.base import Plugin

logger = logging.getLogger(__name__)
export, __all__ = exporter()


# ===========================
# Strax插件适配器
# ===========================


@export
class StraxPluginAdapter(Plugin):
    """
    Strax插件适配器

    将strax插件包装为本框架的Plugin,实现接口转换和兼容

    使用示例:
        # 假设有一个strax插件类
        class StraxMyPlugin:
            provides = 'my_data'
            depends_on = ('raw_records',)
            dtype = [('time', 'i8'), ('data', 'f4')]

            def compute(self, raw_records):
                # strax插件逻辑
                return processed_data

        # 创建适配器
        adapter = StraxPluginAdapter(StraxMyPlugin)

        # 注册到Context
        ctx.register(adapter())
    """

    def __init__(self, strax_plugin_class: Type):
        """
        初始化适配器

        Args:
            strax_plugin_class: strax插件类
        """
        self.strax_plugin_class = strax_plugin_class
        self.strax_plugin = strax_plugin_class()

        # 从strax插件提取元数据
        self._extract_metadata()

    def _extract_metadata(self):
        """从strax插件提取元数据"""
        # 基本属性
        self.provides = getattr(self.strax_plugin, "provides", "unknown")
        self.depends_on = getattr(self.strax_plugin, "depends_on", ())
        self.dtype = getattr(self.strax_plugin, "dtype", None)
        self.version = getattr(self.strax_plugin, "__version__", "0.1.0")

        # 配置选项 - strax使用不同的配置系统
        self._extract_config()

        # 其他strax特有属性
        self.data_kind = getattr(self.strax_plugin, "data_kind", "unknown")
        self.compressor = getattr(self.strax_plugin, "compressor", "blosc")
        self.parallel = getattr(self.strax_plugin, "parallel", False)

        logger.info(
            f"Wrapped strax plugin '{self.provides}' "
            f"(depends_on={self.depends_on}, dtype={self.dtype})"
        )

    def _extract_config(self):
        """提取strax配置选项"""
        from waveform_analysis.core.plugins.core.base import Option

        self.options = {}

        # strax使用takes_config属性
        if hasattr(self.strax_plugin, "takes_config"):
            for config_item in self.strax_plugin.takes_config:
                # config_item可能是字符串或(name, default)元组
                if isinstance(config_item, str):
                    config_name = config_item
                    config_default = None
                elif isinstance(config_item, tuple):
                    config_name = config_item[0]
                    config_default = config_item[1] if len(config_item) > 1 else None
                else:
                    continue

                # 创建Option对象
                self.options[config_name] = Option(
                    default=config_default, help=f"Strax config option: {config_name}", track=True
                )

        # config_keys是property,从options派生,不需要手动设置

    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        """
        执行计算,调用strax插件的compute方法

        Args:
            context: Context对象
            run_id: 运行ID
            **kwargs: 配置参数

        Returns:
            计算结果
        """
        try:
            # 检查compute方法签名
            import inspect

            sig = inspect.signature(self.strax_plugin.compute)
            params = list(sig.parameters.keys())

            # 移除self参数(如果是实例方法)
            if params and params[0] == "self":
                params = params[1:]

            # 准备位置参数和关键字参数
            args = []
            remaining_kwargs = {}

            # 获取依赖数据
            for i, dep in enumerate(self.depends_on):
                dep_name = dep if isinstance(dep, str) else dep[0]
                dep_data = context.get_data(run_id, dep_name)

                # 检查这个依赖是否对应一个位置参数
                if i < len(params):
                    param_name = params[i]
                    # 如果参数名匹配依赖名，作为位置参数
                    if param_name == dep_name:
                        args.append(dep_data)
                    else:
                        # 否则作为关键字参数
                        remaining_kwargs[dep_name] = dep_data
                else:
                    remaining_kwargs[dep_name] = dep_data

            # 添加配置参数 - 只添加compute方法真正接受的参数
            for config_key in self.config_keys:
                # 检查这个配置是否在compute的参数列表中
                if config_key in params:
                    # 从context获取配置
                    config_value = context.get_config(self, config_key)
                    remaining_kwargs[config_key] = config_value

            # 调用compute
            if args and remaining_kwargs:
                result = self.strax_plugin.compute(*args, **remaining_kwargs)
            elif args:
                result = self.strax_plugin.compute(*args)
            elif remaining_kwargs:
                result = self.strax_plugin.compute(**remaining_kwargs)
            else:
                result = self.strax_plugin.compute()

            return result

        except Exception as e:
            logger.error(f"Strax plugin '{self.provides}' compute failed: {e}")
            raise

    def is_compatible(self) -> bool:
        """
        检查strax插件是否兼容

        Returns:
            是否兼容
        """
        # 检查必需属性
        required_attrs = ["provides", "compute"]
        for attr in required_attrs:
            if not hasattr(self.strax_plugin, attr):
                logger.warning(f"Strax plugin missing required attribute: {attr}")
                return False

        return True


# ===========================
# Strax数据类型转换
# ===========================


@export
def strax_dtype_to_numpy(strax_dtype: Any) -> np.dtype:
    """
    将strax dtype转换为numpy dtype

    Args:
        strax_dtype: strax数据类型定义

    Returns:
        numpy dtype对象
    """
    # strax的dtype通常已经是numpy兼容的
    if isinstance(strax_dtype, np.dtype):
        return strax_dtype

    # 如果是列表或元组,尝试创建numpy dtype
    if isinstance(strax_dtype, (list, tuple)):
        try:
            return np.dtype(strax_dtype)
        except Exception as e:
            logger.warning(f"Failed to convert strax dtype to numpy: {e}")
            return None

    # 其他情况
    return None


@export
def numpy_dtype_to_strax(numpy_dtype: np.dtype) -> List[Tuple]:
    """
    将numpy dtype转换为strax兼容格式

    Args:
        numpy_dtype: numpy数据类型

    Returns:
        strax兼容的dtype定义
    """
    # strax和numpy的dtype格式通常是兼容的
    return numpy_dtype.descr


# ===========================
# Strax Context适配器
# ===========================


@export
class StraxContextAdapter:
    """
    Strax Context适配器

    提供类似strax.Context的接口,但使用我们的Context实现

    使用示例:
        # 创建适配器
        ctx = Context(storage_dir='./data')
        strax_ctx = StraxContextAdapter(ctx)

        # 使用strax风格的API
        data = strax_ctx.get_array(run_id='run_001', targets='peaks')
    """

    def __init__(self, context: Any):
        """
        初始化适配器

        Args:
            context: 我们的Context对象
        """
        self.context = context
        self.logger = logging.getLogger(self.__class__.__name__)

    def register(self, plugin_class: Type):
        """
        注册strax插件

        Args:
            plugin_class: strax插件类
        """
        # 检查是否已经是我们的Plugin
        if isinstance(plugin_class, Plugin):
            self.context.register(plugin_class)
        else:
            # 包装为适配器
            adapter = StraxPluginAdapter(plugin_class)
            if adapter.is_compatible():
                self.context.register(adapter)
            else:
                raise ValueError(f"Incompatible strax plugin: {plugin_class}")

    def get_array(
        self, run_id: str, targets: Union[str, List[str]], **kwargs
    ) -> Union[np.ndarray, Dict[str, np.ndarray]]:
        """
        获取数据数组(strax风格API)

        Args:
            run_id: 运行ID
            targets: 目标数据名称或列表
            **kwargs: 额外参数

        Returns:
            数据数组或数组字典
        """
        if isinstance(targets, str):
            # 单个目标
            return self.context.get_data(run_id, targets, **kwargs)
        else:
            # 多个目标
            results = {}
            for target in targets:
                results[target] = self.context.get_data(run_id, target, **kwargs)
            return results

    def get_df(self, run_id: str, targets: Union[str, List[str]], **kwargs):
        """
        获取DataFrame(strax风格API)

        Args:
            run_id: 运行ID
            targets: 目标数据名称或列表
            **kwargs: 额外参数

        Returns:
            DataFrame或DataFrame字典
        """
        import pandas as pd

        arrays = self.get_array(run_id, targets, **kwargs)

        def _structured_to_df(arr: np.ndarray) -> pd.DataFrame:
            """Convert structured array to DataFrame, preserving multi-dim fields as list values."""
            data = {}
            for field in arr.dtype.names or []:
                values = arr[field]
                if getattr(values, "ndim", 1) > 1:
                    data[field] = values.tolist()
                else:
                    data[field] = values
            return pd.DataFrame(data)

        if isinstance(targets, str):
            # 单个目标 - 转换为DataFrame
            if isinstance(arrays, np.ndarray):
                if arrays.dtype.names:
                    # 结构化数组
                    return _structured_to_df(arrays)
                # 普通数组
                return pd.DataFrame({"data": arrays})
            return arrays
        else:
            # 多个目标
            results = {}
            for target, arr in arrays.items():
                if isinstance(arr, np.ndarray):
                    if arr.dtype.names:
                        results[target] = _structured_to_df(arr)
                    else:
                        results[target] = pd.DataFrame({"data": arr})
                else:
                    results[target] = arr
            return results

    def set_config(self, config: Dict[str, Any]):
        """
        设置配置(strax风格API)

        Args:
            config: 配置字典
        """
        self.context.set_config(config)

    def search_field(self, pattern: str) -> List[str]:
        """
        搜索数据字段(strax风格API)

        Args:
            pattern: 搜索模式

        Returns:
            匹配的字段名列表
        """
        # 获取所有已注册的数据名称
        all_data = self.context.list_provided_data()

        # 简单的模式匹配
        import re

        regex = re.compile(pattern, re.IGNORECASE)
        return [name for name in all_data if regex.search(name)]


# ===========================
# 辅助函数
# ===========================


@export
def wrap_strax_plugin(strax_plugin_class: Type) -> Plugin:
    """
    包装strax插件为我们的Plugin

    Args:
        strax_plugin_class: strax插件类

    Returns:
        适配器实例
    """
    adapter = StraxPluginAdapter(strax_plugin_class)

    if not adapter.is_compatible():
        raise ValueError(f"Incompatible strax plugin: {strax_plugin_class}")

    return adapter


@export
def create_strax_context(storage_dir: str = "./strax_data", **kwargs) -> StraxContextAdapter:
    """
    创建strax兼容的Context

    Args:
        storage_dir: 存储目录
        **kwargs: 传递给Context的额外参数

    Returns:
        StraxContextAdapter实例

    Examples:
        >>> ctx = create_strax_context('./data')
        >>> ctx.register(MyStraxPlugin)
        >>> data = ctx.get_array('run_001', 'peaks')
    """
    from waveform_analysis.core.context import Context

    context = Context(storage_dir=storage_dir, **kwargs)
    return StraxContextAdapter(context)
