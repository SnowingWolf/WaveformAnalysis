"""
Plugins 模块测试
"""

import numpy as np
import pytest

from waveform_analysis.core.plugins.core.base import Option, Plugin


class TestOption:
    """Option 测试"""

    def test_option_defaults(self):
        """测试 Option 默认值"""
        opt = Option()
        assert opt.default is None
        assert opt.type is None
        assert opt.help == ""
        assert opt.validate is None

    def test_option_with_values(self):
        """测试带值的 Option"""
        opt = Option(
            default=10,
            type=int,
            help="A number option",
            validate=lambda x: x > 0,
        )
        assert opt.default == 10
        assert opt.type is int
        assert opt.help == "A number option"
        assert opt.validate is not None

    def test_validate_value_correct_type(self):
        """测试正确类型的值验证"""
        opt = Option(type=int)
        result = opt.validate_value("test", 42, "TestPlugin")
        assert result == 42

    def test_validate_value_type_conversion_int(self):
        """测试整数类型转换"""
        opt = Option(type=int)
        result = opt.validate_value("test", "42", "TestPlugin")
        assert result == 42

    def test_validate_value_type_conversion_float(self):
        """测试浮点类型转换"""
        opt = Option(type=float)
        result = opt.validate_value("test", "3.14", "TestPlugin")
        assert result == 3.14

    def test_validate_value_type_conversion_bool(self):
        """测试布尔类型转换"""
        opt = Option(type=bool)

        for true_val in ["true", "1", "yes", "on", "TRUE"]:
            result = opt.validate_value("test", true_val, "TestPlugin")
            assert result is True

    def test_validate_value_wrong_type(self):
        """测试错误类型抛出异常"""
        opt = Option(type=int)

        with pytest.raises(TypeError) as exc_info:
            opt.validate_value("test", "not_a_number", "TestPlugin")

        assert "must be of type" in str(exc_info.value)

    def test_validate_value_custom_validation(self):
        """测试自定义验证"""
        opt = Option(type=int, validate=lambda x: x > 0)

        # 有效值
        result = opt.validate_value("test", 10, "TestPlugin")
        assert result == 10

        # 无效值
        with pytest.raises(ValueError) as exc_info:
            opt.validate_value("test", -5, "TestPlugin")

        assert "failed validation" in str(exc_info.value)


class TestPlugin:
    """Plugin 测试"""

    def test_plugin_abstract(self):
        """测试 Plugin 是抽象类"""
        # 不能直接实例化
        with pytest.raises(TypeError):
            Plugin()

    def test_simple_plugin_implementation(self):
        """测试简单的 Plugin 实现"""

        class SimplePlugin(Plugin):
            provides = "simple_data"
            depends_on = []
            dtype = np.dtype([("time", "<i8")])
            version = "1.0.0"

            def compute(self, *args, **kwargs):
                return np.array([], dtype=self.dtype)

        plugin = SimplePlugin()
        assert plugin.provides == "simple_data"
        assert plugin.depends_on == []
        assert plugin.version == "1.0.0"

    def test_plugin_with_dependencies(self):
        """测试带依赖的 Plugin"""

        class DependentPlugin(Plugin):
            provides = "derived_data"
            depends_on = ["raw_data", "other_data"]
            dtype = np.dtype("<f8")
            version = "1.0.0"

            def compute(self, *args, **kwargs):
                return np.array([])

        plugin = DependentPlugin()
        assert "raw_data" in plugin.depends_on
        assert "other_data" in plugin.depends_on

    def test_plugin_with_options(self):
        """测试带选项的 Plugin"""

        class ConfigurablePlugin(Plugin):
            provides = "config_data"
            depends_on = []
            options = {
                "threshold": Option(default=0.5, type=float, help="Detection threshold"),
                "window_size": Option(default=100, type=int, help="Window size"),
            }
            version = "1.0.0"

            def compute(self, *args, **kwargs):
                return np.array([])

        plugin = ConfigurablePlugin()
        assert "threshold" in plugin.options
        assert plugin.options["threshold"].default == 0.5
        assert plugin.config_keys == ["threshold", "window_size"]

    def test_plugin_validate_success(self):
        """测试插件验证成功"""

        class ValidPlugin(Plugin):
            provides = "valid_data"
            depends_on = ["dep1"]
            options = {"opt1": Option()}
            version = "1.0.0"

            def compute(self, *args, **kwargs):
                return np.array([])

        plugin = ValidPlugin()
        # 应该不抛异常
        plugin.validate()

    def test_plugin_validate_no_provides(self):
        """测试没有 provides 的插件验证失败"""

        class NoProvides(Plugin):
            provides = ""  # Empty
            depends_on = []
            version = "1.0.0"

            def compute(self, *args, **kwargs):
                return np.array([])

        plugin = NoProvides()
        with pytest.raises(ValueError) as exc_info:
            plugin.validate()

        assert "must specify 'provides'" in str(exc_info.value)

    def test_plugin_validate_invalid_depends_on(self):
        """测试无效 depends_on 的插件验证失败"""

        class InvalidDepsType(Plugin):
            provides = "data"
            depends_on = "not_a_list"  # Should be list
            version = "1.0.0"

            def compute(self, *args, **kwargs):
                return np.array([])

        plugin = InvalidDepsType()
        with pytest.raises(TypeError) as exc_info:
            plugin.validate()

        assert "must be a list or tuple" in str(exc_info.value)

    def test_plugin_side_effect(self):
        """测试副作用插件"""

        class SideEffectPlugin(Plugin):
            provides = "plot_output"
            depends_on = ["data"]
            is_side_effect = True
            version = "1.0.0"

            def compute(self, *args, **kwargs):
                # 副作用：生成文件或图表
                pass

        plugin = SideEffectPlugin()
        assert plugin.is_side_effect is True

    def test_plugin_output_kinds(self):
        """测试输出类型"""

        class StaticPlugin(Plugin):
            provides = "static"
            output_kind = "static"
            version = "1.0.0"

            def compute(self, *args, **kwargs):
                return np.array([])

        class StreamPlugin(Plugin):
            provides = "stream"
            output_kind = "stream"
            version = "1.0.0"

            def compute(self, *args, **kwargs):
                yield np.array([])

        static = StaticPlugin()
        stream = StreamPlugin()

        assert static.output_kind == "static"
        assert stream.output_kind == "stream"

    def test_plugin_validate_invalid_depends_on_elements(self):
        """测试 depends_on 包含非字符串元素"""

        class BadDependsPlugin(Plugin):
            provides = "data"
            depends_on = ["dep1", 123]

            def compute(self, context, run_id):
                return None

        with pytest.raises(TypeError, match="dependency '123' must be a string"):
            BadDependsPlugin().validate()

    def test_plugin_optional_methods(self):
        """测试插件的可选方法"""

        class MyPlugin(Plugin):
            provides = "data"

            def compute(self, context, run_id):
                return np.array([1])

            def on_register(self, context):
                self.registered = True

            def on_unregister(self, context):
                self.unregistered = True

        p = MyPlugin()
        p.on_register(None)
        assert p.registered
        p.on_unregister(None)
        assert p.unregistered

    def test_option_type_conversion_fallback(self):
        """测试类型转换失败后的回退"""
        opt = Option(type=int)
        with pytest.raises(TypeError):
            opt.validate_value("test", object(), "TestPlugin")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
