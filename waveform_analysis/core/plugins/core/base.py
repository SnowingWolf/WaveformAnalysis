# -*- coding: utf-8 -*-
"""
Plugins 模块 - 定义插件和配置选项的基类。

本模块提供了 Plugin 和 Option 类，用于构建可扩展的数据处理管道。
每个插件声明其提供的数据项 (provides) 和依赖项 (depends_on)，
由 Context 自动解析执行顺序。
"""

import abc
import logging
from typing import Any, Dict, List, Literal, Optional, Tuple, Type, Union

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()

logger = logging.getLogger(__name__)

# 尝试导入 packaging 用于语义化版本
try:
    from packaging.version import InvalidVersion, Version

    PACKAGING_AVAILABLE = True
except ImportError:
    PACKAGING_AVAILABLE = False
    Version = None
    InvalidVersion = None
    logger.warning("packaging library not available, version constraints will not work")


@export
class Option:
    """
    A configuration option for a plugin.
    """

    def __init__(
        self,
        default: Any = None,
        type: Optional[Union[Type, tuple]] = None,
        help: str = "",
        validate: Optional[callable] = None,
        track: bool = True,
    ):
        """
        初始化插件配置选项

        Args:
            default: 默认值（默认 None）
            type: 期望的类型（int, float, str, bool 等，默认 None 表示任意类型）
            help: 帮助文本，说明此选项的用途
            validate: 自定义验证函数，接收值并返回 bool（默认 None）
            track: 是否追踪此选项用于 lineage（默认 True）

        Examples:
            >>> threshold_option = Option(default=10.0, type=float, help="Hit 检测阈值")
            >>> n_channels_option = Option(default=2, type=int, help="通道数量", track=True)
        """
        self.default = default
        self.type = type
        self.help = help
        self.validate = validate
        self.track = track

    def validate_value(self, name: str, value: Any, plugin_name: str = "unknown"):
        """Validate and potentially convert the value."""
        # 如果值为 None 且默认值也为 None，允许通过（可选参数）
        if value is None and self.default is None:
            return None

        # Type conversion attempt
        if self.type is not None and not isinstance(value, self.type):
            try:
                if self.type is int:
                    value = int(value)
                elif self.type is float:
                    value = float(value)
                elif self.type is bool:
                    if isinstance(value, str):
                        value = value.lower() in ("true", "1", "yes", "on")
                    else:
                        value = bool(value)
            except (ValueError, TypeError):
                pass  # Fallback to type check below

        if self.type is not None and not isinstance(value, self.type):
            raise TypeError(
                f"Plugin '{plugin_name}' option '{name}' must be of type {self.type}, "
                f"but got {type(value).__name__} (value: {value!r})"
            )
        if self.validate is not None:
            if not self.validate(value):
                raise ValueError(f"Plugin '{plugin_name}' option '{name}' failed validation for value: {value!r}")
        return value


@export
def option(name: str, **kwargs):
    """
    Decorator to add an option to a Plugin class.
    Usage:
        @option('my_option', default=10, help='...')
        class MyPlugin(Plugin):
            ...
    """

    def decorator(cls):
        if not hasattr(cls, "options") or "options" not in cls.__dict__:
            # Ensure we have our own options dict, not sharing with parent
            cls.options = getattr(cls, "options", {}).copy()
        cls.options[name] = Option(**kwargs)
        return cls

    return decorator


@export
def takes_config(config_dict: Dict[str, Option]):
    """
    Decorator to add multiple options to a Plugin class.
    Usage:
        @takes_config({
            'opt1': Option(default=1),
            'opt2': Option(default=2)
        })
        class MyPlugin(Plugin):
            ...
    """

    def decorator(cls):
        if not hasattr(cls, "options") or "options" not in cls.__dict__:
            cls.options = getattr(cls, "options", {}).copy()
        cls.options.update(config_dict)
        return cls

    return decorator


