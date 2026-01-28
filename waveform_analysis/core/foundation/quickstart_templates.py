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
from waveform_analysis.core.plugins.builtin.cpu import standard_plugins

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
    basic_features = ctx.get_data('{run_id}', 'basic_features')
    heights = [ch['height'] for ch in basic_features]
    print(f"Found {{len(heights)}} height arrays")

    # 4. 可视化血缘图（可选）
    # ctx.plot_lineage('basic_features', kind='labview')

    return heights

if __name__ == '__main__':
    result = main()
    print(f"Analysis complete. Result shape: {{result.shape}}")
'''


# 模板注册表
TEMPLATES = {
    'basic': BasicAnalysisTemplate(),
    'basic_analysis': BasicAnalysisTemplate(),
}
