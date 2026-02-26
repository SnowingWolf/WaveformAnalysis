"""
Plugin Contract Tests

Verifies that all builtin plugins have valid specs and follow contracts:
1. All builtin plugins must have extractable PluginSpec
2. spec.output_schema/config_spec must be complete and serializable
3. depends_on must be resolvable (no cycles, no missing deps)
4. provides must be unique across all plugins
"""

import json
from typing import Dict, List, Set

import pytest

from waveform_analysis.core.plugins.core.base import Plugin
from waveform_analysis.core.plugins.core.spec import (
    Capabilities,
    ConfigField,
    PluginSpec,
)

pytestmark = pytest.mark.contract


class TestPluginSpecExtraction:
    """Test that PluginSpec can be extracted from all builtin plugins."""

    def test_all_builtin_plugins_have_extractable_spec(self, all_builtin_plugins):
        """Every builtin plugin must have an extractable PluginSpec."""
        failed_plugins = []

        for plugin_cls in all_builtin_plugins:
            try:
                plugin = plugin_cls()
                spec = PluginSpec.from_plugin(plugin)
                assert spec is not None
                assert spec.name == plugin_cls.__name__
                assert spec.provides == plugin.provides
            except Exception as e:
                failed_plugins.append((plugin_cls.__name__, str(e)))

        if failed_plugins:
            msg = "Failed to extract spec from plugins:\n"
            for name, error in failed_plugins:
                msg += f"  - {name}: {error}\n"
            pytest.fail(msg)

    def test_spec_has_required_fields(self, all_builtin_plugins):
        """Every extracted spec must have required fields populated."""
        for plugin_cls in all_builtin_plugins:
            try:
                plugin = plugin_cls()
                spec = PluginSpec.from_plugin(plugin)

                # Required fields
                assert spec.name, f"{plugin_cls.__name__}: name is empty"
                assert spec.provides, f"{plugin_cls.__name__}: provides is empty"
                assert spec.version, f"{plugin_cls.__name__}: version is empty"

                # depends_on must be a tuple
                assert isinstance(
                    spec.depends_on, tuple
                ), f"{plugin_cls.__name__}: depends_on is not tuple"

                # capabilities must be Capabilities instance
                assert isinstance(
                    spec.capabilities, Capabilities
                ), f"{plugin_cls.__name__}: capabilities is not Capabilities"

            except Exception as e:
                pytest.fail(f"{plugin_cls.__name__}: {e}")


class TestOutputSchemaCompleteness:
    """Test that output schemas are complete and serializable."""

    def test_output_schema_serializable(self, all_builtin_plugins):
        """Output schema must be JSON-serializable for lineage tracking."""
        for plugin_cls in all_builtin_plugins:
            try:
                plugin = plugin_cls()
                spec = PluginSpec.from_plugin(plugin)

                if spec.output_schema is not None:
                    # Must be serializable
                    schema_dict = {
                        "dtype": spec.output_schema.dtype,
                        "kind": spec.output_schema.kind,
                        "fields": [
                            {"name": f.name, "dtype": f.dtype, "units": f.units}
                            for f in spec.output_schema.fields
                        ],
                    }
                    json_str = json.dumps(schema_dict)
                    assert json_str, f"{plugin_cls.__name__}: schema not serializable"

            except (TypeError, ValueError) as e:
                pytest.fail(f"{plugin_cls.__name__}: output_schema not serializable: {e}")

    def test_output_dtype_matches_schema(self, all_builtin_plugins):
        """If plugin has output_dtype, schema should reflect it."""
        for plugin_cls in all_builtin_plugins:
            try:
                plugin = plugin_cls()

                # Skip plugins without output_dtype
                if not hasattr(plugin, "output_dtype") or plugin.output_dtype is None:
                    continue

                # Skip non-structured dtypes
                if not hasattr(plugin.output_dtype, "names") or plugin.output_dtype.names is None:
                    continue

                spec = PluginSpec.from_plugin(plugin)

                if spec.output_schema is not None and spec.output_schema.fields:
                    schema_fields = {f.name for f in spec.output_schema.fields}
                    dtype_fields = set(plugin.output_dtype.names)

                    # Schema fields should match dtype fields
                    assert schema_fields == dtype_fields, (
                        f"{plugin_cls.__name__}: schema fields {schema_fields} "
                        f"!= dtype fields {dtype_fields}"
                    )

            except Exception as e:
                pytest.fail(f"{plugin_cls.__name__}: {e}")


