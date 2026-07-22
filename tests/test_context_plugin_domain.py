import types

import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin


class _SourceAPlugin(Plugin):
    provides = "domain_source_a"

    def compute(self, context, run_id):
        return np.array([1])


class _SourceBPlugin(Plugin):
    provides = "domain_source_b"

    def compute(self, context, run_id):
        return np.array([2])


class _RunAwarePlugin(Plugin):
    provides = "domain_target"
    depends_on = []

    def resolve_depends_on(self, context, run_id=None):
        return ["domain_source_a" if run_id == "run_a" else "domain_source_b"]

    def compute(self, context, run_id):
        return np.array([3])


class _LegacyDynamicPlugin(Plugin):
    provides = "legacy_dynamic_target"
    depends_on = []

    def resolve_depends_on(self, context):
        return ["domain_source_a"]

    def compute(self, context, run_id):
        return np.array([4])


def test_context_uses_plugin_domain_without_legacy_registration_api(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))

    assert ctx._plugin_domain.ctx is ctx
    assert not hasattr(ctx, "register_plugin_")
    assert Context.__bases__ == (object,)


def test_register_supports_nested_sequences_and_modules(tmp_path):
    class ModulePlugin(Plugin):
        provides = "module_registered"

        def compute(self, context, run_id):
            return np.array([5])

    module = types.ModuleType("context_plugin_domain_test_module")
    module.__file__ = __file__
    module.ModulePlugin = ModulePlugin

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register([_SourceAPlugin, (_SourceBPlugin(),)], module)

    assert set(ctx._plugins) == {"domain_source_a", "domain_source_b", "module_registered"}
    plugin = ctx._plugins["module_registered"]
    assert plugin._registered_class == "ModulePlugin"
    assert plugin._registered_from_module == ModulePlugin.__module__


def test_resolve_dependencies_delegates_dynamic_dependencies_with_run_id(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(_SourceAPlugin, _SourceBPlugin, _RunAwarePlugin, _LegacyDynamicPlugin)

    assert ctx.resolve_dependencies("domain_target", run_id="run_a") == [
        "domain_source_a",
        "domain_target",
    ]
    assert ctx.resolve_dependencies("domain_target", run_id="run_b") == [
        "domain_source_b",
        "domain_target",
    ]
    assert ctx.resolve_dependencies("legacy_dynamic_target", run_id="run_a") == [
        "domain_source_a",
        "legacy_dynamic_target",
    ]


def test_auto_discovery_registers_after_domains_are_initialized(tmp_path, monkeypatch):
    class DiscoveredPlugin(Plugin):
        provides = "auto_discovered"

        def compute(self, context, run_id):
            return np.array([6])

    from waveform_analysis.core.plugins.core.loader import PluginLoader

    monkeypatch.setattr(PluginLoader, "discover_all", lambda self: 1)
    monkeypatch.setattr(PluginLoader, "get_plugins", lambda self: [DiscoveredPlugin])
    monkeypatch.setattr(PluginLoader, "get_failed_plugins", lambda self: {})

    ctx = Context(storage_dir=str(tmp_path), auto_discover_plugins=True)

    assert "auto_discovered" in ctx._plugins


def test_plugin_domain_registration_invalidates_caches_on_override(tmp_path):
    class PluginV1(Plugin):
        provides = "cache_domain_target"
        version = "1.0.0"

        def compute(self, context, run_id):
            return np.array([1])

    class PluginV2(Plugin):
        provides = "cache_domain_target"
        version = "2.0.0"

        def compute(self, context, run_id):
            return np.array([2])

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PluginV1)
    ctx._execution_plan_cache["cache_domain_target"] = ["cache_domain_target"]
    ctx._lineage_cache["cache_domain_target"] = {"plugin_version": "1.0.0"}
    ctx._lineage_hash_cache["cache_domain_target"] = "old-hash"
    ctx._key_cache[("run_001", "cache_domain_target")] = "old-key"

    ctx.register(PluginV2, allow_override=True)

    assert "cache_domain_target" not in ctx._execution_plan_cache
    assert "cache_domain_target" not in ctx._lineage_cache
    assert "cache_domain_target" not in ctx._lineage_hash_cache
    assert ("run_001", "cache_domain_target") not in ctx._key_cache
