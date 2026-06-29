#!/usr/bin/env python3
"""
S1S2PairAccessor 使用示例

演示如何使用 S1S2PairAccessor 来：
1. 查询和过滤 S1-S2 配对
2. 提取波形数据
3. 可视化配对波形

替代用户原有的手动函数：
- get_peaklet_waveform_by_peak_id() → accessor.get_waveform()
- plot_s1_s2_pair_on_timeline() → accessor.plot_pair()
"""

import matplotlib.pyplot as plt
import numpy as np

# 注意：这个示例需要实际的 context 和 run_id
# 如果你有真实数据，可以按照以下方式使用


def example_basic_usage(context, run_id):
    """基础用法示例"""
    from waveform_analysis.utils import S1S2PairAccessor

    print("=" * 60)
    print("示例 1: 基础查询")
    print("=" * 60)

    # 创建访问器（默认使用 s1_s2_pairs）
    accessor = S1S2PairAccessor(context, run_id=run_id)

    # 查看总配对数
    print(f"总配对数: {len(accessor.pairs)}")

    # 查询单个配对
    if len(accessor.pairs) > 0:
        pair = accessor.get_pair(int(accessor.pairs[0]["pair_id"]))
        print(f"\n配对 {pair['pair_id']} 信息:")
        print(f"  S1 peak_id: {pair['s1_peak_id']}")
        print(f"  S2 peak_id: {pair['s2_peak_id']}")
        print(f"  Drift time: {pair['drift_time_ns']:.1f} ns")
        print(f"  log10(S2/S1): {pair['log10_s2_s1']:.2f}")

    # 查询某个 S1 的所有配对
    if len(accessor.pairs) > 0:
        s1_peak_id = int(accessor.pairs[0]["s1_peak_id"])
        pairs_for_s1 = accessor.get_pairs_for_s1(s1_peak_id)
        print(f"\nS1 peak {s1_peak_id} 有 {len(pairs_for_s1)} 个配对候选")


def example_filtering(context, run_id):
    """过滤示例"""
    from waveform_analysis.utils import S1S2PairAccessor

    print("\n" + "=" * 60)
    print("示例 2: 过滤配对")
    print("=" * 60)

    accessor = S1S2PairAccessor(context, run_id=run_id)

    # 方法 1: 使用 build_mask()
    mask = accessor.build_mask(
        drift_time_ns_range=(10000, 50000),  # 10-50 us
        log10_s2_s1_range=(1.5, None),  # log10(S2/S1) > 1.5
    )
    filtered = accessor.pairs[mask]
    print(f"方法 1 (build_mask): 找到 {len(filtered)} 个符合条件的配对")

    # 方法 2: 使用 filter_pairs() 快捷方法
    filtered2 = accessor.filter_pairs(
        drift_time_ns_range=(10000, 50000),
        log10_s2_s1_range=(1.5, None),
    )
    print(f"方法 2 (filter_pairs): 找到 {len(filtered2)} 个符合条件的配对")

    # 自定义过滤
    def custom_filter(pairs):
        """自定义：S1 和 S2 面积都大于 100"""
        return (pairs["s1_area"] > 100) & (pairs["s2_area"] > 100)

    filtered3 = accessor.filter_pairs(custom_filter=custom_filter)
    print(f"自定义过滤: 找到 {len(filtered3)} 个符合条件的配对")


def example_waveform_extraction(context, run_id):
    """波形提取示例"""
    from waveform_analysis.utils import S1S2PairAccessor

    print("\n" + "=" * 60)
    print("示例 3: 波形提取")
    print("=" * 60)

    accessor = S1S2PairAccessor(context, run_id=run_id)

    if len(accessor.pairs) > 0:
        pair = accessor.pairs[0]

        # 提取单个 peak 的波形
        s1_wf = accessor.get_waveform(int(pair["s1_peak_id"]))
        if s1_wf:
            print("S1 波形:")
            print(f"  波形长度: {len(s1_wf['waveform'])} 个采样点")
            print(f"  时间起点: {s1_wf['time_start_ns']:.1f} ns")
            print(f"  采样间隔: {s1_wf['dt_ns']:.1f} ns")

        # 提取配对的两个波形
        s1_wf, s2_wf = accessor.get_pair_waveforms(pair)
        print("\n配对波形:")
        print(f"  S1 波形长度: {len(s1_wf['waveform'])}")
        print(f"  S2 波形长度: {len(s2_wf['waveform'])}")

        # 注意：默认返回 view，不应原地修改
        # 如果需要修改，使用 copy=True
        _s1_wf_copy = accessor.get_waveform(int(pair["s1_peak_id"]), copy=True)  # noqa: F841


def example_visualization(context, run_id):
    """可视化示例"""
    from waveform_analysis.utils import S1S2PairAccessor

    print("\n" + "=" * 60)
    print("示例 4: 可视化配对")
    print("=" * 60)

    accessor = S1S2PairAccessor(context, run_id=run_id)

    if len(accessor.pairs) > 0:
        # 单个配对可视化
        pair_id = int(accessor.pairs[0]["pair_id"])
        fig, ax = accessor.plot_pair(pair_id, pad_ns=200)
        plt.savefig(f"output/pair_{pair_id}.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"已保存配对 {pair_id} 的图像")

        # 批量绘制（简单循环）
        filtered = accessor.filter_pairs(drift_time_ns_range=(10000, 50000))
        for _i, pair in enumerate(filtered[:5]):
            fig, _ax = accessor.plot_pair(pair, pad_ns=200)
            fig.savefig(f"output/pair_{pair['pair_id']}.png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            print(f"  已保存配对 {pair['pair_id']}")


def example_pandas_integration(context, run_id):
    """与 pandas 集成示例"""
    from waveform_analysis.utils import S1S2PairAccessor

    print("\n" + "=" * 60)
    print("示例 5: 与 pandas 集成")
    print("=" * 60)

    accessor = S1S2PairAccessor(context, run_id=run_id)

    # 转换为 pandas DataFrame
    try:
        import pandas as pd

        df = pd.DataFrame(accessor.pairs)
        print(f"DataFrame 形状: {df.shape}")
        print("\n前 5 行:")
        print(df.head())

        # pandas 风格的过滤
        high_score = df[df["score_total"] > 0.8] if "score_total" in df.columns else df
        print(f"\n高分配对数: {len(high_score)}")

        # 统计分析
        print("\nDrift time 统计:")
        print(df["drift_time_ns"].describe())

    except ImportError:
        print("需要安装 pandas: pip install pandas")


def main():
    """主函数"""
    print("S1S2PairAccessor 使用示例")
    print("=" * 60)
    print("\n注意：这个示例需要实际的 context 和 run_id")
    print("请在你的分析脚本中按照以下方式使用：\n")

    print("from waveform_analysis.utils import S1S2PairAccessor")
    print("accessor = S1S2PairAccessor(context, run_id='your_run_id')")
    print("\n# 查询配对")
    print("pair = accessor.get_pair(pair_id=42)")
    print("\n# 过滤配对")
    print("filtered = accessor.filter_pairs(drift_time_ns_range=(10000, 50000))")
    print("\n# 绘制配对")
    print("fig, ax = accessor.plot_pair(pair_id=42)")
    print("plt.show()")

    # 如果有实际的 context 和 run_id，可以取消注释以下代码
    # example_basic_usage(context, run_id)
    # example_filtering(context, run_id)
    # example_waveform_extraction(context, run_id)
    # example_visualization(context, run_id)
    # example_pandas_integration(context, run_id)


if __name__ == "__main__":
    main()
