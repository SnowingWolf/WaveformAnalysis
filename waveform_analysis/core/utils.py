import contextlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

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
        self.durations = defaultdict(float)
        self.counts = defaultdict(int)

    @contextlib.contextmanager
    def timeit(self, key: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.durations[key] += time.perf_counter() - start
            self.counts[key] += 1

    def profile(self, key: Optional[str] = None):
        """
        Decorator to profile a function.
        """

        def decorator(func):
            name = key or func.__name__

            def wrapper(*args, **kwargs):
                with self.timeit(name):
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    def reset(self):
        self.durations.clear()
        self.counts.clear()

    def summary(self) -> str:
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
    arrow_mutation_scale: float = 12
    wire_alpha: float = 0.8
    verbose: int = 1


class OneTimeGenerator:
    """
    A wrapper for generators that ensures they are only consumed once.
    Raises RuntimeError if __iter__ is called more than once.
    """

    def __init__(self, generator, name="Generator"):
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
    if ctx is None:
        return {}
    return getattr(ctx, "_plugins", getattr(ctx, "plugins", {}))


def get_plugin_dtype(name: str, plugins: Dict[str, Any]) -> str:
    if name == "raw_files":
        return "List[List[str]]"
    if name == "waveforms":
        return "List[np.ndarray]"
    plugin = plugins.get(name)
    if plugin:
        for attr in ("dtype", "output_dtype", "DTYPE"):
            val = getattr(plugin, attr, None)
            if val:
                return str(val)
    return "Unknown"


def get_plugin_title(name: str, info: Dict[str, Any], plugins: Dict[str, Any]) -> str:
    plugin = plugins.get(name)
    if plugin:
        for attr in ("name", "plugin_name", "display_name"):
            val = getattr(plugin, attr, None)
            if val:
                return str(val)
        return plugin.__class__.__name__
    return str(info.get("plugin_class", name))
