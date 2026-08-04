#!/usr/bin/env python
"""
测试 hit_merged_features 的两种归一化模式

展示 normalize_to_pe 配置的两种模式：
1. normalize_to_pe=False (默认): area/height 保持 ADC，area_pe/height_pe 输出 PE
2. normalize_to_pe=True: area/height 直接归一化为 PE，area_pe/height_pe 为 NaN
"""

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    HitFinderPlugin,
    HitMergedFeaturesPlugin,
    HitMergePlugin,
    RawFilesPlugin,
    WaveformsPlugin,
)


def test_mode_1_default():
    """模式 1: normalize_to_pe=False (默认，向后兼容)"""
    print("=" * 80)
    print("模式 1: normalize_to_pe=False (默认)")
    print("=" * 80)

    ctx = Context(storage_dir="./strax_data")
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        HitFinderPlugin(),
        HitMergePlugin(),
        HitMergedFeaturesPlugin(),
    )

    # 设置增益，但不设置 normalize_to_pe（默认为 False）
    gain_config = {
        "0:9": 200.0,
        "0:10": 200.0,
        "0:11": 200.0,
        "0:12": 200.0,
        "0:13": 200.0,
        "0:14": 200.0,
        "0:15": 200.0,
    }

    ctx.set_config({"gain_adc_per_pe": gain_config})

    print("\n配置:")
    print(f"  gain_adc_per_pe: {gain_config}")
    print("  normalize_to_pe: False (默认)")

    print("\n预期结果:")
    print("  - area/height: ADC 单位（原始值）")
    print("  - area_pe/height_pe: PE 单位（校准值）")

    # 处理数据
    features = ctx.get_array(run_id="demo_run", target="hit_merged_features")

    print(f"\n✓ 数据处理完成，共 {len(features)} 条记录")

    # 显示示例数据
    if len(features) > 0:
        print("\n数据示例（前3条）:")
        print("-" * 80)
        print(
            f"{'Ch':<4} {'Area(ADC)':<12} {'Area(PE)':<12} {'Height(ADC)':<12} {'Height(PE)':<12}"
        )
        print("-" * 80)
        for i in range(min(3, len(features))):
            ch = features[i]["channel"]
            area = features[i]["area"]
            area_pe = features[i]["area_pe"]
            height = features[i]["height"]
            height_pe = features[i]["height_pe"]
            print(f"{ch:<4} {area:<12.1f} {area_pe:<12.3f} {height:<12.1f} {height_pe:<12.3f}")


def test_mode_2_normalize():
    """模式 2: normalize_to_pe=True (直接归一化)"""
    print("\n\n" + "=" * 80)
    print("模式 2: normalize_to_pe=True")
    print("=" * 80)

    ctx = Context(storage_dir="./strax_data")
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        HitFinderPlugin(),
        HitMergePlugin(),
        HitMergedFeaturesPlugin(),
    )

    # 设置增益并启用直接归一化
    gain_config = {
        "0:9": 200.0,
        "0:10": 200.0,
        "0:11": 200.0,
        "0:12": 200.0,
        "0:13": 200.0,
        "0:14": 200.0,
        "0:15": 200.0,
    }

    ctx.set_config({"gain_adc_per_pe": gain_config, "normalize_to_pe": True})  # 启用直接归一化

    print("\n配置:")
    print(f"  gain_adc_per_pe: {gain_config}")
    print("  normalize_to_pe: True")

    print("\n预期结果:")
    print("  - area/height: PE 单位（已归一化）")
    print("  - area_pe/height_pe: NaN（因为 area/height 已经是 PE）")

    # 处理数据
    features = ctx.get_array(run_id="demo_run", target="hit_merged_features")

    print(f"\n✓ 数据处理完成，共 {len(features)} 条记录")

    # 显示示例数据
    if len(features) > 0:
        print("\n数据示例（前3条）:")
        print("-" * 80)
        print(f"{'Ch':<4} {'Area(PE)':<12} {'Area_PE':<12} {'Height(PE)':<12} {'Height_PE':<12}")
        print("-" * 80)
        for i in range(min(3, len(features))):
            ch = features[i]["channel"]
            area = features[i]["area"]
            area_pe = features[i]["area_pe"]
            height = features[i]["height"]
            height_pe = features[i]["height_pe"]
            print(f"{ch:<4} {area:<12.3f} {area_pe:<12} {height:<12.3f} {height_pe:<12}")


def compare_modes():
    """对比两种模式的差异"""
    print("\n\n" + "=" * 80)
    print("两种模式对比")
    print("=" * 80)

    print("\n| 配置项 | 模式 1 (默认) | 模式 2 (归一化) |")
    print("|--------|---------------|-----------------|")
    print("| normalize_to_pe | False | True |")
    print("| area 单位 | ADC | PE |")
    print("| height 单位 | ADC | PE |")
    print("| area_pe 单位 | PE | NaN |")
    print("| height_pe 单位 | PE | NaN |")
    print("| 向后兼容 | ✅ 是 | ⚠️ 否 |")
    print("| 数据冗余 | 有（ADC+PE） | 无 |")

    print("\n推荐使用场景:")
    print("  • 模式 1: 需要保留原始 ADC 值，或与现有代码兼容")
    print("  • 模式 2: 新项目，只关心 PE 单位，不需要原始 ADC 值")


def main():
    print("\n" + "=" * 80)
    print("hit_merged_features 归一化模式测试")
    print("=" * 80)

    try:
        test_mode_1_default()
    except Exception as e:
        print(f"\n✗ 模式 1 测试失败: {e}")

    try:
        test_mode_2_normalize()
    except Exception as e:
        print(f"\n✗ 模式 2 测试失败: {e}")

    compare_modes()

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
