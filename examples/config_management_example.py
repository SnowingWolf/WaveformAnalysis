#!/usr/bin/env python
"""
配置管理综合示例

这个示例展示了如何使用 WaveformAnalysis 的配置管理功能：
1. list_plugin_configs() - 查看所有插件可用的配置选项
2. show_config() - 查看当前配置值和使用情况
3. set_config() - 设置全局和插件特定配置
"""

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin,
    WaveformsPlugin,
)


def main():
    print("=" * 80)
    print("配置管理综合示例")
    print("=" * 80)

    # ====================================================================
    # 1. 创建 Context 并注册插件
    # ====================================================================
    print("\n步骤 1: 创建 Context 并注册插件")
    print("-" * 80)

    ctx = Context(storage_dir="./strax_data")
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
    )
    print("✓ 已注册 2 个插件: raw_files, st_waveforms")

    # ====================================================================
    # 2. 查看所有插件的配置选项（了解有哪些配置可用）
    # ====================================================================
    print("\n\n步骤 2: 查看所有插件的配置选项")
    print("-" * 80)
    print("使用 list_plugin_configs() 查看所有插件提供的配置选项...")
    input("\n按 Enter 继续...")
    ctx.list_plugin_configs()

    # ====================================================================
    # 3. 设置全局配置
    # ====================================================================
    print("\n\n步骤 3: 设置全局配置")
    print("-" * 80)
    print("设置一些全局配置项（会影响多个插件）:")
    print("  - n_channels: 4")
    print("  - data_root: 'DAQ_v2'")
    print("  - start_channel_slice: 10")

    ctx.set_config(
        {
            "n_channels": 4,
            "data_root": "DAQ_v2",
            "start_channel_slice": 10,
        }
    )
    print("\n✓ 全局配置已设置")

    # ====================================================================
    # 4. 查看配置使用情况
    # ====================================================================
    print("\n\n步骤 4: 查看配置使用情况")
    print("-" * 80)
    print("使用 show_config() 查看配置项被哪些插件使用...")
    input("\n按 Enter 继续...")
    ctx.show_config()

    # ====================================================================
    # 5. 设置插件特定配置
    # ====================================================================
    print("\n\n步骤 5: 设置插件特定配置")
    print("-" * 80)
    print("为 waveforms 插件设置特定配置:")
    print("  - channel_executor: 'process'")
    print("  - channel_workers: 2")

    ctx.set_config(
        {
            "channel_executor": "process",
            "channel_workers": 2,
        },
        plugin_name="waveforms",
    )
    print("\n✓ 插件特定配置已设置")

    # ====================================================================
    # 6. 再次查看配置（观察插件特定配置）
    # ====================================================================
    print("\n\n步骤 6: 查看更新后的配置")
    print("-" * 80)
    print("注意观察「插件特定配置」部分...")
    input("\n按 Enter 继续...")
    ctx.show_config()

    # ====================================================================
    # 7. 查看特定插件的详细配置
    # ====================================================================
    print("\n\n步骤 7: 查看特定插件的详细配置")
    print("-" * 80)
    print("使用 show_config('waveforms') 查看单个插件的详细配置...")
    input("\n按 Enter 继续...")
    ctx.show_config("waveforms")

    # ====================================================================
    # 8. 对比两种配置查看方法
    # ====================================================================
    print("\n\n步骤 8: 对比两种配置查看方法")
    print("-" * 80)
    print("\nlist_plugin_configs() vs show_config() 的区别：\n")
    print("📦 list_plugin_configs():")
    print("   • 显示所有可用的配置选项（包括默认值）")
    print("   • 适合了解插件支持哪些配置")
    print("   • 显示帮助文本和类型信息")
    print("   • 区分默认值和已修改的配置\n")

    print("⚙️  show_config():")
    print("   • 显示当前实际使用的配置值")
    print("   • 自动识别配置项被哪些插件使用")
    print("   • 区分全局配置、插件特定配置和未使用配置")
    print("   • 适合诊断配置问题\n")

    # ====================================================================
    # 9. 演示配置错误检测
    # ====================================================================
    print("\n\n步骤 9: 演示配置错误检测")
    print("-" * 80)
    print("设置一个拼写错误的配置项（未被任何插件使用）:")
    print("  - n_chanels: 8  # 正确应该是 n_channels")

    ctx.set_config({"n_chanels": 8})  # 故意拼写错误
    print("\n✓ 配置已设置")

    print("\n使用 show_config() 可以发现这个错误...")
    input("\n按 Enter 继续...")
    ctx.show_config()

    print("\n" + "=" * 80)
    print("示例完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
