#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
示例：使用 list_plugin_configs() 查看插件配置

这个示例展示了如何使用 Context.list_plugin_configs() 方法来：
1. 查看所有插件的配置选项
2. 查看特定插件的配置
3. 以编程方式获取配置信息
"""

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.standard import (
    RawFilesPlugin,
    WaveformsPlugin,
    StWaveformsPlugin,
)


def main():
    # 创建 Context 并注册插件
    ctx = Context(storage_dir="./strax_data")
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        StWaveformsPlugin(),
    )

    # 示例 1: 列出所有插件的配置选项
    print("=" * 80)
    print("示例 1: 列出所有插件的配置选项")
    print("=" * 80)
    ctx.list_plugin_configs()

    # 示例 2: 设置配置后查看变化
    print("\n" + "=" * 80)
    print("示例 2: 设置配置后查看变化")
    print("=" * 80)
    ctx.set_config({
        'n_channels': 4,
        'data_root': 'custom_DAQ',
    })
    ctx.set_config({'channel_executor': 'process'}, plugin_name='waveforms')
    ctx.list_plugin_configs()

    # 示例 3: 只查看特定插件
    print("\n" + "=" * 80)
    print("示例 3: 只查看特定插件的配置")
    print("=" * 80)
    ctx.list_plugin_configs(plugin_name='waveforms')

    # 示例 4: 以编程方式获取配置信息
    print("\n" + "=" * 80)
    print("示例 4: 以编程方式获取配置信息")
    print("=" * 80)
    config_info = ctx.list_plugin_configs(verbose=False)

    print("获取到的配置信息（字典格式）：")
    for plugin_name, info in config_info.items():
        print(f"\n{plugin_name}:")
        print(f"  - 类: {info['class']}")
        print(f"  - 配置选项数: {len(info['options'])}")
        if info['options']:
            modified = sum(1 for opt in info['options'].values()
                         if not opt.get('is_default', True))
            print(f"  - 已修改: {modified}/{len(info['options'])}")


if __name__ == "__main__":
    main()
