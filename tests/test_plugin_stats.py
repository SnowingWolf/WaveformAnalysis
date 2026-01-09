"""
测试插件性能统计功能
"""

import os
import tempfile
import shutil
import pytest
import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin
from waveform_analysis.core.plugin_stats import (
    PluginStatsCollector,
    get_stats_collector,
    PluginExecutionRecord,
    PluginStatistics,
)


class SimplePlugin(Plugin):
    """简单测试插件"""
    provides = "simple_data"
    depends_on = []
    output_dtype = np.dtype([('value', np.int32)])

    def compute(self, context, run_id, **kwargs):
        return np.array([(1,), (2,), (3,)], dtype=self.output_dtype)


class SlowPlugin(Plugin):
    """慢速测试插件(用于测试时间统计)"""
    provides = "slow_data"
    depends_on = []
    output_dtype = np.dtype([('value', np.int32)])

    def compute(self, context, run_id, **kwargs):
        import time
        time.sleep(0.1)  # 100ms
        return np.array([(1,)], dtype=self.output_dtype)


class FailingPlugin(Plugin):
    """失败的测试插件"""
    provides = "failing_data"
    depends_on = []
    output_dtype = np.dtype([('value', np.int32)])

    def compute(self, context, run_id, **kwargs):
        raise ValueError("Intentional failure for testing")


class TestPluginStatsCollector:
    """测试PluginStatsCollector基本功能"""

    def setup_method(self):
        """Setup"""
        self.collector = PluginStatsCollector(mode='basic')

    def test_collector_creation(self):
        """测试创建collector"""
        assert self.collector is not None
        assert self.collector.mode == 'basic'
        assert self.collector.is_enabled()

    def test_collector_modes(self):
        """测试不同的监控模式"""
        # Off mode
        collector_off = PluginStatsCollector(mode='off')
        assert not collector_off.is_enabled()

        # Basic mode
        collector_basic = PluginStatsCollector(mode='basic')
        assert collector_basic.is_enabled()
        assert not collector_basic.enable_memory_tracking

        # Detailed mode
        collector_detailed = PluginStatsCollector(mode='detailed')
        assert collector_detailed.is_enabled()
        # Memory tracking may or may not be available
        assert collector_detailed.enable_memory_tracking in [True, False]

    def test_start_end_execution(self):
        """测试记录执行"""
        self.collector.start_execution('test_plugin', 'run_001')
        self.collector.end_execution('test_plugin', success=True, cache_hit=False)

        stats = self.collector.get_statistics('test_plugin')
        assert 'test_plugin' in stats
        assert stats['test_plugin'].total_calls == 1
        assert stats['test_plugin'].successful_calls == 1
        assert stats['test_plugin'].cache_misses == 1

    def test_cache_hit_recording(self):
        """测试缓存命中记录"""
        self.collector.start_execution('test_plugin', 'run_001')
        self.collector.end_execution('test_plugin', success=True, cache_hit=True)

        stats = self.collector.get_statistics('test_plugin')
        assert stats['test_plugin'].cache_hits == 1
        assert stats['test_plugin'].cache_hit_rate() == 1.0

    def test_failure_recording(self):
        """测试失败记录"""
        self.collector.start_execution('test_plugin', 'run_001')
        error = ValueError("Test error")
        self.collector.end_execution('test_plugin', success=False, error=error)

        stats = self.collector.get_statistics('test_plugin')
        assert stats['test_plugin'].failed_calls == 1
        assert stats['test_plugin'].success_rate() == 0.0
        assert len(stats['test_plugin'].recent_errors) == 1

    def test_multiple_executions(self):
        """测试多次执行统计"""
        for i in range(5):
            self.collector.start_execution('test_plugin', f'run_{i:03d}')
            self.collector.end_execution('test_plugin', success=True, cache_hit=(i % 2 == 0))

        stats = self.collector.get_statistics('test_plugin')
        assert stats['test_plugin'].total_calls == 5
        assert stats['test_plugin'].cache_hits == 3  # 0, 2, 4
        assert stats['test_plugin'].cache_misses == 2  # 1, 3

    def test_time_statistics(self):
        """测试时间统计"""
        import time

        # First execution (slower)
        self.collector.start_execution('test_plugin', 'run_001')
        time.sleep(0.05)
        self.collector.end_execution('test_plugin', success=True)

        # Second execution (faster)
        self.collector.start_execution('test_plugin', 'run_002')
        time.sleep(0.02)
        self.collector.end_execution('test_plugin', success=True)

        stats = self.collector.get_statistics('test_plugin')
        s = stats['test_plugin']

        assert s.total_calls == 2
        assert s.min_time >= 0.01  # At least ~20ms
        assert s.max_time >= 0.04  # At least ~50ms
        assert s.mean_time > 0

    def test_generate_text_report(self):
        """测试生成文本报告"""
        self.collector.start_execution('plugin1', 'run_001')
        self.collector.end_execution('plugin1', success=True)

        report = self.collector.generate_report(format='text')
        assert isinstance(report, str)
        assert 'plugin1' in report
        assert 'Total calls: 1' in report

    def test_generate_dict_report(self):
        """测试生成字典报告"""
        self.collector.start_execution('plugin1', 'run_001')
        self.collector.end_execution('plugin1', success=True)

        report = self.collector.generate_report(format='dict')
        assert isinstance(report, dict)
        assert 'summary' in report
        assert 'plugins' in report
        assert 'plugin1' in report['plugins']

    def test_get_execution_history(self):
        """测试获取执行历史"""
        for i in range(3):
            self.collector.start_execution('test_plugin', f'run_{i}')
            self.collector.end_execution('test_plugin', success=True)

        history = self.collector.get_execution_history('test_plugin')
        assert len(history) == 3
        assert all(isinstance(record, PluginExecutionRecord) for record in history)

    def test_reset(self):
        """测试重置统计"""
        self.collector.start_execution('test_plugin', 'run_001')
        self.collector.end_execution('test_plugin', success=True)

        self.collector.reset()

        stats = self.collector.get_statistics('test_plugin')
        assert 'test_plugin' not in stats or stats['test_plugin'].total_calls == 0