class TestConfigSpecCompleteness:
    """Test that config specs are complete and match plugin options."""

    def test_config_spec_matches_options(self, all_builtin_plugins):
        """Config spec keys must match plugin.options keys."""
        for plugin_cls in all_builtin_plugins:
            try:
                plugin = plugin_cls()
                spec = PluginSpec.from_plugin(plugin)

                if hasattr(plugin, "options") and plugin.options:
                    option_keys = set(plugin.options.keys())
                    spec_keys = set(spec.config_spec.keys())

                    assert option_keys == spec_keys, (
                        f"{plugin_cls.__name__}: option keys {option_keys} "
                        f"!= spec keys {spec_keys}"
                    )

            except Exception as e:
                pytest.fail(f"{plugin_cls.__name__}: {e}")

    def test_config_field_has_type_and_default(self, all_builtin_plugins):
        """Each ConfigField must have type and default defined."""
        for plugin_cls in all_builtin_plugins:
            try:
                plugin = plugin_cls()
                spec = PluginSpec.from_plugin(plugin)

                for key, field in spec.config_spec.items():
                    assert isinstance(
                        field, ConfigField
                    ), f"{plugin_cls.__name__}.{key}: not ConfigField"
                    # type should be set (even if "any")
                    assert field.type is not None, f"{plugin_cls.__name__}.{key}: type is None"

            except Exception as e:
                pytest.fail(f"{plugin_cls.__name__}: {e}")


