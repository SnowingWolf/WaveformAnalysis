#!/usr/bin/env python
"""
hit_merged_features performance benchmark script

Measures performance differences before and after optimization
"""

from pathlib import Path
import time

import numpy as np

from tests.utils import DummyContext, make_records
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import (
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
)
from waveform_analysis.core.plugins.builtin.cpu.hit_merged_features import (
    HitMergedFeaturesPlugin,
)


def generate_test_data(n_merged=1000, n_channels=16, avg_components_per_merged=2.5):
    """生成测试用的 hit_merged 和相关数据

    Args:
        n_merged: merged hit 数量
        n_channels: 通道数
        avg_components_per_merged: 每个 merged hit 平均包含的原始 hit 数量
    """
    # 预先生成每个 merged hit 的 component 数量，确保总和精确
    component_counts = []
    remaining = int(n_merged * avg_components_per_merged)
    for _ in range(n_merged):
        # 随机决定这个 merged hit 包含几个原始 hit (1-5)
        if remaining <= 0:
            n_components = 1
        else:
            target = max(1, int(remaining / (n_merged - len(component_counts))))
            n_components = min(max(1, np.random.poisson(target)), 5, remaining)
        component_counts.append(n_components)
        remaining -= n_components

    # 如果还有剩余，随机分配
    while remaining > 0:
        idx = np.random.randint(0, n_merged)
        if component_counts[idx] < 5:
            component_counts[idx] += 1
            remaining -= 1

    n_hits_total = sum(component_counts)

    merged = np.zeros(n_merged, dtype=HIT_MERGED_DTYPE)
    hits = np.zeros(n_hits_total, dtype=THRESHOLD_HIT_DTYPE)

    # 生成 component 映射
    component_list = []
    hit_idx = 0

    for merged_idx in range(n_merged):
        n_components = component_counts[merged_idx]

        channel = np.random.randint(0, n_channels)
        record_id = merged_idx

        # 填充 merged 数据
        merged[merged_idx]["record_id"] = record_id
        merged[merged_idx]["board"] = 0
        merged[merged_idx]["channel"] = channel
        merged[merged_idx]["position"] = 50
        merged[merged_idx]["timestamp"] = merged_idx * 10000
        merged[merged_idx]["dt"] = 2
        merged[merged_idx]["component_count"] = n_components

        # 直接窗口路径 vs fallback 路径 (70% vs 30%)
        if np.random.random() < 0.7:
            # 直接窗口路径
            merged[merged_idx]["sample_start"] = 10
            merged[merged_idx]["sample_end"] = 20
            merged[merged_idx]["width"] = 10
        else:
            # fallback 路径（跨 record 等情况）
            merged[merged_idx]["sample_start"] = -1
            merged[merged_idx]["sample_end"] = -1
            merged[merged_idx]["width"] = -1

        # 填充对应的原始 hits
        for comp_idx in range(n_components):
            hits[hit_idx]["record_id"] = record_id
            hits[hit_idx]["board"] = 0
            hits[hit_idx]["channel"] = channel
            hits[hit_idx]["position"] = 50 + comp_idx * 5
            hits[hit_idx]["edge_start"] = 48 + comp_idx * 5
            hits[hit_idx]["edge_end"] = 52 + comp_idx * 5
            hits[hit_idx]["width"] = 4
            hits[hit_idx]["timestamp"] = merged_idx * 10000 + comp_idx * 1000
            hits[hit_idx]["dt"] = 2

            component_list.append((merged_idx, hit_idx))
            hit_idx += 1

    components = np.zeros(len(component_list), dtype=HIT_MERGED_COMPONENTS_DTYPE)
    for i, (m_idx, h_idx) in enumerate(component_list):
        components[i]["merged_index"] = m_idx
        components[i]["hit_index"] = h_idx

    # 生成 records 和 wave_pool
    n_records = max(n_merged, 100)
    records = make_records(n_records=n_records, event_length=100, baseline=100.0, dt=2)
    records["polarity"] = "negative"
    records["timestamp"] = np.arange(n_records) * 10000

    # 生成波形池（简单的随机波形）
    wave_pool_size = n_records * 100
    wave_pool = np.random.randint(80, 120, size=wave_pool_size, dtype=np.uint16)

    return merged, components, hits, records, wave_pool


def benchmark_hit_merged_features(merged, components, hits, records, wave_pool, n_runs=5):
    """Benchmark hit_merged_features performance"""
    plugin = HitMergedFeaturesPlugin()

    times = []
    result = None

    for _ in range(n_runs):
        ctx = DummyContext(
            {"wave_source": "records", "use_filtered": False},
            {
                "hit_merged": merged,
                "hit_merged_components": components,
                "hit_threshold": hits,
                "records": records,
                "wave_pool": wave_pool,
            },
        )

        start_time = time.time()
        result = plugin.compute(ctx, "run_001")
        elapsed = time.time() - start_time

        times.append(elapsed)

    return {
        "n_merged": len(merged),
        "n_hits": len(hits),
        "n_features": len(result) if result is not None else 0,
        "time_mean": np.mean(times),
        "time_std": np.std(times),
        "time_min": np.min(times),
    }


def run_benchmark_suite():
    """Run complete benchmark suite"""
    print("=" * 70)
    print("hit_merged_features Performance Benchmark")
    print("=" * 70)

    test_cases = [
        ("Small dataset", 1_000, 16, 2.5),
        ("Medium dataset", 10_000, 16, 2.5),
        ("Large dataset", 100_000, 32, 2.5),
        ("High component count", 10_000, 16, 4.0),
        ("Low component count", 10_000, 16, 1.5),
    ]

    results = []

    for name, n_merged, n_channels, avg_components in test_cases:
        print(f"\n{name}:")
        print(
            f"  Generating: {n_merged:,} merged hits, {n_channels} channels, "
            f"avg {avg_components:.1f} components/merged"
        )

        merged, components, hits, records, wave_pool = generate_test_data(
            n_merged, n_channels, avg_components
        )

        print("  Running benchmark...")
        result = benchmark_hit_merged_features(
            merged, components, hits, records, wave_pool, n_runs=5
        )
        results.append((name, result))

        throughput = result["n_merged"] / result["time_mean"]

        print(f"  - Input: {result['n_merged']:,} merged hits")
        print(f"  - Components: {result['n_hits']:,} original hits")
        print(f"  - Output: {result['n_features']:,} feature rows")
        print(f"  - Time: {result['time_mean']*1000:.2f} +/- {result['time_std']*1000:.2f} ms")
        print(f"  - Throughput: {throughput:,.0f} merged/s")

    print("\n" + "=" * 70)
    print("Benchmark Complete")
    print("=" * 70)

    # Save results to file
    output_file = Path("benchmark_hit_merged_features_baseline.txt")
    with open(output_file, "w") as f:
        f.write("hit_merged_features Performance Benchmark Results\n")
        f.write("=" * 70 + "\n\n")
        for name, result in results:
            f.write(f"{name}:\n")
            f.write(f"  Input: {result['n_merged']:,} merged hits\n")
            f.write(f"  Components: {result['n_hits']:,} original hits\n")
            f.write(f"  Output: {result['n_features']:,} feature rows\n")
            f.write(
                f"  Time: {result['time_mean']*1000:.2f} +/- " f"{result['time_std']*1000:.2f} ms\n"
            )
            f.write(f"  Throughput: {result['n_merged'] / result['time_mean']:,.0f} merged/s\n")
            f.write("\n")

    print(f"\nResults saved to: {output_file}")
    return results


if __name__ == "__main__":
    run_benchmark_suite()
