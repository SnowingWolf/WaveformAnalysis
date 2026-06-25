#!/usr/bin/env python
"""单光子增益配置简单示例"""

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    BasicFeaturesPlugin,
    DataFramePlugin,
    RawFilesPlugin,
    WaveformsPlugin,
)

# 创建 Context
ctx = Context(storage_dir="./strax_data")

# 注册插件
ctx.register(
    RawFilesPlugin(),
    WaveformsPlugin(),
    BasicFeaturesPlugin(),
    DataFramePlugin(),
)

# 设置单光子增益（每个光电子对应的 ADC 计数值）
gain_config = {
    "0:9": 200.0,  # board 0, channel 9: 200.0 ADC/PE
    "0:10": 200.0,  # board 0, channel 10: 200.0 ADC/PE
    "0:11": 200.0,  # board 0, channel 11: 200.0 ADC/PE
    "0:12": 200.0,  # board 0, channel 12: 200.0 ADC/PE
    "0:13": 200.0,  # board 0, channel 13: 200.0 ADC/PE
    "0:14": 200.0,  # board 0, channel 14: 200.0 ADC/PE
    "0:15": 200.0,  # board 0, channel 15: 200.0 ADC/PE
}

ctx.set_config({"gain_adc_per_pe": gain_config})

# 处理数据（DataFrame 会自动添加 area_pe 和 height_pe 列）
df = ctx.get_array(run_id="demo_run", target="df")

print(f"配置的增益值: {gain_config}")
print(f"\nDataFrame 列名: {df.dtype.names}")
print("\n配置增益后会自动添加:")
print("  - area_pe: 峰面积（单位：光电子数）")
print("  - height_pe: 峰高（单位：光电子数）")
