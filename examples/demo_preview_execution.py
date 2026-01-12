#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
演示 preview_execution() 功能 - 在运行前确认 lineage

本示例展示如何使用 Context.preview_execution() 方法在实际执行数据处理之前：
1. 查看将要执行的插件链
2. 了解配置参数
3. 查看依赖关系树
4. 确认缓存状态（哪些已缓存，哪些需要计算）
"""

import sys
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin import (
    RawFilesPlugin,
    WaveformsPlugin,
    StWaveformsPlugin,
    FilteredWaveformsPlugin,
    SignalPeaksPlugin,
)


def example_basic_preview():
    """示例 1: 基本预览功能"""
    print("\n" + "=" * 70)
    print("示例 1: 基本预览功能")
    print("=" * 70 + "\n")

    # 创建 Context 并注册插件
    ctx = Context(storage_dir="./test_preview_data")

    plugins = [
        RawFilesPlugin(),
        WaveformsPlugin(),
        StWaveformsPlugin(),
        FilteredWaveformsPlugin(),
        SignalPeaksPlugin(),
    ]

    for plugin in plugins:
        ctx.register_plugin(plugin)

    # 设置配置
    ctx.set_config({
        "data_root": "DAQ",
        "n_channels": 2,
        "start_channel_slice": 6,
    })

    ctx.set_config({
        "filter_type": "SG",
        "sg_window_size": 11,
        "sg_poly_order": 2,
    }, plugin_name="filtered_waveforms")

    ctx.set_config({
        "height": 30.0,
        "prominence": 0.7,
        "use_derivative": True,
    }, plugin_name="signal_peaks")

    # 预览执行计划
    print("调用 ctx.preview_execution('run_001', 'signal_peaks')\n")
    result = ctx.preview_execution('run_001', 'signal_peaks')

    # 返回结果也是一个字典，可以程序化使用
    print("\n返回的结果字典包含:")
    print(f"  - target: {result['target']}")
    print(f"  - run_id: {result['run_id']}")
    print(f"  - execution_plan: {result['execution_plan']}")
    print(f"  - 共 {len(result['cache_status'])} 个插件的缓存状态")
    print(f"  - 共 {len(result['configs'])} 个插件有自定义配置")


def example_different_verbosity():
    """示例 2: 不同详细程度的预览"""
    print("\n" + "=" * 70)
    print("示例 2: 不同详细程度的预览")
    print("=" * 70 + "\n")

    ctx = Context(storage_dir="./test_preview_data")

    for plugin in [RawFilesPlugin(), WaveformsPlugin(), StWaveformsPlugin(),
                   FilteredWaveformsPlugin(), SignalPeaksPlugin()]:
        ctx.register_plugin(plugin)

    ctx.set_config({"data_root": "DAQ", "n_channels": 2})
    ctx.set_config({"filter_type": "BW", "lowcut": 0.05, "highcut": 0.8},
                   plugin_name="filtered_waveforms")

    # verbose=0: 简洁模式
    print("\n>>> verbose=0 (简洁模式):")
    ctx.preview_execution('run_001', 'signal_peaks', verbose=0)

    # verbose=1: 标准模式（默认）
    print("\n>>> verbose=1 (标准模式):")
    ctx.preview_execution('run_001', 'signal_peaks', verbose=1)

    # verbose=2: 详细模式
    print("\n>>> verbose=2 (详细模式，显示默认值):")
    ctx.preview_execution('run_001', 'signal_peaks', verbose=2)


def example_selective_display():
    """示例 3: 选择性显示内容"""
    print("\n" + "=" * 70)
    print("示例 3: 选择性显示内容")
    print("=" * 70 + "\n")

    ctx = Context(storage_dir="./test_preview_data")

    for plugin in [RawFilesPlugin(), WaveformsPlugin(), StWaveformsPlugin(),
                   FilteredWaveformsPlugin(), SignalPeaksPlugin()]:
        ctx.register_plugin(plugin)

    ctx.set_config({"data_root": "DAQ", "n_channels": 2})

    # 只显示执行计划和缓存状态
    print(">>> 只显示执行计划和缓存状态（不显示依赖树和配置）:")
    ctx.preview_execution(
        'run_001', 'signal_peaks',
        show_tree=False,
        show_config=False,
        show_cache=True
    )

    # 只显示依赖树
    print("\n>>> 只显示依赖树:")
    ctx.preview_execution(
        'run_001', 'signal_peaks',
        show_tree=True,
        show_config=False,
        show_cache=False
    )


def example_programmatic_use():
    """示例 4: 程序化使用预览结果"""
    print("\n" + "=" * 70)
    print("示例 4: 程序化使用预览结果")
    print("=" * 70 + "\n")

    ctx = Context(storage_dir="./test_preview_data")

    for plugin in [RawFilesPlugin(), WaveformsPlugin(), StWaveformsPlugin(),
                   FilteredWaveformsPlugin(), SignalPeaksPlugin()]:
        ctx.register_plugin(plugin)

    ctx.set_config({"data_root": "DAQ", "n_channels": 2})

    # 获取预览结果但不打印（通过重定向或使用返回值）
    result = ctx.preview_execution('run_001', 'signal_peaks')

    # 程序化分析结果
    print("\n程序化分析预览结果：\n")

    # 检查需要计算的插件数量
    needs_compute = [
        plugin for plugin, status in result['cache_status'].items()
        if status['needs_compute']
    ]

    print(f"✓ 目标数据: {result['target']}")
    print(f"✓ 执行计划包含 {len(result['execution_plan'])} 个步骤")
    print(f"✓ 需要计算的插件: {len(needs_compute)} 个")
    if needs_compute:
        print(f"  → {', '.join(needs_compute)}")

    # 检查是否有自定义配置
    if result['configs']:
        print(f"✓ 有 {len(result['configs'])} 个插件使用自定义配置:")
        for plugin_name, config in result['configs'].items():
            print(f"  → {plugin_name}: {len(config)} 个自定义参数")
    else:
        print("✓ 所有插件使用默认配置")

    # 基于预览结果做决策
    print("\n基于预览结果的决策：")
    if len(needs_compute) > 3:
        print(f"⚠️ 需要计算 {len(needs_compute)} 个插件，可能需要较长时间")
        print("   建议: 确认配置无误后再执行")
    else:
        print("✓ 大部分数据已缓存，执行会很快")


def example_workflow():
    """示例 5: 完整工作流 - 预览 → 确认 → 执行"""
    print("\n" + "=" * 70)
    print("示例 5: 完整工作流 - 预览 → 确认 → 执行")
    print("=" * 70 + "\n")

    ctx = Context(storage_dir="./test_preview_data")

    for plugin in [RawFilesPlugin(), WaveformsPlugin(), StWaveformsPlugin(),
                   FilteredWaveformsPlugin(), SignalPeaksPlugin()]:
        ctx.register_plugin(plugin)

    ctx.set_config({
        "data_root": "DAQ",
        "n_channels": 2,
        "start_channel_slice": 6,
    })

    ctx.set_config({"filter_type": "SG"}, plugin_name="filtered_waveforms")
    ctx.set_config({"height": 30.0}, plugin_name="signal_peaks")

    # 步骤 1: 预览执行计划
    print("步骤 1: 预览执行计划\n")
    result = ctx.preview_execution('run_001', 'signal_peaks', verbose=1)

    # 步骤 2: 用户确认（可选）
    print("\n步骤 2: 用户确认")
    try:
        # 在真实应用中可以添加交互式确认
        user_input = input("\n是否继续执行? (y/n, 默认 n): ").strip().lower()
        if user_input != 'y':
            print("✗ 用户取消执行")
            return
    except (EOFError, KeyboardInterrupt):
        print("\n✗ 用户取消执行")
        return

    # 步骤 3: 执行（如果有真实数据）
    print("\n步骤 3: 执行数据处理")
    try:
        # 注意：如果没有真实数据文件，这里会失败
        # data = ctx.get_data('run_001', 'signal_peaks')
        # print(f"✓ 成功获取数据: {type(data)}")
        print("（跳过实际执行，因为可能没有真实数据文件）")
    except FileNotFoundError as e:
        print(f"✗ 数据文件不存在: {e}")
        print("   这是正常的，因为示例不包含真实数据")


def example_compare_multiple_targets():
    """示例 6: 比较不同目标的执行计划"""
    print("\n" + "=" * 70)
    print("示例 6: 比较不同目标的执行计划")
    print("=" * 70 + "\n")

    ctx = Context(storage_dir="./test_preview_data")

    for plugin in [RawFilesPlugin(), WaveformsPlugin(), StWaveformsPlugin(),
                   FilteredWaveformsPlugin(), SignalPeaksPlugin()]:
        ctx.register_plugin(plugin)

    ctx.set_config({"data_root": "DAQ", "n_channels": 2})

    # 比较不同目标的执行计划复杂度
    targets = ['st_waveforms', 'filtered_waveforms', 'signal_peaks']

    print("比较不同目标的执行计划复杂度:\n")
    for target in targets:
        result = ctx.preview_execution('run_001', target, show_tree=False,
                                       show_config=False, show_cache=False,
                                       verbose=0)
        print(f"  {target}: {len(result['execution_plan'])} 个步骤")


def main():
    """主函数 - 运行所有示例"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "   preview_execution() 功能演示".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")

    try:
        # 示例 1: 基本预览
        example_basic_preview()

        # 示例 2: 不同详细程度
        example_different_verbosity()

        # 示例 3: 选择性显示
        example_selective_display()

        # 示例 4: 程序化使用
        example_programmatic_use()

        # 示例 5: 完整工作流
        example_workflow()

        # 示例 6: 比较多个目标
        example_compare_multiple_targets()

        print("\n" + "=" * 70)
        print("✓ 所有示例运行完成!")
        print("=" * 70)

        print("\n使用提示:")
        print("  1. 在调用 get_data() 前先 preview_execution() 确认计划")
        print("  2. 检查配置参数是否正确")
        print("  3. 了解哪些数据已缓存，避免重复计算")
        print("  4. 使用 verbose 参数控制显示详细程度")
        print("  5. 返回的字典可用于程序化决策")

        return 0

    except Exception as e:
        print(f"\n✗ 示例运行出错: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
