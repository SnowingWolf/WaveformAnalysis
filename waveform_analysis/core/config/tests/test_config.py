# -*- coding: utf-8 -*-
"""
配置系统单元测试

测试 ConfigResolver, CompatManager, AdapterInfo 等核心组件。
"""

import pytest
import warnings

from waveform_analysis.core.config import (
    AdapterInfo,
    CompatManager,
    ConfigResolver,
    ConfigSource,
    ConfigValue,
    DeprecationInfo,
    ResolvedConfig,
    get_adapter_info,
)
from waveform_analysis.core.plugins.core.base import Option, Plugin


# ============================================================================
# Fixtures
# ============================================================================


class MockPlugin(Plugin):
    """测试用的模拟插件"""
    provides = "mock_plugin"
    depends_on = []
    options = {
        "sampling_rate_hz": Option(default=250e6, type=float, help="采样率"),
        "dt_ns": Option(default=4, type=int, help="采样间隔（ns）"),
        "threshold": Option(default=50, type=int, help="阈值"),
        "name": Option(default="default", type=str, help="名称"),
    }

    def compute(self, context, run_id, **kwargs):
        return None


@pytest.fixture
def mock_plugin():
    return MockPlugin()


@pytest.fixture
def resolver():
    return ConfigResolver()


@pytest.fixture
def compat_manager():
    return CompatManager()


# ============================================================================
# ConfigSource Tests
# ============================================================================


class TestConfigSource:
    """ConfigSource 枚举测试"""

    def test_enum_values(self):
        assert ConfigSource.EXPLICIT.value == "explicit"
        assert ConfigSource.PLUGIN_DEFAULT.value == "plugin_default"
        assert ConfigSource.ADAPTER_INFERRED.value == "adapter_inferred"
        assert ConfigSource.GLOBAL_DEFAULT.value == "global_default"


# ============================================================================
# ConfigValue Tests
# ============================================================================


class TestConfigValue:
    """ConfigValue 数据类测试"""

    def test_basic_creation(self):
        cv = ConfigValue(
            value=100,
            source=ConfigSource.EXPLICIT,
            original_key="threshold",
            canonical_key="threshold",
        )
        assert cv.value == 100
        assert cv.source == ConfigSource.EXPLICIT
        assert cv.is_explicit()
        assert not cv.is_inferred()

    def test_inferred_value(self):
        cv = ConfigValue(
            value=500e6,
            source=ConfigSource.ADAPTER_INFERRED,
            original_key="sampling_rate_hz",
            canonical_key="sampling_rate_hz",
            inferred_from="vx2730.sampling_rate_hz",
        )
        assert cv.is_inferred()
        assert not cv.is_explicit()
        assert "inferred from vx2730" in cv.summary()

    def test_summary_explicit(self):
        cv = ConfigValue(
            value="test",
            source=ConfigSource.EXPLICIT,
            original_key="name",
            canonical_key="name",
        )
        assert "(explicit)" in cv.summary()

    def test_summary_default(self):
        cv = ConfigValue(
            value=50,
            source=ConfigSource.PLUGIN_DEFAULT,
            original_key="threshold",
            canonical_key="threshold",
        )
        assert "(default)" in cv.summary()


# ============================================================================
# ResolvedConfig Tests
# ============================================================================


class TestResolvedConfig:
    """ResolvedConfig 数据类测试"""

    def test_basic_operations(self):
        values = {
            "threshold": ConfigValue(
                value=100,
                source=ConfigSource.EXPLICIT,
                original_key="threshold",
                canonical_key="threshold",
            ),
            "name": ConfigValue(
                value="test",
                source=ConfigSource.PLUGIN_DEFAULT,
                original_key="name",
                canonical_key="name",
            ),
        }
        resolved = ResolvedConfig(
            plugin_name="test_plugin",
            values=values,
            adapter_name="vx2730",
        )

        # 基本访问
        assert resolved.get("threshold") == 100
        assert resolved.get("name") == "test"
        assert resolved.get("nonexistent", "default") == "default"
        assert resolved["threshold"] == 100
        assert "threshold" in resolved
        assert "nonexistent" not in resolved

    def test_to_dict(self):
        values = {
            "a": ConfigValue(value=1, source=ConfigSource.EXPLICIT, original_key="a", canonical_key="a"),
            "b": ConfigValue(value=2, source=ConfigSource.PLUGIN_DEFAULT, original_key="b", canonical_key="b"),
        }
        resolved = ResolvedConfig(plugin_name="test", values=values)
        d = resolved.to_dict()
        assert d == {"a": 1, "b": 2}

    def test_get_explicit_values(self):
        values = {
            "explicit_val": ConfigValue(
                value=1, source=ConfigSource.EXPLICIT, original_key="explicit_val", canonical_key="explicit_val"
            ),
            "default_val": ConfigValue(
                value=2, source=ConfigSource.PLUGIN_DEFAULT, original_key="default_val", canonical_key="default_val"
            ),
        }
        resolved = ResolvedConfig(plugin_name="test", values=values)
        explicit = resolved.get_explicit_values()
        assert explicit == {"explicit_val": 1}

    def test_get_inferred_values(self):
        values = {
            "inferred_val": ConfigValue(
                value=500e6,
                source=ConfigSource.ADAPTER_INFERRED,
                original_key="inferred_val",
                canonical_key="inferred_val",
                inferred_from="vx2730.sampling_rate_hz",
            ),
            "default_val": ConfigValue(
                value=2, source=ConfigSource.PLUGIN_DEFAULT, original_key="default_val", canonical_key="default_val"
            ),
        }
        resolved = ResolvedConfig(plugin_name="test", values=values)
        inferred = resolved.get_inferred_values()
        assert inferred == {"inferred_val": 500e6}

    def test_summary(self):
        values = {
            "threshold": ConfigValue(
                value=100, source=ConfigSource.EXPLICIT, original_key="threshold", canonical_key="threshold"
            ),
        }
        resolved = ResolvedConfig(plugin_name="test_plugin", values=values, adapter_name="vx2730")
        summary = resolved.summary(verbose=True)
        assert "test_plugin" in summary
        assert "vx2730" in summary
        assert "threshold" in summary


