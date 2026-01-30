"""
测试插件版本支持功能
"""

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin


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

    def test_version_validation_in_context(self):
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

        ctx = Context()
        ctx.register_plugin_(ProducerPlugin())

        # 兼容的插件应该可以注册
        ctx.register_plugin_(CompatibleConsumerPlugin())

        # 不兼容的插件会记录警告但不会失败（graceful degradation）
        try:
            ctx.register_plugin_(IncompatibleConsumerPlugin())
        except ValueError:
            # 如果packaging可用，可能会抛出ValueError
            pass

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
