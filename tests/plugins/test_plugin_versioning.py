"""
测试插件版本支持功能
"""

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Option, Plugin


class TestPluginVersioning:
    """测试插件语义化版本支持"""

    def test_plugin_semantic_version(self):
        """测试插件的语义化版本属性"""

        class MyPlugin(Plugin):
            provides = "data"
            version = "1.2.3"

            def compute(self, context, run_id):
                return np.array([1])

        plugin = MyPlugin()

        # 检查semantic_version属性
        if plugin.semantic_version is not None:
            from packaging.version import Version

            assert plugin.semantic_version == Version("1.2.3")

    def test_plugin_invalid_version_fallback(self):
        """测试无效版本号会回退到0.0.0"""

        class MyPlugin(Plugin):
            provides = "data"
            version = "invalid-version"

            def compute(self, context, run_id):
                return np.array([1])

        plugin = MyPlugin()

        # 如果packaging可用，应该回退到0.0.0
        if plugin.semantic_version is not None:
            from packaging.version import Version

            assert plugin.semantic_version == Version("0.0.0")

    def test_dependency_with_version_spec(self):
        """测试带版本约束的依赖声明"""

        class ProducerPlugin(Plugin):
            provides = "input_data"
            version = "1.5.0"

            def compute(self, context, run_id):
                return np.array([1, 2, 3])

        class ConsumerPlugin(Plugin):
            provides = "output_data"
            depends_on = [("input_data", ">=1.0.0,<2.0.0")]

            def compute(self, context, run_id):
                return np.array([4, 5, 6])

        # 验证依赖格式
        consumer = ConsumerPlugin()
        consumer.validate()

        # 检查依赖提取方法
        assert consumer.get_dependency_name(("input_data", ">=1.0.0")) == "input_data"
        assert (
            consumer.get_dependency_version_spec(("input_data", ">=1.0.0,<2.0.0"))
            == ">=1.0.0,<2.0.0"
        )
        assert consumer.get_dependency_name("simple_dep") == "simple_dep"
        assert consumer.get_dependency_version_spec("simple_dep") is None

    def test_version_validation_in_context(self, tmp_path):
        """测试Context注册插件时的版本验证"""

        class ProducerPlugin(Plugin):
            provides = "data_v1"
            version = "1.0.0"

            def compute(self, context, run_id):
                return np.array([1])

        class CompatibleConsumerPlugin(Plugin):
            provides = "result"
            depends_on = [("data_v1", ">=1.0.0,<2.0.0")]

            def compute(self, context, run_id):
                return np.array([2])

        class IncompatibleConsumerPlugin(Plugin):
            provides = "result2"
            depends_on = [("data_v1", ">=2.0.0")]

            def compute(self, context, run_id):
                return np.array([3])

        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(ProducerPlugin())

        # 兼容的插件应该可以注册
        ctx.register(CompatibleConsumerPlugin())

        with pytest.raises(ValueError, match="requires 'data_v1'.*>=2.0.0"):
            ctx.register(IncompatibleConsumerPlugin())
        assert "result2" not in ctx.list_provided_data()

    def test_mixed_dependency_formats(self):
        """测试混合使用字符串和元组依赖"""

        class MixedPlugin(Plugin):
            provides = "mixed_output"
            depends_on = ["simple_dep", ("versioned_dep", ">=1.0.0"), "another_simple_dep"]

            def compute(self, context, run_id):
                return np.array([1])

        plugin = MixedPlugin()
        plugin.validate()

        # 验证依赖提取
        assert plugin.get_dependency_name("simple_dep") == "simple_dep"
        assert plugin.get_dependency_name(("versioned_dep", ">=1.0.0")) == "versioned_dep"
        assert plugin.get_dependency_version_spec(("versioned_dep", ">=1.0.0")) == ">=1.0.0"

    def test_invalid_version_spec_format(self):
        """测试无效的版本约束格式"""

        class InvalidSpecPlugin(Plugin):
            provides = "data"
            depends_on = [("dep", "invalid-spec")]

            def compute(self, context, run_id):
                return np.array([1])

        plugin = InvalidSpecPlugin()

        # 如果packaging可用，会在validate时检查版本约束格式
        try:
            plugin.validate()
        except ValueError as e:
            # 应该包含"invalid version specifier"相关信息
            assert "invalid" in str(e).lower() or "version" in str(e).lower()

    def test_dependency_tuple_validation(self):
        """测试依赖元组的格式验证"""

        # 正确的元组格式
        class ValidPlugin(Plugin):
            provides = "data"
            depends_on = [("dep", ">=1.0.0")]

            def compute(self, context, run_id):
                return np.array([1])

        ValidPlugin().validate()

        # 错误的元组长度
        class InvalidLengthPlugin(Plugin):
            provides = "data"
            depends_on = [("dep", ">=1.0.0", "extra")]

            def compute(self, context, run_id):
                return np.array([1])

        with pytest.raises(ValueError, match="dependency tuple must be"):
            InvalidLengthPlugin().validate()

        # 错误的元组类型
        class InvalidTypePlugin(Plugin):
            provides = "data"
            depends_on = [(123, ">=1.0.0")]

            def compute(self, context, run_id):
                return np.array([1])

        with pytest.raises(TypeError, match="dependency name must be a string"):
            InvalidTypePlugin().validate()


