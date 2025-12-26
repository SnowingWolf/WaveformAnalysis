#!/usr/bin/env python3
"""
快速演示脚本：展示如何选择不加载波形
"""

import sys
from pathlib import Path

# 添加项目到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from waveform_analysis import WaveformDataset


def main():
    print("\n" + "=" * 70)
    print("演示：选择不加载原始波形以节省内存")
    print("=" * 70)

    # 方法 1: 加载波形（默认）
    print("\n📌 方法 1: 加载波形（load_waveforms=True，默认）")
    print("-" * 70)
    print("""
    dataset = WaveformDataset(
        char="50V_OV_circulation_20thr",
        n_channels=2,
        load_waveforms=True  # 默认值
    )
    """)
    print("✅ 优点: 可以访问原始波形数据，用于可视化和详细分析")
    print("❌ 缺点: 消耗大量内存（通常 GB 级别）")

    # 方法 2: 不加载波形
    print("\n📌 方法 2: 不加载波形（load_waveforms=False）")
    print("-" * 70)
    print("""
    dataset = WaveformDataset(
        char="50V_OV_circulation_20thr",
        n_channels=2,
        load_waveforms=False  # 关键：不加载波形！
    )
    """)
    print("✅ 优点: 节省内存（通常 70-80% 的节省）")
    print("✅ 优点: 仍然保留所有统计特征（峰值、电荷等）")
    print("❌ 缺点: 不能访问原始波形数据")

    # 工作流演示
    print("\n📌 完整工作流对比")
    print("-" * 70)
    print("\n方案 A: 需要波形可视化")
    print("""
    dataset = WaveformDataset(..., load_waveforms=True)
    dataset.load_raw_data()        # ✅ 加载文件
           .extract_waveforms()     # ✅ 加载波形到内存
           .structure_waveforms()   # ✅ 组织波形数据
           .build_waveform_features()  # ✅ 计算特征
           .build_dataframe()       # ✅ 创建 DataFrame
    
    # 获取波形数据
    wave, baseline = dataset.get_waveform_at(0)  # ✅ 有效
    """)

    print("\n方案 B: 仅需要统计特征")
    print("""
    dataset = WaveformDataset(..., load_waveforms=False)
    dataset.load_raw_data()        # ✅ 加载文件列表
           .extract_waveforms()     # ⏭️  被跳过（节省内存）
           .structure_waveforms()   # ⏭️  被跳过（节省内存）
           .build_waveform_features()  # ✅ 从 CSV 计算特征
           .build_dataframe()       # ✅ 创建 DataFrame
    
    # 获取特征和统计数据
    df = dataset.get_paired_events()  # ✅ 有效（包含峰值、电荷等）
    dataset.get_waveform_at(0)        # ❌ 返回 None（波形未加载）
    """)

    # 实际使用建议
    print("\n💡 选择建议")
    print("-" * 70)
    print("""
    使用 load_waveforms=True 如果你需要:
    • 可视化单个事件的波形
    • 进行波形形状分析
    • 检查数据质量
    
    使用 load_waveforms=False 如果你:
    • 内存有限（笔记本或共享服务器）
    • 只关心统计特征（峰值、电荷、时间差）
    • 处理大型数据集（>1 GB CSV 文件）
    • 想要快速处理而不关心个别波形
    """)

    # 访问可用的数据
    print("\n📊 可访问的数据对比")
    print("-" * 70)
    print("""
    无论 load_waveforms 设置如何，都可以访问:
    ✅ DataFrame: dataset.get_paired_events() 
    ✅ 峰值: dataset.get_peaks() 或 df['peak_chX']
    ✅ 电荷: df['charge_chX']
    ✅ 时间戳: df['timestamp']
    ✅ 通道信息: df['channels']
    
    仅在 load_waveforms=True 时可访问:
    ✅ 原始波形: dataset.get_waveform_at(idx, channel)
    """)

    # 示例代码
    print("\n💻 快速示例")
    print("-" * 70)
    print("""
    # 节省内存的处理方式
    dataset = WaveformDataset(
        char="50V_OV_circulation_20thr",
        load_waveforms=False
    )
    
    dataset.load_raw_data()
    dataset.extract_waveforms()
    dataset.build_waveform_features()
    dataset.build_dataframe()
    dataset.pair_events()
    
    # 获取结果
    df = dataset.get_paired_events()
    
    # 分析特征
    print(f"事件数: {len(df)}")
    print(f"平均峰值: {df['peak_ch6'].mean():.1f} ADC")
    print(f"平均电荷: {df['charge_ch6'].mean():.1f} ADC")
    
    # 这会返回 None（因为未加载波形）
    wave = dataset.get_waveform_at(0)
    # ⚠️  波形数据未加载（load_waveforms=False）
    """)

    print("\n" + "=" * 70)
    print("更多信息，请查看:")
    print("  • examples/skip_waveforms.py - 完整示例")
    print("  • docs/USAGE.md#内存优化 - 详细文档")
    print("  • tests/test_skip_waveforms.py - 测试用例")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
