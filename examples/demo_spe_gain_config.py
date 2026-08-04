#!/usr/bin/env python
"""
单光子增益（SPE Gain）配置示例

本示例展示如何设置和使用单光子增益参数 gain_adc_per_pe。
gain_adc_per_pe 表示每个光电子对应的 ADC 计数值。

配置后，DataFrame 插件会自动添加校准后的列：
- area_pe: 峰面积（单位：光电子数）
- height_pe: 峰高（单位：光电子数）
"""

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    BasicFeaturesPlugin,
    DataFramePlugin,
    RawFilesPlugin,
    WaveformsPlugin,
)


def example_1_global_gain_config():
    """
    示例 1: 全局增益配置

    为所有通道设置统一的增益值。
    """
    print("=" * 80)
    print("示例 1: 全局增益配置")
    print("=" * 80)

    ctx = Context(storage_dir="./strax_data")
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        BasicFeaturesPlugin(),
        DataFramePlugin(),
    )

    # 方式 1: 为所有通道设置相同的增益（假设所有通道增益为 15.0 ADC/PE）
    gain_config = {
        "0:0": 15.0,  # board 0, channel 0
        "0:1": 15.0,  # board 0, channel 1
        "0:2": 15.0,  # board 0, channel 2
        "0:3": 15.0,  # board 0, channel 3
    }

    ctx.set_config({"gain_adc_per_pe": gain_config})

    print("✓ 已设置全局增益配置")
    print(f"  配置内容: {gain_config}")
    print("\n使用 ctx.show_config() 查看配置...")
    ctx.show_config("df")


def example_2_per_channel_gain_config():
    """
    示例 2: 逐通道增益配置

    为每个通道设置不同的增益值（真实场景）。
    """
    print("\n" + "=" * 80)
    print("示例 2: 逐通道增益配置（不同通道不同增益）")
    print("=" * 80)

    ctx = Context(storage_dir="./strax_data")
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        BasicFeaturesPlugin(),
        DataFramePlugin(),
    )

    # 方式 2: 为每个通道设置不同的增益（基于实际标定结果）
    gain_config = {
        "0:0": 12.5,  # board 0, channel 0: 12.5 ADC/PE
        "0:1": 13.2,  # board 0, channel 1: 13.2 ADC/PE
        "0:2": 11.8,  # board 0, channel 2: 11.8 ADC/PE
        "0:3": 14.1,  # board 0, channel 3: 14.1 ADC/PE
    }

    ctx.set_config({"gain_adc_per_pe": gain_config})

    print("✓ 已设置逐通道增益配置")
    print("  配置内容:")
    for ch, gain in gain_config.items():
        print(f"    {ch}: {gain} ADC/PE")


def example_3_plugin_specific_gain_config():
    """
    示例 3: 插件特定增益配置

    直接为 DataFrame 插件设置增益配置。
    """
    print("\n" + "=" * 80)
    print("示例 3: 插件特定增益配置")
    print("=" * 80)

    ctx = Context(storage_dir="./strax_data")
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        BasicFeaturesPlugin(),
        DataFramePlugin(),
    )

    # 方式 3: 直接为 df 插件设置增益
    gain_config = {
        "0:0": 15.3,
        "0:1": 14.7,
        "0:2": 15.8,
        "0:3": 15.1,
    }

    ctx.set_config({"gain_adc_per_pe": gain_config}, plugin_name="df")

    print("✓ 已为 df 插件设置增益配置")
    print(f"  配置内容: {gain_config}")


def example_4_run_specific_gain_config():
    """
    示例 4: Run 特定增益配置

    在处理数据时为特定 run 设置增益。
    """
    print("\n" + "=" * 80)
    print("示例 4: Run 特定增益配置")
    print("=" * 80)

    ctx = Context(storage_dir="./strax_data")
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        BasicFeaturesPlugin(),
        DataFramePlugin(),
    )

    # 方式 4: 通过 run 配置设置增益
    # 这种方式允许不同的 run 使用不同的增益值

    # 假设你有一个 run_config.yaml 文件，内容如下：
    run_config_example = """
    plugins:
      df:
        gain_adc_per_pe:
          "0:0": 15.0
          "0:1": 15.0
          "0:2": 15.0
          "0:3": 15.0
    """

    print("Run 配置文件示例 (run_config.yaml):")
    print(run_config_example)
    print("\n注意：这种方式需要在 DAQ 目录下创建 run_config.yaml 文件")


def example_5_effect_of_gain():
    """
    示例 5: 增益配置的效果

    展示配置增益后 DataFrame 中会增加哪些列。
    """
    print("\n" + "=" * 80)
    print("示例 5: 增益配置的效果")
    print("=" * 80)

    print("\n配置 gain_adc_per_pe 后，DataFrame 会自动添加以下校准列：\n")
    print("  原始列 (ADC单位) → 校准列 (PE单位)")
    print("  " + "-" * 50)
    print("  area             → area_pe      (峰面积，单位：光电子数)")
    print("  height           → height_pe    (峰高，单位：光电子数)")
    print()
    print("转换公式:")
    print("  area_pe = area / gain_adc_per_pe")
    print("  height_pe = height / gain_adc_per_pe")
    print()
    print("示例：如果某个峰的 area=150 ADC，gain_adc_per_pe=15.0")
    print("      则 area_pe = 150 / 15.0 = 10.0 PE（即 10 个光电子）")


def example_6_multi_board_config():
    """
    示例 6: 多板卡配置

    为多个板卡设置增益。
    """
    print("\n" + "=" * 80)
    print("示例 6: 多板卡增益配置")
    print("=" * 80)

    ctx = Context(storage_dir="./strax_data")
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        BasicFeaturesPlugin(),
        DataFramePlugin(),
    )

    # 方式 6: 多板卡配置
    gain_config = {
        # Board 0
        "0:0": 12.5,
        "0:1": 13.2,
        "0:2": 11.8,
        "0:3": 14.1,
        # Board 1
        "1:0": 15.3,
        "1:1": 14.7,
        "1:2": 15.8,
        "1:3": 15.1,
    }

    ctx.set_config({"gain_adc_per_pe": gain_config})

    print("✓ 已设置多板卡增益配置")
    print(f"  Board 0: {len([k for k in gain_config if k.startswith('0:')])} 个通道")
    print(f"  Board 1: {len([k for k in gain_config if k.startswith('1:')])} 个通道")


def main():
    """运行所有示例"""
    print("\n" + "=" * 80)
    print("单光子增益（SPE Gain）配置完整示例")
    print("=" * 80)
    print("\ngain_adc_per_pe 参数说明:")
    print("  • 含义：每个光电子对应的 ADC 计数值")
    print("  • 单位：ADC counts / photoelectron")
    print("  • 格式：字典，键为 'board:channel' 格式")
    print("  • 作用：配置后自动添加 area_pe 和 height_pe 列")
    print()

    example_1_global_gain_config()
    example_2_per_channel_gain_config()
    example_3_plugin_specific_gain_config()
    example_4_run_specific_gain_config()
    example_5_effect_of_gain()
    example_6_multi_board_config()

    print("\n" + "=" * 80)
    print("示例完成！")
    print("=" * 80)
    print("\n推荐使用方式:")
    print("  1. 如果所有 run 使用相同增益 → 使用全局配置（示例 1-3）")
    print("  2. 如果不同 run 使用不同增益 → 使用 run_config.yaml（示例 4）")
    print("  3. 增益值通常通过单光子响应标定获得")
    print()


if __name__ == "__main__":
    main()