@export
class Plugin(abc.ABC):
    """
    Base class for all processing plugins.
    Inspired by strax, each plugin defines what it provides and what it depends on.
    """

    provides: str = ""
    depends_on: List[Union[str, Tuple[str, str]]] = []  # Support version constraints
    options: Dict[str, Option] = {}
    save_when: str = "never"
    output_dtype: Optional[np.dtype] = None
    input_dtype: Dict[str, np.dtype] = {}
    output_kind: Literal["static", "stream"] = "static"
    description: str = ""
    version: str = "0.0.0"
    is_side_effect: bool = False
    timeout: Optional[float] = None  # Plugin execution timeout in seconds (None = no timeout)

    # Metadata for tracking
    _registered_from_module: Optional[str] = None
    _registered_class: Optional[str] = None

    @property
    def semantic_version(self):
        """Get semantic version object from version string."""
        if not PACKAGING_AVAILABLE:
            return None
        try:
            return Version(self.version)
        except (InvalidVersion, TypeError):
            logger.warning(f"Plugin {self.__class__.__name__} has invalid version '{self.version}', using 0.0.0")
            return Version("0.0.0")

    def get_dependency_name(self, dep: Union[str, Tuple[str, str]]) -> str:
        """从依赖规范中提取依赖名称。

        插件的依赖可以是简单的字符串（插件名），也可以是包含版本约束的元组。
        此方法统一提取依赖的名称部分。

        Args:
            dep: 依赖规范，可以是：
                - 字符串：简单的插件名，如 "waveforms"
                - 元组：(插件名, 版本约束)，如 ("waveforms", ">=1.0.0")

        Returns:
            提取的插件名称字符串

        Examples:
            >>> plugin.get_dependency_name("waveforms")
            "waveforms"
            >>> plugin.get_dependency_name(("waveforms", ">=1.0.0"))
            "waveforms"
        """
        if isinstance(dep, tuple):
            return dep[0]
        return dep

    def get_dependency_version_spec(self, dep: Union[str, Tuple[str, str]]) -> Optional[str]:
        """从依赖规范中提取版本约束。

        当依赖声明包含版本约束时（元组形式），提取版本规范字符串。
        支持 PEP 440 版本说明符，如 ">=1.0.0", "==2.1.0", "~=1.2.0" 等。

        Args:
            dep: 依赖规范，可以是：
                - 字符串：简单的插件名（无版本约束）
                - 元组：(插件名, 版本约束)

        Returns:
            版本约束字符串，如果没有约束则返回 None

        Examples:
            >>> plugin.get_dependency_version_spec("waveforms")
            None
            >>> plugin.get_dependency_version_spec(("waveforms", ">=1.0.0"))
            ">=1.0.0"
        """
        if isinstance(dep, tuple) and len(dep) > 1:
            return dep[1]
        return None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Merge options from base classes to support inheritance
        all_options = {}
        for base in reversed(cls.__mro__):
            # Collect from 'options'
            if hasattr(base, "options") and isinstance(base.options, dict):
                all_options.update(base.options)
            # Collect from 'takes_config'
            if hasattr(base, "takes_config") and isinstance(base.takes_config, dict):
                # Support strax-style takes_config attribute
                all_options.update(base.takes_config)
        cls.options = all_options

    @property
    def config_keys(self) -> List[str]:
        """List of configuration keys this plugin uses (derived from options)."""
        return list(self.options.keys())

    def validate(self):
        """
        Validate the plugin structure and configuration.
        Called during registration.
        """
        if not self.provides:
            raise ValueError(f"Plugin {self.__class__.__name__} must specify 'provides'")

        if not isinstance(self.depends_on, (list, tuple)):
            raise TypeError(
                f"Plugin {self.provides}: 'depends_on' must be a list or tuple, got {type(self.depends_on)}"
            )

        for dep in self.depends_on:
            if isinstance(dep, str):
                continue  # Simple string dependency
            elif isinstance(dep, tuple):
                if len(dep) != 2:
                    raise ValueError(
                        f"Plugin {self.provides}: dependency tuple must be (name, version_spec), got {dep}"
                    )
                dep_name, version_spec = dep
                if not isinstance(dep_name, str):
                    raise TypeError(f"Plugin {self.provides}: dependency name must be a string, got {type(dep_name)}")
                if not isinstance(version_spec, str):
                    raise TypeError(f"Plugin {self.provides}: version spec must be a string, got {type(version_spec)}")
                # Validate version spec syntax if packaging is available
                if PACKAGING_AVAILABLE:
                    try:
                        from packaging.specifiers import SpecifierSet

                        SpecifierSet(version_spec)
                    except Exception as e:
                        raise ValueError(f"Plugin {self.provides}: invalid version specifier '{version_spec}': {e}")
            else:
                raise TypeError(
                    f"Plugin {self.provides}: dependency must be a string or tuple (name, version_spec), got {type(dep)}"
                )

        if not isinstance(self.options, dict):
            raise TypeError(f"Plugin {self.provides}: 'options' must be a dict")

        # Check config_keys consistency with options
        # If config_keys is overridden, ensure all keys are in options
        for key in self.config_keys:
            if key not in self.options:
                raise ValueError(f"Plugin {self.provides}: config_key '{key}' is not defined in 'options'")

        for k, v in self.options.items():
            if not isinstance(v, Option):
                raise TypeError(f"Plugin {self.provides}: option '{k}' must be an instance of Option")

        if self.save_when not in ("never", "always", "target"):
            raise ValueError(f"Plugin {self.provides}: 'save_when' must be one of ('never', 'always', 'target')")

        # Validate output_kind
        if self.output_kind not in ("static", "stream"):
            raise ValueError(f"Plugin {self.provides}: 'output_kind' must be 'static' or 'stream'")

        # Validate dtypes
        if self.output_dtype is not None and not isinstance(self.output_dtype, (np.dtype, type)):
            # Basic check, np.dtype constructor is very flexible
            pass

        for dep, dt in self.input_dtype.items():
            # Extract dependency name if it's a tuple
            dep_names = [self.get_dependency_name(d) for d in self.depends_on]
            if dep not in dep_names:
                raise ValueError(
                    f"Plugin {self.provides}: input_dtype specified for '{dep}', but it's not in depends_on"
                )

    @abc.abstractmethod
    def compute(self, context: Any, run_id: str, **kwargs) -> Any:
        """
        The actual processing logic.
        The first argument is the running Context (contains config, cached data, etc.).
        The second argument is the run_id being processed.
        Implementations should access inputs via `context.get_data(run_id, 'input_name')`
        or using `context.get_config(self, 'option_name')`.
        Should return the data specified in 'provides'.
        """
        pass

    def on_error(self, context: Any, exception: Exception):
        """
        Optional hook called when compute() raises an exception.
        """
        pass

    def cleanup(self, context: Any):
        """
        Optional hook called after compute() finishes (successfully or not).
        Useful for releasing resources like file handles.
        """
        pass

    def __repr__(self):
        return f"Plugin({self.provides}, depends_on={self.depends_on})"
