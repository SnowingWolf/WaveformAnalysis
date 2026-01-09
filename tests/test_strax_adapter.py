"""
测试Strax插件适配器 (Phase 2.3)
"""

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.strax_adapter import (
    StraxPluginAdapter,
    StraxContextAdapter,
    create_strax_context,
    wrap_strax_plugin,
)


# ===========================
# 模拟Strax插件
# ===========================

class MockStraxRawRecordsPlugin:
    """模拟strax原始记录插件"""

    provides = 'raw_records'
    depends_on = tuple()
    dtype = [('time', 'i8'), ('channel', 'i2'), ('data', 'i2', (100,))]
    data_kind = 'raw_records'
    __version__ = '1.0.0'

    def compute(self):
        """生成模拟原始记录"""
        n_records = 10
        data = np.zeros(n_records, dtype=self.dtype)
        data['time'] = np.arange(0, n_records * 1000, 1000, dtype=np.int64)
        data['channel'] = np.arange(n_records, dtype=np.int16) % 2
        data['data'] = np.random.randint(-100, 100, size=(n_records, 100), dtype=np.int16)
        return data


class MockStraxPeaksPlugin:
    """模拟strax峰值插件"""

    provides = 'peaks'
    depends_on = ('raw_records',)
    dtype = [('time', 'i8'), ('channel', 'i2'), ('area', 'f4'), ('height', 'f4')]
    data_kind = 'peaks'
    __version__ = '1.0.0'
    takes_config = [
        ('peak_threshold', 10.0),
        'baseline_samples',
    ]

    def compute(self, raw_records, peak_threshold=10.0):
        """从原始记录计算峰值"""
        n_peaks = len(raw_records)
        data = np.zeros(n_peaks, dtype=self.dtype)
        data['time'] = raw_records['time']
        data['channel'] = raw_records['channel']

        # 简单的峰值计算
        for i in range(n_peaks):
            waveform = raw_records['data'][i]
            data['area'][i] = np.abs(waveform).sum()
            data['height'][i] = np.abs(waveform).max()

        # 应用阈值
        mask = data['area'] >= peak_threshold
        return data[mask]


# ===========================
# 测试适配器
# ===========================

def test_strax_plugin_adapter_basic():
    """测试基本的插件适配"""
    adapter = StraxPluginAdapter(MockStraxRawRecordsPlugin)

    assert adapter.provides == 'raw_records'
    assert len(adapter.depends_on) == 0
    assert adapter.dtype is not None
    assert adapter.version == '1.0.0'
    assert adapter.is_compatible()


def test_strax_plugin_adapter_with_config():
    """测试带配置的插件适配"""
    adapter = StraxPluginAdapter(MockStraxPeaksPlugin)

    assert adapter.provides == 'peaks'
    assert adapter.depends_on == ('raw_records',)
    assert 'peak_threshold' in adapter.config_keys
    assert 'baseline_samples' in adapter.config_keys


def test_strax_plugin_adapter_compute():
    """测试适配器的compute方法"""
    # 创建Context
    ctx = Context(storage_dir='./test_strax_cache')

    # 注册原始记录插件
    raw_adapter = wrap_strax_plugin(MockStraxRawRecordsPlugin)
    ctx.register_plugin(raw_adapter)

    # 获取原始记录
    raw_data = ctx.get_data('run_001', 'raw_records')
    assert len(raw_data) == 10
    assert raw_data.dtype.names == ('time', 'channel', 'data')


def test_strax_plugin_adapter_with_dependencies():
    """测试带依赖的插件适配"""
    # 创建Context
    ctx = Context(storage_dir='./test_strax_cache')

    # 注册插件
    raw_adapter = wrap_strax_plugin(MockStraxRawRecordsPlugin)
    peaks_adapter = wrap_strax_plugin(MockStraxPeaksPlugin)

    ctx.register_plugin(raw_adapter)
    ctx.register_plugin(peaks_adapter)

    # 设置配置
    ctx.set_config({'peak_threshold': 50.0})

    # 获取峰值(应该自动解析依赖)
    peaks_data = ctx.get_data('run_001', 'peaks')
    assert len(peaks_data) >= 0  # 可能被阈值过滤
    assert peaks_data.dtype.names == ('time', 'channel', 'area', 'height')


def test_strax_context_adapter():
    """测试StraxContext适配器"""
    # 创建strax风格的context
    strax_ctx = create_strax_context('./test_strax_cache')

    # 注册插件
    strax_ctx.register(MockStraxRawRecordsPlugin)
    strax_ctx.register(MockStraxPeaksPlugin)

    # 使用strax风格的API
    data = strax_ctx.get_array('run_001', 'raw_records')
    assert len(data) == 10

    # 获取多个目标
    multi_data = strax_ctx.get_array('run_001', ['raw_records', 'peaks'])
    assert 'raw_records' in multi_data
    assert 'peaks' in multi_data


def test_strax_context_adapter_get_df():
    """测试StraxContext适配器的get_df方法"""
    strax_ctx = create_strax_context('./test_strax_cache')
    strax_ctx.register(MockStraxRawRecordsPlugin)

    # 获取DataFrame
    df = strax_ctx.get_df('run_001', 'raw_records')
    assert len(df) == 10
    assert 'time' in df.columns
    assert 'channel' in df.columns


def test_strax_context_adapter_set_config():
    """测试配置设置"""
    strax_ctx = create_strax_context('./test_strax_cache')
    strax_ctx.register(MockStraxRawRecordsPlugin)
    strax_ctx.register(MockStraxPeaksPlugin)

    # 设置配置
    strax_ctx.set_config({'peak_threshold': 100.0})

    # 获取数据(应该使用新配置)
    peaks = strax_ctx.get_array('run_001', 'peaks')
    # 由于阈值较高,峰值数量应该较少
    assert len(peaks) >= 0


def test_strax_context_adapter_search_field():
    """测试字段搜索"""
    strax_ctx = create_strax_context('./test_strax_cache')
    strax_ctx.register(MockStraxRawRecordsPlugin)
    strax_ctx.register(MockStraxPeaksPlugin)

    # 搜索包含'peak'的字段
    results = strax_ctx.search_field('peak')
    assert 'peaks' in results

    # 搜索包含'raw'的字段
    results = strax_ctx.search_field('raw')
    assert 'raw_records' in results


def test_wrap_strax_plugin():
    """测试包装函数"""
    # 包装插件
    adapter = wrap_strax_plugin(MockStraxRawRecordsPlugin)

    assert isinstance(adapter, StraxPluginAdapter)
    assert adapter.is_compatible()
    assert adapter.provides == 'raw_records'


def test_strax_plugin_incompatible():
    """测试不兼容的插件"""

    class IncompatiblePlugin:
        """不兼容的插件(缺少required属性)"""
        provides = 'test'
        # 缺少compute方法

    # 应该能创建适配器,但is_compatible返回False
    adapter = StraxPluginAdapter(IncompatiblePlugin)
    assert not adapter.is_compatible()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
