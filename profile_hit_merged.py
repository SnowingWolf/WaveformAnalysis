#!/usr/bin/env python
"""
Profiling script for hit_merged to identify bottlenecks
"""

import cProfile
import io
import pstats

import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.cpu.hit_merge import HitMergePlugin


def generate_test_hits(n_hits=10000, n_channels=16):
    """Generate test hits"""
    hits = np.zeros(n_hits, dtype=THRESHOLD_HIT_DTYPE)
    hits["channel"] = np.random.randint(0, n_channels, n_hits)
    hits["board"] = 0

    for ch in range(n_channels):
        mask = hits["channel"] == ch
        n_ch = np.sum(mask)
        if n_ch == 0:
            continue

        timestamps = [0]
        for _ in range(n_ch - 1):
            if np.random.random() < 0.3:
                timestamps.append(timestamps[-1] + np.random.randint(10, 50) * 1000)
            else:
                timestamps.append(timestamps[-1] + np.random.randint(200, 1000) * 1000)

        hits["timestamp"][mask] = np.array(timestamps, dtype=np.int64)
        hits["position"][mask] = np.arange(n_ch, dtype=np.int64) * 10
        hits["edge_start"][mask] = hits["position"][mask] - 2
        hits["edge_end"][mask] = hits["position"][mask] + 2
        hits["width"][mask] = 4.0
        hits["dt"][mask] = 2
        hits["record_id"][mask] = np.arange(n_ch, dtype=np.int64)

    return hits


def profile_hit_merge():
    """Profile hit_merge performance"""
    print("Generating test data...")
    hits = generate_test_hits(n_hits=10000, n_channels=16)

    plugin = HitMergePlugin()
    config = {
        "merge_gap_ns": 50.0,
        "max_total_width_ns": 10000.0,
        "dt": 2,
        "chunk_parallel": False,  # Disable parallel for clearer profiling
        "use_numba": False,  # Disable Numba to see Python bottlenecks
    }
    ctx = DummyContext(config, {"hit_threshold": hits})

    print("Running profiler...")
    profiler = cProfile.Profile()
    profiler.enable()

    # Run multiple times for better statistics
    result = None
    for _ in range(10):
        result = plugin.compute(ctx, "run_001")

    profiler.disable()

    # Print results
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.strip_dirs()
    ps.sort_stats("cumulative")
    ps.print_stats(30)

    print("\n" + "=" * 70)
    print("PROFILING RESULTS (Top 30 by cumulative time)")
    print("=" * 70)
    print(s.getvalue())

    # Save to file
    with open("profile_hit_merged.txt", "w") as f:
        f.write(s.getvalue())

    print("\nProfile saved to: profile_hit_merged.txt")
    if result is not None:
        print(f"Result: {len(result)} merged hits from {len(hits)} input hits")


if __name__ == "__main__":
    profile_hit_merge()
