# -*- coding: utf-8 -*-
"""
Utils 模块 - 核心工具函数与导出管理。

本模块提供 WaveformAnalysis 框架的基础工具集，主要包括：
1. 模块 API 导出管理 (exporter)：统一管理各模块的 __all__ 导出，确保 API 规范与一致性。
2. 性能分析 (Profiler)：轻量级计时器与装饰器，用于追踪插件、计算步骤及 IO 操作的执行耗时。
3. 数据安全 (OneTimeGenerator)：封装生成器，防止在流式处理中因多次消费导致的数据丢失或静默失败。
4. 可视化配置 (LineageStyle)：定义血缘追踪图 (Lineage) 的统一视觉样式，包括节点颜色、间距与字体。
5. 插件辅助工具：提供从 Context 中提取插件元数据、DType 及显示名称的便捷函数。

它是框架内部使用的基础工具集，所有新模块必须使用本模块提供的 exporter 管理其公共接口。
"""

from collections import defaultdict
import contextlib
from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple, TypeVar

# =============================================================================
# Exporter - 模块 API 导出管理
# =============================================================================

T = TypeVar("T")
_EXPORT_SENTINEL = object()


def exporter(export_self: bool = False) -> Tuple[Any, List[str]]:
    """
    创建一个模块 API 导出管理器，类似 strax.exporter()。

    返回一个 (export, __all__) 元组：
    - export: 装饰器或函数，用于标记要导出的函数/类/常量
    - __all__: 字符串列表，包含所有被标记的名称

    用法:
        # 在模块开头
        export, __all__ = exporter()

        @export
        def my_public_function():
            pass

        @export(name="AlternativeName")
        class MyPublicClass:
            pass

        # 导出常量
        MY_CONSTANT = export(42, "MY_CONSTANT")

    Args:
        export_self: 如果为 True，将 'exporter' 加入 __all__

    Returns:
        (export, __all__) 元组
    """
    __all__: List[str] = []

    if export_self:
        __all__.append("exporter")

    def export(obj: Any = _EXPORT_SENTINEL, name: Optional[str] = None) -> Any:
        """
        导出对象。支持作为装饰器、带参数的装饰器或普通函数使用。
        """
        # 处理 @export(name="...") 情况 (作为装饰器工厂)
        if obj is _EXPORT_SENTINEL:
            return lambda o: export(o, name=name)

        # 获取导出名称
        actual_name = name or getattr(obj, "__name__", None)

        if actual_name is None:
            raise ValueError(
                f"Cannot export {obj!r}: it has no __name__ and no name was provided. "
                "For constants, use: CONST = export(value, name='CONST')"
            )

        if actual_name not in __all__:
            __all__.append(actual_name)

        return obj

    return export, __all__


# =============================================================================
# Profiler - 性能分析
# =============================================================================