# ============================================================================
# AdapterInfo Tests
# ============================================================================


class TestAdapterInfo:
    """AdapterInfo 数据类测试"""

    def test_from_adapter_vx2730(self):
        info = AdapterInfo.from_adapter("vx2730")
        assert info is not None
        assert info.name == "vx2730"
        assert info.sampling_rate_hz == 500e6
        assert info.dt_ns == 2
        assert info.dt_ps == 2000
        assert info.timestamp_unit == "ps"

    def test_from_adapter_nonexistent(self):
        info = AdapterInfo.from_adapter("nonexistent_adapter")
        assert info is None

    def test_to_dict(self):
        info = AdapterInfo(
            name="test",
            sampling_rate_hz=250e6,
            timestamp_unit="ns",
            dt_ns=4,
            dt_ps=4000,
            expected_samples=1000,
        )
        d = info.to_dict()
        assert d["name"] == "test"
        assert d["sampling_rate_hz"] == 250e6
        assert d["timestamp_unit"] == "ns"
        assert d["dt_ns"] == 4
        assert d["dt_ps"] == 4000
        assert d["expected_samples"] == 1000

    def test_get_inferred_value(self):
        info = AdapterInfo(
            name="test",
            sampling_rate_hz=500e6,
            timestamp_unit="ps",
            dt_ns=2,
            dt_ps=2000,
        )
        assert info.get_inferred_value("sampling_rate_hz") == 500e6
        assert info.get_inferred_value("dt_ns") == 2
        assert info.get_inferred_value("nonexistent") is None


class TestGetAdapterInfo:
    """get_adapter_info 函数测试"""

    def test_cached_lookup(self):
        info1 = get_adapter_info("vx2730")
        info2 = get_adapter_info("vx2730")
        assert info1 is info2  # 应该是同一个缓存对象

    def test_nonexistent_adapter(self):
        info = get_adapter_info("nonexistent")
        assert info is None


# ============================================================================
# ConfigResolver Tests
# ============================================================================


class TestConfigResolver:
    """ConfigResolver 测试"""

    def test_resolve_explicit_config(self, resolver, mock_plugin):
        config = {"threshold": 200}
        resolved = resolver.resolve(mock_plugin, config)

        assert resolved.get("threshold") == 200
        cv = resolved.get_value("threshold")
        assert cv.source == ConfigSource.EXPLICIT

    def test_resolve_plugin_namespace_config(self, resolver, mock_plugin):
        config = {"mock_plugin": {"threshold": 300}}
        resolved = resolver.resolve(mock_plugin, config)

        assert resolved.get("threshold") == 300
        cv = resolved.get_value("threshold")
        assert cv.source == ConfigSource.EXPLICIT

    def test_resolve_default_value(self, resolver, mock_plugin):
        config = {}
        resolved = resolver.resolve(mock_plugin, config)

        assert resolved.get("threshold") == 50  # 默认值
        cv = resolved.get_value("threshold")
        assert cv.source == ConfigSource.PLUGIN_DEFAULT

    def test_resolve_adapter_inferred(self, resolver, mock_plugin):
        config = {}
        resolved = resolver.resolve(mock_plugin, config, adapter_name="vx2730")

        # sampling_rate_hz 应该从 adapter 推断
        assert resolved.get("sampling_rate_hz") == 500e6
        cv = resolved.get_value("sampling_rate_hz")
        assert cv.source == ConfigSource.ADAPTER_INFERRED
        assert "vx2730" in cv.inferred_from

    def test_explicit_overrides_inferred(self, resolver, mock_plugin):
        config = {"sampling_rate_hz": 250e6}
        resolved = resolver.resolve(mock_plugin, config, adapter_name="vx2730")

        # 显式配置应该覆盖推断值
        assert resolved.get("sampling_rate_hz") == 250e6
        cv = resolved.get_value("sampling_rate_hz")
        assert cv.source == ConfigSource.EXPLICIT

    def test_resolve_value_single(self, resolver, mock_plugin):
        config = {"threshold": 150}
        cv = resolver.resolve_value(mock_plugin, "threshold", config)

        assert cv.value == 150
        assert cv.source == ConfigSource.EXPLICIT

    def test_list_inferred_options(self):
        options = ConfigResolver.list_inferred_options()
        assert "sampling_rate_hz" in options
        assert "dt_ns" in options
        assert "dt_ps" in options


