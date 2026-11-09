"""Plugin registration and dependency orchestration for :class:`Context`."""

from contextlib import nullcontext
import inspect
import logging
from typing import Any


class ContextPluginDomain:
    """Own plugin registration, validation, and dependency resolution."""

    def __init__(self, context: Any) -> None:
        self.ctx = context
        self._validated_version_requests: set[tuple[str | None, str]] = set()

    def invalidate_version_checks(self) -> None:
        self._validated_version_requests.clear()

    def get_depends_on(self, plugin: Any, run_id: str | None = None) -> list[Any]:
        """Return dependency specs, resolving dynamic dependencies when supported."""
        if hasattr(plugin, "resolve_depends_on"):
            resolver = plugin.resolve_depends_on
            try:
                inspect.signature(resolver).bind(self.ctx, run_id=run_id)
            except TypeError:
                deps = resolver(self.ctx)
            else:
                deps = resolver(self.ctx, run_id=run_id)
        else:
            deps = getattr(plugin, "depends_on", []) or []
        return list(deps or [])

    def get_dependency_names(self, plugin: Any, run_id: str | None = None) -> list[str]:
        """Return dependency names without version constraints."""
        names = []
        for dep in self.get_depends_on(plugin, run_id=run_id):
            if hasattr(plugin, "get_dependency_name"):
                dep_name = plugin.get_dependency_name(dep)
            else:
                dep_name = dep[0] if isinstance(dep, tuple) else dep
            names.append(dep_name)
        return names

    def register_plugin(
        self,
        plugin: Any,
        allow_override: bool = False,
        require_spec: bool = False,
    ) -> None:
        """Register one plugin instance with validation and cache invalidation."""
        if hasattr(plugin, "validate"):
            plugin.validate()

        self._validate_plugin_spec(plugin, require_spec=require_spec)
        provides = plugin.provides

        if provides in self.ctx._plugins:
            existing = self.ctx._plugins[provides]
            same_implementation = existing.__class__ is plugin.__class__ and getattr(
                existing, "version", None
            ) == getattr(plugin, "version", None)
            if same_implementation and not allow_override:
                logging.getLogger(__name__).info(
                    "Skipping duplicate registration for '%s' from %s",
                    provides,
                    existing.__class__.__name__,
                )
                return
            if not allow_override:
                raise RuntimeError(
                    f"Plugin conflict: '{provides}' is already provided by "
                    f"{existing.__class__.__name__}. Use allow_override=True if you want "
                    "to replace it."
                )
            logging.getLogger(__name__).warning(
                "Overriding plugin '%s': %s(%s) -> %s(%s) (allow_override=True)",
                provides,
                existing.__class__.__name__,
                existing.__class__.__module__,
                plugin.__class__.__name__,
                plugin.__class__.__module__,
            )

        self._validate_plugin_dependencies(plugin)

        plugin._registered_class = plugin.__class__.__name__
        try:
            module = inspect.getmodule(plugin.__class__)
            plugin._registered_from_module = module.__name__ if module else "unknown"
        except Exception:
            plugin._registered_from_module = "unknown"

        self.ctx._plugins[provides] = plugin
        self.invalidate_version_checks()
        self.ctx._invalidate_caches_for(provides)
        # 注册/覆盖会改变依赖关系：使 reverse_deps 缓存键失效。
        self.ctx._registry_version += 1

    def _validate_plugin_dependencies(
        self,
        plugin: Any,
        *,
        dependencies: list[Any] | None = None,
        require_registered: bool = False,
    ) -> None:
        """Validate dependency versions against already registered providers."""
        deps = self.get_depends_on(plugin) if dependencies is None else dependencies
        constraints = [dep for dep in deps if isinstance(dep, tuple)]
        if not constraints:
            return
        try:
            from packaging.specifiers import SpecifierSet
            from packaging.version import InvalidVersion, Version
        except ImportError as exc:
            raise ImportError("Dependency version constraints require 'packaging'") from exc

        for dep_name, version_spec in constraints:
            spec = SpecifierSet(version_spec)
            if dep_name not in self.ctx._plugins:
                if require_registered:
                    raise ValueError(
                        f"Plugin '{plugin.provides}' requires '{dep_name}' {version_spec}, "
                        "but no provider is registered"
                    )
                continue
            provider = self.ctx._plugins[dep_name]
            try:
                provider_version = Version(str(provider.version))
            except InvalidVersion as exc:
                raise ValueError(
                    f"Plugin '{dep_name}' has invalid version {provider.version!r}, "
                    f"required by '{plugin.provides}'"
                ) from exc
            if provider_version not in spec:
                raise ValueError(
                    f"Plugin '{plugin.provides}' requires '{dep_name}' {version_spec}, "
                    f"but version {provider_version} is registered"
                )

    def validate_request_versions(self, run_id: str | None, target: str) -> None:
        """Check reachable registered providers before returning computed or cached data."""
        cache_key = (run_id, target)
        if cache_key in self._validated_version_requests:
            return
        pending = [target]
        visited = set()
        while pending:
            name = pending.pop()
            if name in visited or name not in self.ctx._plugins:
                continue
            visited.add(name)
            plugin = self.ctx._plugins[name]
            dependencies = self.get_depends_on(plugin, run_id=run_id)
            self._validate_plugin_dependencies(
                plugin, dependencies=dependencies, require_registered=True
            )
            pending.extend(dep[0] if isinstance(dep, tuple) else dep for dep in dependencies)
        self._validated_version_requests.add(cache_key)

    def _validate_plugin_spec(self, plugin: Any, require_spec: bool = False) -> None:
        """Validate a plugin's optional :class:`PluginSpec`."""
        spec = None
        if hasattr(plugin, "spec") and callable(plugin.spec):
            try:
                spec = plugin.spec()
            except Exception as exc:
                if require_spec:
                    raise ValueError(
                        f"Plugin '{plugin.provides}' spec() method failed: {exc}"
                    ) from exc
                logging.getLogger(__name__).warning(
                    "Plugin '%s' spec() failed: %s", plugin.provides, exc
                )
                return
        elif hasattr(plugin, "SPEC"):
            spec = plugin.SPEC

        if spec is None:
            if require_spec:
                raise ValueError(
                    f"Plugin '{plugin.provides}' must provide spec() method or SPEC attribute"
                )
            return

        from waveform_analysis.core.plugins.core.spec import PluginSpec

        if not isinstance(spec, PluginSpec):
            if require_spec:
                raise ValueError(
                    f"Plugin '{plugin.provides}' spec must be PluginSpec, "
                    f"got {type(spec).__name__}"
                )
            logging.getLogger(__name__).warning(
                "Plugin '%s' spec is not PluginSpec: %s",
                plugin.provides,
                type(spec).__name__,
            )
            return

        errors = spec.validate()
        if errors:
            error_msg = f"Plugin '{plugin.provides}' spec validation failed: {'; '.join(errors)}"
            if require_spec:
                raise ValueError(error_msg)
            logging.getLogger(__name__).warning(error_msg)
            return

        if spec.provides != plugin.provides:
            msg = (
                f"Plugin '{plugin.provides}' spec.provides mismatch: "
                f"spec says '{spec.provides}', plugin says '{plugin.provides}'"
            )
            if require_spec:
                raise ValueError(msg)
            logging.getLogger(__name__).warning(msg)

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
            logging.getLogger(__name__).warning(msg)

        plugin._validated_spec = spec

    def resolve_dependencies(self, target: str, run_id: str | None = None) -> list[str]:
        """Topologically resolve a target's dependency graph and detect cycles."""
        self.validate_request_versions(run_id, target)
        profiler = getattr(self.ctx, "profiler", None)
        with profiler.timeit("context.resolve_dependencies") if profiler else nullcontext():
            plan = []
            visited = set()
            visiting_stack = []

            def visit(node: str) -> None:
                if node in visiting_stack:
                    cycle_path = " -> ".join(visiting_stack + [node])
                    raise RuntimeError(f"Circular dependency detected: {cycle_path}")
                if node in visited:
                    return
                if node not in self.ctx._plugins:
                    if run_id is None or self.ctx._get_data_from_memory(run_id, node) is None:
                        raise ValueError(f"No plugin registered for '{node}'")
                    visited.add(node)
                    return

                visiting_stack.append(node)
                plugin = self.ctx._plugins[node]
                for dep_name in self.get_dependency_names(plugin, run_id=run_id):
                    try:
                        visit(dep_name)
                    except ValueError as exc:
                        if "No plugin registered" in str(exc):
                            path = " -> ".join(visiting_stack + [dep_name])
                            raise ValueError(f"Missing dependency: {path}") from None
                        raise
                visiting_stack.pop()
                visited.add(node)
                plan.append(node)

        visit(target)
        return plan
