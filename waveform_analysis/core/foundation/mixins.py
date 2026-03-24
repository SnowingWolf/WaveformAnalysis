"""
Mixins 模块 - 框架基础功能混合类。

提供插件编排支持等扩展功能。
"""

from contextlib import nullcontext
import logging
from typing import Any


class PluginMixin:
    """Mixin for orchestrating plugins in legacy workflow."""

    def __init__(self):
        """
        初始化插件管理 Mixin

                设置插件注册和管理的数据结构。

                初始化内容:
                - _plugins: 插件字典 {provides: plugin_instance}

                Note:
                    这是一个 Mixin 类，提供插件注册和访问功能。
        """
        self._plugins: dict[str, Any] = {}

    def _invalidate_caches_for(self, data_name: str) -> None:
        """Hook for subclasses to clear caches after plugin registration."""
        return None

    def _get_plugin_depends_on(self, plugin: Any, run_id: str | None = None) -> list[Any]:
        """Return plugin dependency specs, resolving dynamically when supported."""
        if hasattr(plugin, "resolve_depends_on"):
            try:
                deps = plugin.resolve_depends_on(self, run_id=run_id)
            except TypeError:
                deps = plugin.resolve_depends_on(self)
        else:
            deps = getattr(plugin, "depends_on", []) or []
        return list(deps or [])

    def _get_plugin_dependency_names(self, plugin: Any, run_id: str | None = None) -> list[str]:
        """Return dependency names (no version specs)."""
        deps = self._get_plugin_depends_on(plugin, run_id=run_id)
        names = []
        for dep in deps:
            if hasattr(plugin, "get_dependency_name"):
                dep_name = plugin.get_dependency_name(dep)
            else:
                dep_name = dep[0] if isinstance(dep, tuple) else dep
            names.append(dep_name)
        return names

    def register_plugin_(
        self,
        plugin: Any,
        allow_override: bool = False,
        require_spec: bool = False,
    ) -> None:
        """(DONT USE THIS METHOD DIRECTLY, USE CONTEXT.REGISTER INSTEAD)
        Register a plugin instance with strict validation.

        Args:
            plugin: Plugin instance to register
            allow_override: Allow replacing existing plugin
            require_spec: Require plugin to have valid spec() or SPEC
        """

        # 1. Basic validation
        if hasattr(plugin, "validate"):
            plugin.validate()

        # 1.5 Spec validation (if required or available)
        self._validate_plugin_spec(plugin, require_spec=require_spec)

        provides = plugin.provides

        # 2. Uniqueness check
        if provides in self._plugins:
            existing = self._plugins[provides]
            same_implementation = existing.__class__ is plugin.__class__ and getattr(
                existing, "version", None
            ) == getattr(plugin, "version", None)
            if same_implementation and not allow_override:
                logger = logging.getLogger(__name__)
                logger.info(
                    "Skipping duplicate registration for '%s' from %s",
                    provides,
                    existing.__class__.__name__,
                )
                return
            if not allow_override:
                raise RuntimeError(
                    f"Plugin conflict: '{provides}' is already provided by {existing.__class__.__name__}. "
                    f"Use allow_override=True if you want to replace it."
                )
            logger = logging.getLogger(__name__)
            logger.warning(
                "Overriding plugin '%s': %s(%s) -> %s(%s) (allow_override=True)",
                provides,
                existing.__class__.__name__,
                existing.__class__.__module__,
                plugin.__class__.__name__,
                plugin.__class__.__module__,
            )

        # 3. Version compatibility check
        self._validate_plugin_dependencies(plugin)

        # 4. Record metadata
        import inspect

        plugin._registered_class = plugin.__class__.__name__
        try:
            module = inspect.getmodule(plugin.__class__)
            plugin._registered_from_module = module.__name__ if module else "unknown"
        except Exception:
            plugin._registered_from_module = "unknown"

        # 5. Register
        self._plugins[provides] = plugin

        # 6. Invalidate caches for this data type
        if hasattr(self, "_invalidate_caches_for"):
            self._invalidate_caches_for(provides)

    def _validate_plugin_dependencies(self, plugin: Any) -> None:
        """
        Validate that plugin dependencies are compatible with registered plugins.
        """
        try:
            from packaging.specifiers import SpecifierSet
            from packaging.version import Version

            PACKAGING_AVAILABLE = True
        except ImportError:
            PACKAGING_AVAILABLE = False
            return  # Skip validation if packaging not available

        for dep in self._get_plugin_depends_on(plugin):
            # Extract dependency name and version spec
            if isinstance(dep, tuple):
                dep_name, version_spec = dep
            else:
                dep_name = dep
                version_spec = None

            # Check if dependency is already registered
            if dep_name in self._plugins:
                provider = self._plugins[dep_name]

                # Validate version if spec is provided
                if version_spec and PACKAGING_AVAILABLE:
                    try:
                        provider_version = provider.semantic_version
                        if provider_version is None:
                            continue  # Skip if provider doesn't have valid version

                        spec = SpecifierSet(version_spec)
                        if provider_version not in spec:
                            raise ValueError(
                                f"Plugin '{plugin.provides}' requires '{dep_name}' {version_spec}, "
                                f"but version {provider_version} is registered"
                            )
                    except Exception as e:
                        # Log warning but don't fail - allows graceful degradation
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.warning(
                            f"Version validation failed for {plugin.provides} -> {dep_name}: {e}"
                        )

    def _validate_plugin_spec(self, plugin: Any, require_spec: bool = False) -> None:
        """Validate plugin spec if available.

        Args:
            plugin: Plugin instance
            require_spec: If True, raise error when spec is missing

        Raises:
            ValueError: If require_spec=True and spec is missing or invalid
        """
        # Check for spec() method or SPEC attribute
        spec = None
        if hasattr(plugin, "spec") and callable(plugin.spec):
            try:
                spec = plugin.spec()
            except Exception as e:
                if require_spec:
                    raise ValueError(f"Plugin '{plugin.provides}' spec() method failed: {e}") from e
                logger = logging.getLogger(__name__)
                logger.warning(f"Plugin '{plugin.provides}' spec() failed: {e}")
                return
        elif hasattr(plugin, "SPEC"):
            spec = plugin.SPEC

        if spec is None:
            if require_spec:
                raise ValueError(
                    f"Plugin '{plugin.provides}' must provide spec() method or SPEC attribute"
                )
            return

        # Validate spec structure
        from waveform_analysis.core.plugins.core.spec import PluginSpec

        if not isinstance(spec, PluginSpec):
            if require_spec:
                raise ValueError(
                    f"Plugin '{plugin.provides}' spec must be PluginSpec, got {type(spec).__name__}"
                )
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Plugin '{plugin.provides}' spec is not PluginSpec: {type(spec).__name__}"
            )
            return

        # Validate spec content
        errors = spec.validate()
        if errors:
            error_msg = f"Plugin '{plugin.provides}' spec validation failed: {'; '.join(errors)}"
            if require_spec:
                raise ValueError(error_msg)
            logger = logging.getLogger(__name__)
            logger.warning(error_msg)
            return

        # Validate consistency between spec and plugin attributes
        if spec.provides != plugin.provides:
            msg = (
                f"Plugin '{plugin.provides}' spec.provides mismatch: "
                f"spec says '{spec.provides}', plugin says '{plugin.provides}'"
            )
            if require_spec:
                raise ValueError(msg)
            logger = logging.getLogger(__name__)
            logger.warning(msg)

        # Validate config_spec keys match plugin.options
        plugin_options = set(plugin.options.keys()) if hasattr(plugin, "options") else set()
        spec_config_keys = set(spec.config_spec.keys())
        if spec_config_keys != plugin_options:
            missing_in_spec = plugin_options - spec_config_keys
            extra_in_spec = spec_config_keys - plugin_options
            parts = []
            if missing_in_spec:
                parts.append(f"missing in spec: {missing_in_spec}")
            if extra_in_spec:
                parts.append(f"extra in spec: {extra_in_spec}")
            msg = f"Plugin '{plugin.provides}' config_spec mismatch: {'; '.join(parts)}"
            if require_spec:
                raise ValueError(msg)
            logger = logging.getLogger(__name__)
            logger.warning(msg)

        # Store validated spec on plugin for later use
        plugin._validated_spec = spec

    def resolve_dependencies(self, target: str, run_id: str | None = None) -> list[str]:
        """
        Resolve dependencies and return a list of data_names to compute in order.
        Uses topological sort to determine execution order and detect cycles.
        """
        profiler = getattr(self, "profiler", None)
        with profiler.timeit("context.resolve_dependencies") if profiler else nullcontext():
            plan = []
            visited = set()
            visiting_stack = []  # Use a stack to track the path for better error messages

            def visit(node):
                if node in visiting_stack:
                    # Found a cycle!
                    cycle_path = " -> ".join(visiting_stack + [node])
                    raise RuntimeError(f"Circular dependency detected: {cycle_path}")

                if node in visited:
                    return

                if node not in self._plugins:
                    # If it's not provided by a plugin, check if it's already in memory
                    # (e.g. manually set or provided by a side-effect)
                    # If it's not a plugin and not a known attribute, it's a missing dependency
                    if not hasattr(self, node) or getattr(self, node) is None:
                        # Check memory results (this is tricky without run_id, but we can check if it's a known data name)
                        _results = getattr(self, "_results", {})
                        if not any(k[1] == node for k in _results.keys()):
                            raise ValueError(f"No plugin registered for '{node}'")

                    # If it's not a plugin, it's a leaf node (base input)
                    visited.add(node)
                    return

                visiting_stack.append(node)
                plugin = self._plugins[node]
                for dep_name in self._get_plugin_dependency_names(plugin, run_id=run_id):
                    try:
                        visit(dep_name)
                    except ValueError as e:
                        # Re-raise with path information
                        if "No plugin registered" in str(e):
                            raise ValueError(
                                f"Missing dependency: {' -> '.join(visiting_stack + [dep_name])}"
                            ) from None
                        raise

                visiting_stack.pop()
                visited.add(node)
                plan.append(node)

        if target not in self._plugins:
            # Check if it's already available
            _get_mem = getattr(self, "_get_data_from_memory", None)
            if hasattr(self, target) and getattr(self, target) is not None:
                return []
            raise ValueError(f"No plugin registered for '{target}'")

        visit(target)
        return plan