# ============================================================================
# CompatManager Tests
# ============================================================================


class TestCompatManager:
    """CompatManager 测试"""

    def test_resolve_global_alias(self, compat_manager):
        canonical, used = compat_manager.resolve_alias("any_plugin", "break_threshold_ns")
        assert canonical == "break_threshold_ps"
        assert used is True

    def test_resolve_no_alias(self, compat_manager):
        canonical, used = compat_manager.resolve_alias("any_plugin", "threshold")
        assert canonical == "threshold"
        assert used is False

    def test_warn_deprecation(self, compat_manager):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            compat_manager.warn_deprecation("break_threshold_ns", "test_context")

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "break_threshold_ns" in str(w[0].message)
            assert "break_threshold_ps" in str(w[0].message)

    def test_is_deprecated(self, compat_manager):
        assert compat_manager.is_deprecated("break_threshold_ns")
        assert not compat_manager.is_deprecated("threshold")

    def test_get_deprecation_info(self, compat_manager):
        info = compat_manager.get_deprecation_info("break_threshold_ns")
        assert info is not None
        assert info.old_name == "break_threshold_ns"
        assert info.new_name == "break_threshold_ps"

    def test_register_alias(self):
        CompatManager.register_alias("old_param", "new_param", "test_plugin")
        manager = CompatManager()
        canonical, used = manager.resolve_alias("test_plugin", "old_param")
        assert canonical == "new_param"
        assert used is True

        # 清理
        CompatManager.unregister_alias("old_param", "test_plugin")

    def test_list_aliases(self, compat_manager):
        aliases = compat_manager.list_aliases()
        assert "break_threshold_ns" in aliases

    def test_list_deprecations(self, compat_manager):
        deprecations = compat_manager.list_deprecations()
        assert len(deprecations) > 0
        names = [d.old_name for d in deprecations]
        assert "break_threshold_ns" in names


class TestDeprecationInfo:
    """DeprecationInfo 测试"""

    def test_get_warning_message_default(self):
        info = DeprecationInfo(
            old_name="old",
            new_name="new",
            deprecated_in="1.0.0",
            removed_in="2.0.0",
        )
        msg = info.get_warning_message()
        assert "old" in msg
        assert "new" in msg
        assert "1.0.0" in msg
        assert "2.0.0" in msg

    def test_get_warning_message_custom(self):
        info = DeprecationInfo(
            old_name="old",
            new_name="new",
            deprecated_in="1.0.0",
            removed_in="2.0.0",
            message="Custom deprecation message",
        )
        msg = info.get_warning_message()
        assert msg == "Custom deprecation message"


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """集成测试"""

    def test_context_get_resolved_config(self):
        """测试 Context.get_resolved_config()"""
        from waveform_analysis.core.context import Context
        from waveform_analysis.core.plugins.builtin.cpu import standard_plugins

        ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
        ctx.register(*standard_plugins)

        resolved = ctx.get_resolved_config("waveforms")
        assert resolved.plugin_name == "waveforms"
        assert resolved.adapter_name == "vx2730"

    def test_context_get_lineage_with_adapter_info(self):
        """测试 get_lineage() 包含 adapter_info"""
        from waveform_analysis.core.context import Context
        from waveform_analysis.core.plugins.builtin.cpu import standard_plugins

        ctx = Context(config={"data_root": "DAQ", "daq_adapter": "vx2730"})
        ctx.register(*standard_plugins)

        lineage = ctx.get_lineage("waveforms")
        assert "adapter_info" in lineage
        assert lineage["adapter_info"]["name"] == "vx2730"
        assert lineage["adapter_info"]["sampling_rate_hz"] == 500e6

    def test_context_get_adapter_info(self):
        """测试 Context.get_adapter_info()"""
        from waveform_analysis.core.context import Context

        ctx = Context(config={"daq_adapter": "vx2730"})
        info = ctx.get_adapter_info()
        assert info is not None
        assert info.name == "vx2730"

        # 无 adapter 时返回 None
        ctx2 = Context(config={})
        assert ctx2.get_adapter_info() is None
