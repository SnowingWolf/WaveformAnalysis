"""
Help 系统测试
"""

import pytest
from waveform_analysis.core.context import Context
from waveform_analysis import WaveformDataset


class TestHelpSystem:
    """Help 系统测试"""

    def test_context_help_default(self):
        """测试 Context 默认 help 输出"""
        ctx = Context()
        output = ctx.help()

        assert 'WaveformAnalysis Context - 快速参考' in output
        assert "ctx.help('quickstart')" in output
        assert '快速开始' in output

    def test_context_help_quickstart_topic(self):
        """测试 quickstart 主题"""
        ctx = Context()
        output = ctx.help('quickstart')

        assert 'basic' in output
        assert '快速开始指南' in output

    def test_context_help_config_topic(self):
        """测试 config 主题"""
        ctx = Context()
        output = ctx.help('config')

        assert '配置管理' in output
        assert 'list_plugin_configs' in output
        assert 'show_config' in output

    def test_context_help_unknown_topic(self):
        """测试未知主题错误提示"""
        ctx = Context()
        output = ctx.help('nonexistent_topic')

        assert '未知主题' in output
        assert 'quickstart' in output

    def test_context_help_search(self):
        """测试搜索功能（简化版）"""
        ctx = Context()
        output = ctx.help(search='time_range')

        assert '搜索' in output
        assert 'time_range' in output

    def test_context_help_verbose_mode(self):
        """测试 verbose 模式"""
        ctx = Context()
        output_default = ctx.help('quickstart')
        output_verbose = ctx.help('quickstart', verbose=True)

        # verbose 模式应该有更多内容
        assert len(output_verbose) > len(output_default)
        assert '详细' in output_verbose or '代码模板' in output_verbose

    def test_context_quickstart_template_basic(self):
        """测试生成 basic 模板"""
        ctx = Context()
        code = ctx.quickstart('basic')

        assert 'from waveform_analysis' in code
        assert 'Context(' in code
        assert 'get_data' in code
        assert 'def main()' in code

        # 验证是否为有效 Python 代码
        compile(code, '<string>', 'exec')

    def test_context_quickstart_custom_params(self):
        """测试自定义模板参数"""
        ctx = Context()
        code = ctx.quickstart('basic', run_id='run_002', n_channels=4)

        assert 'run_002' in code
        assert "'n_channels': 4" in code or '"n_channels": 4' in code

    def test_context_quickstart_unknown_template(self):
        """测试未知模板错误处理"""
        ctx = Context()

        with pytest.raises(ValueError, match="未知模板"):
            ctx.quickstart('nonexistent_template')

    def test_dataset_help_workflow(self, tmp_path):
        """测试 WaveformDataset 工作流程帮助"""
        # 创建临时数据目录
        data_dir = tmp_path / "DAQ" / "test"
        data_dir.mkdir(parents=True, exist_ok=True)

        ds = WaveformDataset(run_name='test', n_channels=2, data_root=str(tmp_path / "DAQ"))
        output = ds.help()

        assert 'WaveformDataset 工作流程' in output
        assert 'load_raw_data' in output
        assert 'extract_waveforms' in output
        assert '链式调用' in output

    def test_dataset_help_workflow_verbose(self, tmp_path):
        """测试 Dataset 工作流程详细模式"""
        # 创建临时数据目录
        data_dir = tmp_path / "DAQ" / "test"
        data_dir.mkdir(parents=True, exist_ok=True)

        ds = WaveformDataset(run_name='test', n_channels=2, data_root=str(tmp_path / "DAQ"))
        output_default = ds.help()
        output_verbose = ds.help(verbose=True)

        # verbose 模式应该有更多内容
        assert len(output_verbose) > len(output_default)
        assert '数据流详解' in output_verbose

    def test_dataset_help_delegates_to_context(self, tmp_path):
        """测试 Dataset.help() 转发给 Context"""
        # 创建临时数据目录
        data_dir = tmp_path / "DAQ" / "test"
        data_dir.mkdir(parents=True, exist_ok=True)

        ds = WaveformDataset(run_name='test', n_channels=2, data_root=str(tmp_path / "DAQ"))
        output = ds.help('config')

        assert '配置管理' in output

    def test_help_system_performance(self):
        """测试 help 响应性能（< 100ms）"""
        import time

        ctx = Context()

        # 预热（首次加载）
        ctx.help()

        # 测试性能（应使用缓存）
        start = time.perf_counter()
        ctx.help()
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"Help system too slow: {elapsed:.3f}s"

    def test_help_caching(self):
        """测试 help 文本缓存"""
        ctx = Context()

        # 第一次调用
        output1 = ctx.help('quickstart')

        # 第二次调用（应从缓存读取）
        output2 = ctx.help('quickstart')

        # 输出应完全相同
        assert output1 == output2

    def test_help_system_integration(self):
        """测试 help 系统与 Context 的完整集成"""
        ctx = Context()

        # help() 方法应该存在
        assert hasattr(ctx, 'help')
        assert callable(ctx.help)

        # quickstart() 方法应该存在
        assert hasattr(ctx, 'quickstart')
        assert callable(ctx.quickstart)

        # 延迟初始化应该正常工作
        assert ctx._help_system is None  # 未调用前为 None
        ctx.help()
        assert ctx._help_system is not None  # 调用后被初始化

    def test_quickstart_template_completeness(self):
        """测试 quickstart 模板的完整性"""
        ctx = Context()

        for template_name in ['basic', 'basic_analysis']:
            code = ctx.quickstart(template_name)

            # 所有模板应该包含基本元素
            assert '#!/usr/bin/env python' in code
            assert '# -*- coding: utf-8 -*-' in code
            assert 'def main()' in code
            assert "if __name__ == '__main__':" in code

            # 应该是有效的 Python 代码
            compile(code, f'<{template_name}>', 'exec')
