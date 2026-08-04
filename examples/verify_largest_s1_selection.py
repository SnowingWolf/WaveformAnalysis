#!/usr/bin/env python
"""
验证 S1-S2 配对是否按照"最大 S1"逻辑选择
"""

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import (
    HitFinderPlugin,
    HitMergedFeaturesPlugin,
    HitMergePlugin,
    PeakClassificationPlugin,
    PeakletFeaturesPlugin,
    PeakletPlugin,
    PeakletWaveformPlugin,
    PeaksPlugin,
    RawFilesPlugin,
    S1S2PairCandidatesPlugin,
    S1S2PairSelectionPlugin,
    WaveformsPlugin,
)


def verify_largest_s1_logic():
    """验证是否按最大 S1 选择"""
    print("=" * 80)
    print("验证 S1-S2 配对逻辑：是否选择最大 S1")
    print("=" * 80)

    ctx = Context(storage_dir="./strax_data")
    ctx.register(
        RawFilesPlugin(),
        WaveformsPlugin(),
        HitFinderPlugin(),
        HitMergePlugin(),
        HitMergedFeaturesPlugin(),
        PeakletPlugin(),
        PeakletWaveformPlugin(),
        PeakletFeaturesPlugin(),
        PeaksPlugin(),
        PeakClassificationPlugin(),
        S1S2PairCandidatesPlugin(),
        S1S2PairSelectionPlugin(),
    )

    # 明确设置为 largest 模式
    ctx.set_config(
        {
            "selection_mode": "largest",
            "max_drift_time": 50000.0,
        }
    )

    run_id = "demo_run"

    # 获取最终配对
    pairs = ctx.get_data(run_id, "s1_s2_pairs")
    selected = pairs[pairs["selected"]]

    print("\n数据统计:")
    print(f"  总候选数: {len(pairs)}")
    print(f"  选中配对数: {len(selected)}")

    # 验证逻辑
    print("\n" + "=" * 80)
    print("验证：对于每个 S2，是否选择了最大的 S1")
    print("=" * 80)

    # 按 S2 分组
    s2_groups = {}
    for pair in pairs:
        s2_id = int(pair["s2_peak_id"])
        if s2_id not in s2_groups:
            s2_groups[s2_id] = []
        s2_groups[s2_id].append(pair)

    # 检查前 10 个 S2
    violation_count = 0
    check_count = 0

    for s2_id, group in list(s2_groups.items())[:10]:
        if len(group) == 1:
            continue  # 跳过只有一个候选的

        check_count += 1

        # 找到选中的配对
        selected_pairs = [p for p in group if p["selected"]]
        if len(selected_pairs) == 0:
            continue

        selected_pair = selected_pairs[0]
        selected_s1_area = selected_pair["s1_area"]

        # 找到最大 S1 面积
        max_s1_area = max(p["s1_area"] for p in group)

        print(f"\nS2 ID: {s2_id}")
        print(f"  候选数: {len(group)}")
        print(f"  选中的 S1 面积: {selected_s1_area:.1f}")
        print(f"  最大的 S1 面积: {max_s1_area:.1f}")

        # 验证是否选择了最大的
        if abs(selected_s1_area - max_s1_area) > 0.01:
            print("  ❌ 不一致！没有选择最大的 S1")
            violation_count += 1

            # 显示所有候选
            print("\n  所有候选:")
            for p in sorted(group, key=lambda x: -x["s1_area"]):
                marker = "✓" if p["selected"] else " "
                print(
                    f"    {marker} S1_area={p['s1_area']:.1f}, "
                    f"score={p['score_total']:.3f}, selected={p['selected']}"
                )
        else:
            print("  ✅ 正确：选择了最大的 S1")

    print("\n" + "=" * 80)
    print("验证结果")
    print("=" * 80)
    print(f"  检查的 S2 数量: {check_count}")
    print(f"  违反逻辑的数量: {violation_count}")

    if violation_count == 0:
        print("\n✅ 验证通过：所有 S2 都选择了最大的 S1")
    else:
        print(f"\n❌ 验证失败：有 {violation_count} 个 S2 没有选择最大的 S1")

    return violation_count == 0


if __name__ == "__main__":
    success = verify_largest_s1_logic()
    exit(0 if success else 1)