class VersionSource(Plugin):
    provides = "version_source"
    version = "1.0.0"
    output_dtype = np.dtype("i8")

    def compute(self, context, run_id):
        return np.array([1], dtype=self.output_dtype)


class VersionTarget(Plugin):
    provides = "version_target"
    depends_on = []
    output_dtype = np.dtype("i8")
    save_when = "always"
    options = {"required_version": Option(default=">=1.0.0", type=str)}

    def resolve_depends_on(self, context, run_id=None):
        version_spec = (
            ">=2.0.0" if run_id == "bad_run" else context.get_config(self, "required_version")
        )
        return [("version_source", version_spec)]

    def compute(self, context, run_id):
        return context.get_data(run_id, "version_source") + 1


class VersionRoot(Plugin):
    provides = "version_root"
    depends_on = ["version_target"]
    output_dtype = np.dtype("i8")

    def compute(self, context, run_id):
        return context.get_data(run_id, "version_target") + 1


@pytest.mark.parametrize("cache_kind", ["none", "memory", "disk"])
@pytest.mark.parametrize("target", ["version_target", "version_root"])
def test_run_specific_version_constraints_precede_cache_and_compute(tmp_path, cache_kind, target):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(VersionSource, VersionTarget, VersionRoot)
    data = np.array([99], dtype="i8")
    if cache_kind == "memory":
        ctx._set_data("bad_run", target, data)
    elif cache_kind == "disk":
        ctx.storage.save_memmap(
            ctx.key_for("bad_run", target),
            data,
            extra_metadata={"lineage": ctx.get_lineage(target)},
            run_id="bad_run",
        )

    with pytest.raises(ValueError, match="requires 'version_source'.*>=2.0.0"):
        ctx.get_data("bad_run", target)


