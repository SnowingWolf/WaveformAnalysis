"""
快速开始代码模板系统

提供可执行的代码模板用于常见分析场景。
"""

from datetime import datetime
from typing import TYPE_CHECKING
from waveform_analysis.core.foundation.utils import exporter

if TYPE_CHECKING:
    from waveform_analysis.core.context import Context

export, __all__ = exporter()


@export
class QuickstartTemplate:
    """模板基类"""
    name: str
    description: str

    def generate(self, ctx: 'Context', **params) -> str:
        """
        生成 Python 代码字符串

        Args:
            ctx: Context 实例
            **params: 模板参数

        Returns:
            可执行的 Python 代码
        """
        raise NotImplementedError


@export
class BasicAnalysisTemplate(QuickstartTemplate):
    """基础分析流程模板"""
    name = 'basic_analysis'
    description = '基础分析流程'

    def generate(self, ctx: 'Context', run_id: str = 'run_001',
                 data_root: str = 'DAQ', n_channels: int = 2) -> str:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f'''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基础波形分析 - 自动生成于 {timestamp}
"""

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin import standard_plugins

def main():
    # 1. 初始化 Context
    ctx = Context(storage_dir='./strax_data')
    ctx.register(standard_plugins)

    # 2. 设置配置
    ctx.set_config({{
        'data_root': '{data_root}',
        'n_channels': {n_channels},
        'threshold': 15.0,
    }})

    # 3. 获取数据（自动触发依赖链）
    print(f"Processing run: {run_id}")
    peaks = ctx.get_data('{run_id}', 'peaks')
    print(f"Found {{len(peaks)}} peaks")

    # 4. 可视化血缘图（可选）
    # ctx.plot_lineage('peaks', kind='labview')

    return peaks

if __name__ == '__main__':
    result = main()
    print(f"Analysis complete. Result shape: {{result.shape}}")
'''


@export
class MemoryEfficientTemplate(QuickstartTemplate):
    """内存优化流程模板"""
    name = 'memory_efficient'
    description = '内存优化流程（节省 70-80% 内存）'

    def generate(self, ctx: 'Context', run_name: str = 'run_001',
                 n_channels: int = 2) -> str:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return f'''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
内存优化分析 - 自动生成于 {timestamp}

跳过波形加载，只计算特征（节省 70-80% 内存）
"""

from waveform_analysis import WaveformDataset

def main():
    # load_waveforms=False 跳过波形数据加载
    ds = WaveformDataset(
        run_name='{run_name}',
        n_channels={n_channels},
        load_waveforms=False  # 关键：跳过波形加载
    )

    # 链式调用（波形步骤会被跳过）
    (ds
        .load_raw_data()
        .extract_waveforms()        # 跳过
        .structure_waveforms()      # 跳过
        .build_waveform_features()  # 仍会计算特征
        .build_dataframe()
        .group_events(time_window_ns=100)
        .pair_events())

    # 获取结果
    df_paired = ds.get_paired_events()
    print(f"Processed {{len(df_paired)}} paired events")

    # 显示摘要
    print("\\nDataset summary:")
    print(ds.summary())

    # 注意: get_waveform_at() 会返回 None
    # wf = ds.get_waveform_at(0)  # None

    return df_paired

if __name__ == '__main__':
    result = main()
    print(f"\\nResult columns: {{result.columns.tolist()}}")
    print(f"Memory saved: ~70-80% compared to full waveform loading")
'''


# 模板注册表
TEMPLATES = {
    'basic': BasicAnalysisTemplate(),
    'basic_analysis': BasicAnalysisTemplate(),
    'memory_efficient': MemoryEfficientTemplate(),
}