class Profiler:
    """
    Lightweight profiler to track execution time of different components.
    """

    def __init__(self):
        """
        初始化性能分析器

        创建用于记录函数执行时间和调用次数的计数器。
        """
        self.durations = defaultdict(float)
        self.counts = defaultdict(int)

    @contextlib.contextmanager
    def timeit(self, key: str):
        """
        上下文管理器，用于计时代码块的执行时间。

        Args:
            key: 计时项的标识符，用于聚合多次调用的统计数据

        Yields:
            None

        Examples:
            >>> profiler = Profiler()
            >>> with profiler.timeit('data_loading'):
            ...     load_data()
            >>> print(profiler.summary())
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            self.durations[key] += time.perf_counter() - start
            self.counts[key] += 1

    def profile(self, key: Optional[str] = None):
        """
        函数装饰器，自动记录被装饰函数的执行时间。

        Args:
            key: 自定义计时项名称。如果为 None，使用函数名作为 key

        Returns:
            装饰器函数

        Examples:
            >>> profiler = Profiler()
            >>> @profiler.profile('custom_task')
            ... def my_function():
            ...     process_data()
            >>> my_function()
            >>> print(profiler.summary())
        """

        def decorator(func):
            name = key or func.__name__

            def wrapper(*args, **kwargs):
                with self.timeit(name):
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    def reset(self):
        """
        清空所有性能统计数据。

        重置累积的执行时间和调用次数，用于重新开始性能分析。

        Examples:
            >>> profiler.reset()
            >>> # 开始新的性能分析周期
        """
        self.durations.clear()
        self.counts.clear()

    def summary(self) -> str:
        """
        生成性能统计摘要报告。

        按执行时间降序排列所有计时项，显示调用次数和总耗时。

        Returns:
            格式化的性能统计报告字符串

        Examples:
            >>> print(profiler.summary())
            ============================================================
            Component / Task                         | Calls  | Total (s)
            ------------------------------------------------------------
            data_loading                             | 10     | 2.3456
            feature_extraction                       | 10     | 1.2345
            ============================================================
        """
        if not self.durations:
            return "No profiling data collected."

        lines = [
            "\n" + "=" * 60,
            f"{'Component / Task':<40} | {'Calls':<6} | {'Total (s)':<10}",
            "-" * 60,
        ]
        # Sort by duration descending
        sorted_items = sorted(self.durations.items(), key=lambda x: x[1], reverse=True)
        for key, duration in sorted_items:
            count = self.counts[key]
            lines.append(f"{key:<40} | {count:<6} | {duration:<10.4f}")
        lines.append("=" * 60)
        return "\n".join(lines)


@dataclass
class LineageStyle:
    """样式配置，供可视化与其它工具共享。"""

    node_width: float = 3.2
    node_height: float = 2.0
    header_height: float = 0.35
    port_size: float = 0.12

    x_gap: float = 4.5
    y_gap: float = 2.8

    node_bg: str = "#f5f6fa"
    node_edge: str = "#2f3640"
    header_bg: str = "#dcdde1"
    text_color: str = "#2f3640"

    type_colors: Dict[str, str] = field(
        default_factory=lambda: {
            "List[List[str]]": "#e84393",
            "List[np.ndarray]": "#f1c40f",
            "np.ndarray": "#e67e22",
            "structured": "#a0522d",
            "Unknown": "#bdc3c7",
        }
    )

    font_size_title: int = 10
    font_size_key: int = 8
    font_size_port: int = 7
    font_size_wire: int = 7
    wire_linewidth: float = 2.5
    wire_capstyle: str = "round"
    wire_joinstyle: str = "round"
    bundle_enabled: bool = True
    bundle_offset: float = 0.6
    layout_reorder: bool = True
    layout_iterations: int = 3
    auto_fit_text: bool = True
    wire_style_by_category: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "dataframe": {
                "color": "#ef6c00",
                "width": 1.6,
                "alpha": 0.55,
                "dash": "dot",
            },
            "structured": {
                "color": "#2e7d32",
                "width": 2.8,
                "alpha": 0.85,
            },
            "list_array": {
                "color": "#f1c40f",
                "width": 2.2,
                "alpha": 0.7,
                "dash": "dash",
            },
            "array": {
                "color": "#7f8c8d",
                "width": 2.0,
                "alpha": 0.7,
            },
        }
    )
    wire_style_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    port_groups: Dict[str, Dict[str, List[List[str]]]] = field(default_factory=dict)
    arrow_mutation_scale: float = 12
    wire_alpha: float = 0.8
    verbose: int = 1


class OneTimeGenerator:
    """
    A wrapper for generators that ensures they are only consumed once.
    Raises RuntimeError if __iter__ is called more than once.
    """

    def __init__(self, generator, name="Generator"):
        """
        初始化一次性生成器包装器

        包装生成器以确保只被消费一次，防止数据丢失。

        Args:
            generator: 要包装的生成器对象
            name: 生成器名称，用于错误提示（默认 "Generator"）

        Note:
            如果尝试多次迭代，将抛出 RuntimeError。
            如需多次访问，请转换为列表或使用 Context 的缓存机制。
        """
        self.generator = generator
        self.name = name
        self.consumed = False

    def __iter__(self):
        if self.consumed:
            raise RuntimeError(
                f"{self.name} has already been consumed. "
                "Generators in WaveformAnalysis are one-time use to prevent silent data loss. "
                "If you need to iterate multiple times, convert to a list or use context.get_data() "
                "which handles caching automatically."
            )
        self.consumed = True
        yield from self.generator


def get_plugins_from_context(ctx: Any) -> Dict[str, Any]:
    """
    从 Context 对象中提取插件字典。

    兼容不同版本的 Context 实现，支持 _plugins 和 plugins 两种属性名。

    Args:
        ctx: Context 实例（或任何包含插件字典的对象）

    Returns:
        插件名称到插件对象的映射字典。如果 ctx 为 None 或无插件属性，返回空字典

    Examples:
        >>> from waveform_analysis.core.context import Context
        >>> ctx = Context()
        >>> plugins = get_plugins_from_context(ctx)
        >>> print(list(plugins.keys()))
    """
    if ctx is None:
        return {}
    return getattr(ctx, "_plugins", getattr(ctx, "plugins", {}))


def get_plugin_dtypes(name: str, plugins: Dict[str, Any]) -> Tuple[str, str]:
    """
    获取插件的输入与输出数据类型信息。

    用于血缘可视化和类型检查，自动推断插件的输入输出类型。

    Args:
        name: 插件名称或数据名称
        plugins: 插件字典（通常从 Context 获取）

    Returns:
        (input_dtype, output_dtype) 元组，其中：
        - input_dtype: 输入数据类型的字符串表示（如 "List[str]" 或依赖名）
        - output_dtype: 输出数据类型的字符串表示（如 "np.ndarray" 或 dtype 描述）

    Examples:
        >>> plugins = get_plugins_from_context(ctx)
        >>> in_type, out_type = get_plugin_dtypes('waveforms', plugins)
        >>> print(f"Input: {in_type}, Output: {out_type}")
        Input: List[List[str]], Output: List[np.ndarray]
    """
    in_dtype = "None"
    out_dtype = "Unknown"

    if name == "raw_files":
        out_dtype = "List[List[str]]"
    elif name == "waveforms":
        in_dtype = "List[List[str]]"
        out_dtype = "List[np.ndarray]"
    else:
        plugin = plugins.get(name)
        if plugin:
            # 获取输出类型 (统一使用 output_dtype)
            for attr in ("output_dtype", "DTYPE"):
                val = getattr(plugin, attr, None)
                if val:
                    out_dtype = str(val)
                    break

            # 获取输入类型
            input_dtypes = getattr(plugin, "input_dtype", {})
            if input_dtypes:
                # 如果有明确的输入类型定义，则显示类型名
                in_dtype = ", ".join([str(v) for v in input_dtypes.values()])
            else:
                # 否则显示依赖项名称作为占位
                deps = getattr(plugin, "depends_on", [])
                if deps:
                    in_dtype = ", ".join(deps)

    return in_dtype, out_dtype


def get_plugin_title(name: str, info: Dict[str, Any], plugins: Dict[str, Any]) -> str:
    """
    获取插件的显示标题。

    按优先级尝试提取插件的显示名称：
    1. plugin.name
    2. plugin.plugin_name
    3. plugin.display_name
    4. plugin.__class__.__name__
    5. info.get('plugin_class')
    6. 原始 name

    Args:
        name: 插件或数据名称
        info: 血缘信息字典（包含 plugin_class 等元数据）
        plugins: 插件字典

    Returns:
        插件的显示标题字符串

    Examples:
        >>> title = get_plugin_title('waveforms', lineage_info, plugins)
        >>> print(title)
        WaveformsPlugin
    """
    plugin = plugins.get(name)
    if plugin:
        for attr in ("name", "plugin_name", "display_name"):
            val = getattr(plugin, attr, None)
            if val:
                return str(val)
        # 确保返回 str 类型
        class_name: str = plugin.__class__.__name__
        return class_name
    return str(info.get("plugin_class", name))


# =============================================================================
# Jupyter 环境检测
# =============================================================================


def is_notebook_environment() -> bool:
    """
    检测当前代码是否运行在 Jupyter Notebook/Lab 环境中。

    用于自动适配 Jupyter 环境下的特殊行为，例如：
    - 禁用信号处理（Jupyter 有自己的中断处理）
    - 使用轮询模式替代 as_completed() 避免阻塞
    - 使用 tqdm.notebook 进度条

    Returns:
        True 如果在 Jupyter Notebook/Lab 中运行，否则 False

    Examples:
        >>> if is_notebook_environment():
        ...     # Jupyter 特定逻辑
        ...     pass
    """
    try:
        from IPython.core.getipython import get_ipython

        shell = get_ipython()
        if shell is None:
            return False
        # ZMQInteractiveShell = Jupyter Notebook/Lab
        shell_name: str = shell.__class__.__name__
        is_jupyter: bool = shell_name == "ZMQInteractiveShell"
        return is_jupyter
    except (ImportError, NameError, AttributeError):
        return False


def is_ipython_environment() -> bool:
    """
    检测当前代码是否运行在任何 IPython 环境中（包括终端和 Notebook）。

    区别于 is_notebook_environment()，此函数检测所有类型的 IPython shell，
    包括 IPython 终端和 Jupyter Notebook/Lab。

    Returns:
        True 如果在任何 IPython 环境中运行，否则 False

    Examples:
        >>> if is_ipython_environment():
        ...     # IPython 特定逻辑（终端或 Notebook）
        ...     from IPython.display import display
        >>> if is_notebook_environment():
        ...     # 仅 Notebook 特定逻辑
        ...     pass

    See Also:
        is_notebook_environment(): 仅检测 Jupyter Notebook/Lab 环境
    """
    try:
        from IPython.core.getipython import get_ipython

        shell = get_ipython()
        if shell is None:
            return False
        # 任何 IPython shell 都返回 True
        shell_name: str = shell.__class__.__name__
        is_ipython: bool = shell_name in (
            "ZMQInteractiveShell",  # Jupyter Notebook/Lab
            "TerminalInteractiveShell",  # IPython 终端
        )
        return is_ipython
    except (ImportError, NameError, AttributeError):
        return False