def test_consumer_registered_before_incompatible_provider_cannot_run(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(VersionTarget)
    ctx.set_config({"required_version": ">=2.0.0"})
    ctx.register(VersionSource)

    with pytest.raises(ValueError, match="requires 'version_source'.*>=2.0.0"):
        ctx.get_data("run", "version_target")


def test_provider_override_rechecks_constraints_before_memory_hit(tmp_path):
    class SourceV2(VersionSource):
        version = "2.0.0"

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(SourceV2, VersionTarget)
    ctx.set_config({"required_version": ">=2.0.0"})
    np.testing.assert_array_equal(ctx.get_data("run", "version_target"), [2])
    ctx.register(VersionSource, allow_override=True)

    with pytest.raises(ValueError, match="requires 'version_source'.*>=2.0.0"):
        ctx.get_data("run", "version_target")


def test_config_change_rechecks_constraints_before_memory_hit(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(VersionSource, VersionTarget)
    np.testing.assert_array_equal(ctx.get_data("run", "version_target"), [2])
    ctx.set_config({"required_version": ">=2.0.0"})

    with pytest.raises(ValueError, match="requires 'version_source'.*>=2.0.0"):
        ctx.get_data("run", "version_target")


def test_compatible_memory_hits_reuse_request_version_checks(tmp_path, monkeypatch):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(VersionSource, VersionTarget)
    expected = ctx.get_data("run", "version_target")

    def unexpected_resolve(*args, **kwargs):
        raise AssertionError("warm memory hit must not resolve dependencies again")

    monkeypatch.setattr(ctx._plugin_domain, "get_depends_on", unexpected_resolve)
    np.testing.assert_array_equal(ctx.get_data("run", "version_target"), expected)


def test_unconstrained_cache_does_not_require_absent_provider(tmp_path):
    class CachedTarget(VersionTarget):
        def resolve_depends_on(self, context, run_id=None):
            return ["unregistered_source"]

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(CachedTarget)
    ctx._set_data("run", "version_target", np.array([17], dtype="i8"))

    np.testing.assert_array_equal(ctx.get_data("run", "version_target"), [17])
    with pytest.raises(ValueError, match="Missing dependency.*unregistered_source"):
        ctx.resolve_dependencies("version_target", run_id="run")


def test_execution_plan_validates_once_on_miss_and_again_on_hit(tmp_path, monkeypatch):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(VersionSource, VersionTarget)
    calls = []
    validate = ctx._plugin_domain.validate_request_versions

    def record_validation(run_id, target):
        calls.append((run_id, target))
        return validate(run_id, target)

    monkeypatch.setattr(ctx._plugin_domain, "validate_request_versions", record_validation)
    expected = ["version_source", "version_target"]
    assert ctx._execution_domain.resolve_execution_plan("run", "version_target") == expected
    assert calls == [("run", "version_target")]
    assert ctx._execution_domain.resolve_execution_plan("run", "version_target") == expected
    assert calls == [("run", "version_target"), ("run", "version_target")]


def test_cached_execution_plan_cannot_bypass_invalidated_version_check(tmp_path):
    requirement = {"value": ">=1.0.0"}

    class ChangingTarget(VersionTarget):
        def resolve_depends_on(self, context, run_id=None):
            return [("version_source", requirement["value"])]

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(VersionSource, ChangingTarget)
    np.testing.assert_array_equal(ctx.get_data("run", "version_target"), [2])
    assert ("run", "version_target") in ctx._execution_plan_cache
    requirement["value"] = ">=2.0.0"
    ctx.clear_cache_for(
        "run", "version_target", clear_memory=False, clear_disk=False, verbose=False
    )

    with pytest.raises(ValueError, match="requires 'version_source'.*>=2.0.0"):
        ctx._execution_domain.resolve_execution_plan("run", "version_target")
    with pytest.raises(ValueError, match="requires 'version_source'.*>=2.0.0"):
        ctx.get_data("run", "version_target")


def test_resolve_dependencies_requires_seed_from_requested_run(tmp_path):
    class SeededTarget(Plugin):
        provides = "seeded_target"
        depends_on = ["seed"]

        def compute(self, context, run_id):
            return context.get_data(run_id, "seed")

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(SeededTarget)
    ctx._set_data("run_a", "seed", np.array([], dtype="i8"))
    assert ctx.resolve_dependencies("seeded_target", run_id="run_a") == ["seeded_target"]
    assert ctx.resolve_dependencies("seed", run_id="run_a") == []
    with pytest.raises(ValueError, match="Missing dependency.*seed"):
        ctx.resolve_dependencies("seeded_target", run_id="run_b")
    with pytest.raises(ValueError, match="Missing dependency.*seed"):
        ctx.resolve_dependencies("seeded_target")
    ctx.clear_cache_for("run_a", "seed", clear_disk=False, verbose=False)
    ctx.seed = np.array([1])
    with pytest.raises(ValueError, match="Missing dependency.*seed"):
        ctx.resolve_dependencies("seeded_target", run_id="run_a")
    with pytest.raises(ValueError, match="No plugin registered for 'seed'"):
        ctx.resolve_dependencies("seed", run_id="run_a")


def test_constrained_invalid_provider_version_fails(tmp_path):
    class InvalidSource(VersionSource):
        version = "invalid-version"

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(InvalidSource)
    with pytest.raises(ValueError, match="[Vv]ersion"):
        ctx.register(VersionTarget)


def test_constraint_validator_unavailable_fails(tmp_path, monkeypatch):
    import sys

    from waveform_analysis.core.plugins.core import base

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(VersionSource)
    monkeypatch.setattr(base, "PACKAGING_AVAILABLE", False)
    monkeypatch.setitem(sys.modules, "packaging.specifiers", None)
    with pytest.raises(ImportError, match="packaging"):
        ctx.register(VersionTarget)


def test_dynamic_invalid_version_spec_fails_at_request(tmp_path):
    class InvalidRequestTarget(VersionTarget):
        def resolve_depends_on(self, context, run_id=None):
            return [("version_source", "invalid-spec" if run_id else ">=1.0.0")]

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(VersionSource, InvalidRequestTarget)
    with pytest.raises(ValueError, match="[Ss]pec"):
        ctx.get_data("run", "version_target")


def test_missing_constrained_provider_cannot_be_bypassed_by_memory_cache(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(VersionTarget)
    ctx._set_data("run", "version_target", np.array([99], dtype="i8"))

    with pytest.raises(ValueError, match="version_source.*no provider"):
        ctx.get_data("run", "version_target")


def test_run_config_change_invalidates_request_version_checks(tmp_path):
    import json

    class RunConfigTarget(VersionTarget):
        uses_run_config = True

        def resolve_depends_on(self, context, run_id=None):
            spec = context.get_run_config(run_id)["required_version"] if run_id else ">=1.0.0"
            return [("version_source", spec)]

    config_path = tmp_path / "run_config.json"
    config_path.write_text(json.dumps({"required_version": ">=1.0.0"}))
    ctx = Context(storage_dir=str(tmp_path / "cache"), config={"run_config_path": str(config_path)})
    ctx.register(VersionSource, RunConfigTarget)
    np.testing.assert_array_equal(ctx.get_data("run", "version_target"), [2])
    config_path.write_text(json.dumps({"required_version": ">=2.0.0"}))

    with pytest.raises(ValueError, match="requires 'version_source'.*>=2.0.0"):
        ctx.get_data("run", "version_target")


@pytest.mark.parametrize("refresh_mode", ["explicit_refresh", "readonly_external_refresh"])
def test_version_checks_follow_run_config_refresh(tmp_path, refresh_mode):
    import json
    from pathlib import Path

    from waveform_analysis.core.data import BatchProcessor

    class RunConfigTarget(VersionTarget):
        uses_run_config = True

        def resolve_depends_on(self, context, run_id=None):
            spec = context.get_run_config(run_id)["required_version"] if run_id else ">=1.0.0"
            return [("version_source", spec)]

    config_path = tmp_path / "run_config.json"
    config_path.write_text(json.dumps({"required_version": ">=1.0.0"}))
    ctx = Context(storage_dir=str(tmp_path / "cache"), config={"run_config_path": str(config_path)})
    ctx.register(VersionSource, RunConfigTarget)
    np.testing.assert_array_equal(ctx.get_data("run", "version_target"), [2])
    config_path.write_text(json.dumps({"required_version": ">=2.0.0"}))

    if refresh_mode == "explicit_refresh":
        ctx.get_run_config("run", refresh=True)
        with pytest.raises(ValueError, match="requires 'version_source'.*>=2.0.0"):
            ctx.get_data("run", "version_target")
    else:
        state_path = Path(ctx._config_domain.get_run_config_hash_state_path("run"))
        state = json.loads(state_path.read_text())
        state["run_config_hash"] = ctx._config_domain.compute_run_config_hash("run")[0]
        state_path.write_text(json.dumps(state))
        before = {
            path: (path.stat().st_size, path.stat().st_mtime_ns)
            for path in tmp_path.rglob("*")
            if path.is_file()
        }
        result = BatchProcessor(ctx).process_runs(
            ["run"],
            "version_target",
            max_workers=1,
            storage_dir_strategy="readonly",
            show_progress=False,
        )
        assert result["errors"]["run"]["type"] == "ValueError"
        assert "requires 'version_source' >=2.0.0" in result["errors"]["run"]["message"]
        after = {
            path: (path.stat().st_size, path.stat().st_mtime_ns)
            for path in tmp_path.rglob("*")
            if path.is_file()
        }
        assert after == before
        assert not ctx._cache_readonly
        with pytest.raises(ValueError, match="requires 'version_source'.*>=2.0.0"):
            ctx.get_data("run", "version_target")
