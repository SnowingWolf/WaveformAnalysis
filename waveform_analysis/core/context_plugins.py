"""Plugin registration and dependency orchestration for :class:`Context`."""

from contextlib import nullcontext
import inspect
import logging
from typing import Any


class ContextPluginDomain:
    """Own plugin registration, validation, and dependency resolution."""

    def __init__(self, context: Any) -> None:
        self.ctx = context

    def get_depends_on(self, plugin: Any, run_id: str | None = None) -> list[Any]:
        """Return dependency specs, resolving dynamic dependencies when supported."""
        if hasattr(plugin, "resolve_depends_on"):
            try:
                deps = plugin.resolve_depends_on(self.ctx, run_id=run_id)
            except TypeError:
                deps = plugin.resolve_depends_on(self.ctx)
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
        self.ctx._invalidate_caches_for(provides)

    def _validate_plugin_dependencies(self, plugin: Any) -> None:
        """Validate dependency versions against already registered providers."""
        try:
            from packaging.specifiers import SpecifierSet
        except ImportError:
            return

        for dep in self.get_depends_on(plugin):
            if isinstance(dep, tuple):
                dep_name, version_spec = dep
            else:
                dep_name = dep
                version_spec = None

            if dep_name not in self.ctx._plugins:
                continue

            provider = self.ctx._plugins[dep_name]
            if version_spec:
                try:
                    provider_version = provider.semantic_version
                    if provider_version is None:
                        continue
                    spec = SpecifierSet(version_spec)
                    if provider_version not in spec:
                        raise ValueError(
                            f"Plugin '{plugin.provides}' requires '{dep_name}' {version_spec}, "
                            f"but version {provider_version} is registered"
                        )
                except Exception as exc:
                    logging.getLogger(__name__).warning(
                        "Version validation failed for %s -> %s: %s",
                        plugin.provides,
                        dep_name,
                        exc,
                    )

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
                    if not hasattr(self.ctx, node) or getattr(self.ctx, node) is None:
                        results = getattr(self.ctx, "_results", {})
                        if not any(key[1] == node for key in results):
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

        if target not in self.ctx._plugins:
            if hasattr(self.ctx, target) and getattr(self.ctx, target) is not None:
                return []
            raise ValueError(f"No plugin registered for '{target}'")

        visit(target)
        return plan
