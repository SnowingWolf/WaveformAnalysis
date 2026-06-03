#!/usr/bin/env python
"""
hit_merged performance benchmark script

Measures performance differences before and after optimization
"""

import os
from pathlib import Path
import time

import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import HitMergePlugin


def generate_test_hits(n_hits=10000, n_channels=16, merge_rate=0.3):
    """生成测试用的 hit 数据

    Args:
        n_hits: 总 hit 数量
        n_channels: 通道数
        merge_rate: 期望的合并率（相邻 hit 可合并的比例）
    """
    hits = np.zeros(n_hits, dtype=THRESHOLD_HIT_DTYPE)

    # 随机分配通道
    hits["channel"] = np.random.randint(0, n_channels, n_hits)
    hits["board"] = 0

    # 生成时间戳（按通道排序，便于合并）
    for ch in range(n_channels):
        mask = hits["channel"] == ch
        n_ch = np.sum(mask)
        if n_ch == 0:
            continue

        # 生成时间戳，部分间隔小（可合并），部分间隔大（不可合并）
        timestamps = [0]
        for _ in range(n_ch - 1):
            if np.random.random() < merge_rate:
                # 小间隔，可合并
                timestamps.append(timestamps[-1] + np.random.randint(10, 50) * 1000)
            else:
                # 大间隔，不可合并
                timestamps.append(timestamps[-1] + np.random.randint(200, 1000) * 1000)

        hits["timestamp"][mask] = np.array(timestamps, dtype=np.int64)
        hits["position"][mask] = np.arange(n_ch, dtype=np.int64) * 10
        hits["edge_start"][mask] = hits["position"][mask] - 2
        hits["edge_end"][mask] = hits["position"][mask] + 2
        hits["width"][mask] = 4.0
        hits["dt"][mask] = 2
        hits["record_id"][mask] = np.arange(n_ch, dtype=np.int64)

    return hits


def benchmark_hit_merge(hits, config, n_runs=5):
    """Benchmark hit_merge performance"""
    plugin = HitMergePlugin()

    times = []

    result = None
    for _ in range(n_runs):
        ctx = DummyContext(config, {"hit_threshold": hits})

        start_time = time.time()
        result = plugin.compute(ctx, "run_001")
        elapsed = time.time() - start_time

        times.append(elapsed)

    return {
        "n_input": len(hits),
        "n_output": len(result) if result is not None else 0,
        "time_mean": np.mean(times),
        "time_std": np.std(times),
        "time_min": np.min(times),
    }


def run_benchmark_suite():
    """Run complete benchmark suite"""
    print("=" * 70)
    print("hit_merged Performance Benchmark")
    print("=" * 70)

    config = {
        "merge_gap_ns": 50.0,
        "max_total_width_ns": 10000.0,
        "dt": 2,
    }

    test_cases = [
        ("Small dataset", 1_000, 4, 0.3),
        ("Medium dataset", 10_000, 16, 0.3),
        ("Large dataset", 100_000, 32, 0.3),
        ("High merge rate", 10_000, 16, 0.6),
        ("Low merge rate", 10_000, 16, 0.1),
    ]

    results = []

    for name, n_hits, n_channels, merge_rate in test_cases:
        print(f"\n{name}:")
        print(f"  Generating: {n_hits:,} hits, {n_channels} channels, merge rate {merge_rate:.0%}")

        hits = generate_test_hits(n_hits, n_channels, merge_rate)

        print("  Running benchmark...")
        result = benchmark_hit_merge(hits, config, n_runs=5)
        results.append((name, result))

        compression_ratio = result["n_input"] / max(result["n_output"], 1)
        throughput = result["n_input"] / result["time_mean"]

        print(f"  - Input: {result['n_input']:,} hits")
        print(f"  - Output: {result['n_output']:,} merged hits")
        print(f"  - Compression: {compression_ratio:.2f}x")
        print(f"  - Time: {result['time_mean']*1000:.2f} +/- {result['time_std']*1000:.2f} ms")
        print(f"  - Throughput: {throughput:,.0f} hits/s")

    print("\n" + "=" * 70)
    print("Benchmark Complete")
    print("=" * 70)

    # Save results to file
    output_file = Path("benchmark_hit_merged_baseline.txt")
    with open(output_file, "w") as f:
        f.write("hit_merged Performance Benchmark Results\n")
        f.write("=" * 70 + "\n\n")
        for name, result in results:
            f.write(f"{name}:\n")
            f.write(f"  Input: {result['n_input']:,} hits\n")
            f.write(f"  Output: {result['n_output']:,} merged hits\n")
            f.write(
                f"  Time: {result['time_mean']*1000:.2f} +/- {result['time_std']*1000:.2f} ms\n"
            )
            f.write(f"  Throughput: {result['n_input'] / result['time_mean']:,.0f} hits/s\n")
            f.write("\n")

    print(f"\nResults saved to: {output_file}")
    return results


if __name__ == "__main__":
    run_benchmark_suite()