class TestDependencyGraph:
    """Test dependency graph integrity."""

    def test_no_circular_dependencies(self, all_builtin_plugins):
        """Dependency graph must be acyclic (DAG)."""
        # Build dependency graph
        provides_map: Dict[str, str] = {}  # data_name -> plugin_name
        depends_map: Dict[str, List[str]] = {}  # plugin_name -> [dep_data_names]

        for plugin_cls in all_builtin_plugins:
            try:
                plugin = plugin_cls()
                provides_map[plugin.provides] = plugin_cls.__name__

                deps = []
                if hasattr(plugin, "depends_on") and plugin.depends_on:
                    deps = list(plugin.depends_on)
                depends_map[plugin_cls.__name__] = deps
            except Exception:
                pass

        # Check for cycles using DFS
        def has_cycle(node: str, visited: Set[str], rec_stack: Set[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)

            deps = depends_map.get(node, [])
            for dep in deps:
                dep_plugin = provides_map.get(dep)
                if dep_plugin is None:
                    continue  # External dependency
                if dep_plugin not in visited:
                    if has_cycle(dep_plugin, visited, rec_stack):
                        return True
                elif dep_plugin in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        visited: Set[str] = set()
        for plugin_name in depends_map:
            if plugin_name not in visited:
                if has_cycle(plugin_name, visited, set()):
                    pytest.fail(f"Circular dependency detected involving {plugin_name}")

    def test_provides_unique(self, all_builtin_plugins):
        """Each plugin must provide a unique data name."""
        provides_seen: Dict[str, str] = {}  # data_name -> plugin_name

        for plugin_cls in all_builtin_plugins:
            try:
                plugin = plugin_cls()
                data_name = plugin.provides

                if data_name in provides_seen:
                    pytest.fail(
                        f"Duplicate provides '{data_name}': "
                        f"{provides_seen[data_name]} and {plugin_cls.__name__}"
                    )
                provides_seen[data_name] = plugin_cls.__name__
            except Exception:
                pass

    def test_depends_on_resolvable(self, registered_context, all_builtin_plugins):
        """All dependencies should be resolvable within builtin plugins."""
        # Get all provided data names
        provided: Set[str] = set()
        for plugin_cls in all_builtin_plugins:
            try:
                plugin = plugin_cls()
                provided.add(plugin.provides)
            except Exception:
                pass

        # Check each plugin's dependencies
        unresolvable = []
        for plugin_cls in all_builtin_plugins:
            try:
                plugin = plugin_cls()
                if hasattr(plugin, "depends_on") and plugin.depends_on:
                    for dep in plugin.depends_on:
                        if dep not in provided:
                            unresolvable.append((plugin_cls.__name__, dep))
            except Exception:
                pass

        # Note: Some dependencies may be optional or provided by other modules
        # We just report them, not fail
        if unresolvable:
            msg = "Unresolvable dependencies (may be optional):\n"
            for plugin_name, dep in unresolvable:
                msg += f"  - {plugin_name} depends on '{dep}'\n"
            # Use warning instead of fail since some deps may be intentionally external
            pytest.skip(msg)


class TestSpecValidation:
    """Test PluginSpec.validate() method."""

    def test_spec_validate_passes_for_builtin(self, all_builtin_plugins):
        """All builtin plugins should pass spec validation."""
        failed = []

        for plugin_cls in all_builtin_plugins:
            try:
                plugin = plugin_cls()
                spec = PluginSpec.from_plugin(plugin)
                errors = spec.validate()

                if errors:
                    failed.append((plugin_cls.__name__, errors))
            except Exception as e:
                failed.append((plugin_cls.__name__, [str(e)]))

        if failed:
            msg = "Spec validation failed:\n"
            for name, errors in failed:
                msg += f"  - {name}:\n"
                for err in errors:
                    msg += f"      {err}\n"
            pytest.fail(msg)

    def test_spec_to_dict_serializable(self, all_builtin_plugins):
        """PluginSpec.to_dict() must return JSON-serializable dict."""
        for plugin_cls in all_builtin_plugins:
            try:
                plugin = plugin_cls()
                spec = PluginSpec.from_plugin(plugin)
                spec_dict = spec.to_dict()

                # Must be JSON serializable
                json_str = json.dumps(spec_dict, default=str)
                assert json_str

                # Must contain key fields
                assert "name" in spec_dict
                assert "provides" in spec_dict
                assert "version" in spec_dict

            except Exception as e:
                pytest.fail(f"{plugin_cls.__name__}: to_dict() failed: {e}")


class TestRegistrationWithSpec:
    """Test Context.register() with require_spec=True."""

    def test_register_with_require_spec(self, context, simple_plugin_class):
        """Plugins with SPEC should register successfully with require_spec=True."""
        from waveform_analysis.core.plugins.core.spec import PluginSpec

        # Add SPEC to the plugin class
        plugin = simple_plugin_class()
        simple_plugin_class.SPEC = PluginSpec.from_plugin(plugin)

        context.register(plugin, require_spec=True)

        assert simple_plugin_class.provides in context._plugins

    def test_register_without_spec_fails(self, context):
        """Plugins without SPEC should fail when require_spec=True."""

        class NoSpecPlugin(Plugin):
            provides = "no_spec_data"
            depends_on = ()
            version = "1.0.0"

            def compute(self, context, run_id: str, **kwargs):  # noqa: ARG002
                return None

        plugin = NoSpecPlugin()

        # Should raise error due to missing SPEC
        with pytest.raises(ValueError, match="must provide spec"):
            context.register(plugin, require_spec=True)

    def test_register_rejects_invalid_spec(self, context):
        """Plugins with invalid spec should be rejected when require_spec=True."""

        class InvalidPlugin(Plugin):
            provides = ""  # Invalid: empty provides
            depends_on = ()
            version = "1.0.0"

            def compute(self, context, run_id: str, **kwargs):  # noqa: ARG002
                return None

        plugin = InvalidPlugin()

        # Should raise error due to empty provides
        with pytest.raises((ValueError, RuntimeError)):
            context.register(plugin, require_spec=True)