class TestContextIntegration:
    """测试Context集成"""

    def setup_method(self):
        """Setup temporary directory"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_context_with_stats_disabled(self):
        """测试禁用统计的Context"""
        ctx = Context(storage_dir=self.temp_dir, enable_stats=False)
        assert ctx.stats_collector is None

        ctx.register(SimplePlugin())
        data = ctx.get_data('run_001', 'simple_data')
        assert data is not None

    def test_context_with_stats_basic(self):
        """测试启用basic模式统计的Context"""
        ctx = Context(
            storage_dir=self.temp_dir,
            enable_stats=True,
            stats_mode='basic'
        )
        assert ctx.stats_collector is not None
        assert ctx.stats_collector.mode == 'basic'

        ctx.register(SimplePlugin())
        data = ctx.get_data('run_001', 'simple_data')
        assert data is not None

        # Check stats were recorded
        stats = ctx.stats_collector.get_statistics('simple_data')
        assert 'simple_data' in stats
        assert stats['simple_data'].total_calls == 1

    def test_context_with_stats_detailed(self):
        """测试启用detailed模式统计的Context"""
        ctx = Context(
            storage_dir=self.temp_dir,
            enable_stats=True,
            stats_mode='detailed'
        )
        assert ctx.stats_collector is not None
        assert ctx.stats_collector.mode == 'detailed'

        ctx.register(SimplePlugin())
        data = ctx.get_data('run_001', 'simple_data')
        assert data is not None

        # Check detailed stats
        stats = ctx.stats_collector.get_statistics('simple_data')
        s = stats['simple_data']
        assert s.total_calls == 1
        # Memory stats may or may not be available depending on system

    def test_cache_hit_stats(self):
        """测试缓存命中的统计"""
        ctx = Context(
            storage_dir=self.temp_dir,
            enable_stats=True,
            stats_mode='basic'
        )
        ctx.register(SimplePlugin())

        # First call - cache miss
        data1 = ctx.get_data('run_001', 'simple_data')
        assert data1 is not None

        # Second call - cache hit
        data2 = ctx.get_data('run_001', 'simple_data')
        assert data2 is not None

        # Check stats
        stats = ctx.stats_collector.get_statistics('simple_data')
        s = stats['simple_data']
        assert s.total_calls == 2
        assert s.cache_hits == 1
        assert s.cache_misses == 1

    def test_plugin_failure_stats(self):
        """测试插件失败统计"""
        ctx = Context(
            storage_dir=self.temp_dir,
            enable_stats=True,
            stats_mode='basic'
        )
        ctx.register(FailingPlugin())

        # Try to run failing plugin
        with pytest.raises(RuntimeError):
            ctx.get_data('run_001', 'failing_data')

        # Check failure was recorded
        stats = ctx.stats_collector.get_statistics('failing_data')
        s = stats['failing_data']
        assert s.total_calls == 1
        assert s.failed_calls == 1
        assert s.success_rate() == 0.0
        assert len(s.recent_errors) == 1

    def test_get_performance_report(self):
        """测试获取性能报告"""
        ctx = Context(
            storage_dir=self.temp_dir,
            enable_stats=True,
            stats_mode='basic'
        )
        ctx.register(SimplePlugin())
        ctx.get_data('run_001', 'simple_data')

        # Get text report
        report = ctx.get_performance_report()
        assert isinstance(report, str)
        assert 'simple_data' in report

        # Get dict report
        report_dict = ctx.get_performance_report(format='dict')
        assert isinstance(report_dict, dict)

        # Get plugin-specific report
        plugin_report = ctx.get_performance_report(plugin_name='simple_data')
        assert isinstance(plugin_report, str)
        assert 'simple_data' in plugin_report

    def test_get_performance_report_disabled(self):
        """测试禁用统计时获取报告"""
        ctx = Context(storage_dir=self.temp_dir, enable_stats=False)
        report = ctx.get_performance_report()
        assert "disabled" in report.lower()

    def test_stats_with_log_file(self):
        """测试带日志文件的统计"""
        log_file = os.path.join(self.temp_dir, 'logs', 'stats.log')

        ctx = Context(
            storage_dir=self.temp_dir,
            enable_stats=True,
            stats_mode='basic',
            stats_log_file=log_file
        )
        ctx.register(SimplePlugin())
        ctx.get_data('run_001', 'simple_data')

        # Check log file was created
        assert os.path.exists(log_file)

        # Check log contains relevant info
        with open(log_file, 'r') as f:
            log_content = f.read()
            assert 'simple_data' in log_content


class TestGlobalStatsCollector:
    """测试全局stats collector"""

    def test_get_stats_collector_singleton(self):
        """测试全局单例"""
        collector1 = get_stats_collector(mode='basic')
        collector2 = get_stats_collector(mode='basic')
        assert collector1 is collector2

    def test_get_stats_collector_reset(self):
        """测试reset参数"""
        collector1 = get_stats_collector(mode='basic', reset=True)
        collector2 = get_stats_collector(mode='detailed', reset=True)

        # After reset, mode should change
        assert collector2.mode == 'detailed'


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
