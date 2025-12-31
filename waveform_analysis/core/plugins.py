import abc
import inspect
from typing import Any, Dict, List, Literal, Optional, Type, Union

import numpy as np


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
    ):
        self.default = default
        self.type = type
        self.help = help
        self.validate = validate

    def validate_value(self, name: str, value: Any, plugin_name: str = "unknown"):
        """Validate and potentially convert the value."""
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


class Plugin(abc.ABC):
    """
    Base class for all processing plugins.
    Inspired by strax, each plugin defines what it provides and what it depends on.
    """

    provides: str = ""
    depends_on: List[str] = []
    options: Dict[str, Option] = {}
    save_when: str = "never"
    dtype: Optional[np.dtype] = None  # Legacy, use output_dtype for new plugins
    output_dtype: Optional[np.dtype] = None
    input_dtype: Dict[str, np.dtype] = {}
    output_kind: Literal["static", "stream"] = "static"
    description: str = ""
    version: str = "0.0.0"
    is_side_effect: bool = False

    # Metadata for tracking
    _registered_from_module: Optional[str] = None
    _registered_class: Optional[str] = None

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
            if not isinstance(dep, str):
                raise TypeError(f"Plugin {self.provides}: dependency '{dep}' must be a string")

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
            if dep not in self.depends_on:
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
