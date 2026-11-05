#!/usr/bin/env python3
"""Shared helpers for agent quality checks."""

from collections.abc import Iterable
import math
from pathlib import Path
from statistics import median
import tempfile
import time
import tracemalloc

SMOKE_TARGETS = (
    "records",
    "wave_pool",
    "hit_threshold",
    "hit_merged",
    "hit_merged_components",
    "peaklet_components",
    "peaklets",
    "peaklet_waveforms",
    "peaklet_waveform_pool",
    "peaklet_features",
    "peaks",
)


def create_synthetic_vx2730_run(
    data_root: Path,
    run_name: str = "run_smoke_001",
    n_channels: int = 2,
    n_events: int = 12,
    n_samples: int = 128,
) -> Path:
    """Create a small deterministic VX2730-like dataset for smoke/perf checks."""
    raw_dir = data_root / run_name / "RAW"
    raw_dir.mkdir(parents=True, exist_ok=True)

    for ch in range(n_channels):
        csv_path = raw_dir / f"TEST_CH{ch}_0.CSV"
        with csv_path.open("w", encoding="utf-8") as fp:
            # VX2730 reader skips 2 header rows in first file.
            fp.write("HEADER;IGNORE\n")
            fp.write("HEADER;IGNORE\n")

            for event_idx in range(n_events):
                # VX2730 timestamps are ps; channel offsets must share its 2 ns sample grid.
                timestamp = event_idx * 1_000_000 + ch * 2_000
                row = [0, ch, timestamp, event_idx, 0, 0, 0]

                wave = [100] * n_samples
                pulse_start = 30 + (event_idx % 4)
                for j in range(pulse_start, min(pulse_start + 6, n_samples)):
                    wave[j] = 35

                row.extend(wave)
                fp.write(";".join(str(v) for v in row) + "\n")

    return raw_dir


def _build_context(storage_dir: Path, data_root: Path):
    from waveform_analysis.core.context import Context
    from waveform_analysis.core.plugins.builtin.cpu import (
        HitFinderPlugin,
        HitMergedComponentsPlugin,
        HitMergePlugin,
        PeakletComponentsPlugin,
        PeakletFeaturesPlugin,
        PeakletPlugin,
        PeakletWaveformPlugin,
        PeakletWaveformPoolPlugin,
        PeaksPlugin,
        RawFilesPlugin,
        RecordsPlugin,
        ThresholdHitPlugin,
        WaveformsPlugin,
        WavePoolPlugin,
    )

    ctx = Context(
        storage_dir=str(storage_dir),
        config={
            "data_root": str(data_root),
            "daq_adapter": "vx2730",
            "n_channels": 2,
            # Tiny CSV fixture: avoid process-pickling local parser functions.
            # Both benchmark checkouts use this same bounded execution setup.
            "records.channel_workers": 1,
            "records.n_jobs": 1,
            "records.use_process_pool": False,
            "hit.use_filtered": False,
            # Rectangular six-sample pulses have a one-sample derivative edge.
            "hit.use_derivative": False,
            "hit_threshold.wave_source": "records",
            # 性能基准不启用 records asymmetry cut，避免引入 records_asymmetry_mask 依赖
            "hit_threshold.asymmetry_cut_enabled": False,
            "show_progress": False,
        },
        stats_mode="off",
    )
    ctx.register(RawFilesPlugin())
    ctx.register(WaveformsPlugin())
    ctx.register(RecordsPlugin())
    ctx.register(WavePoolPlugin())
    ctx.register(HitFinderPlugin())
    ctx.register(ThresholdHitPlugin())
    ctx.register(HitMergePlugin())
    ctx.register(HitMergedComponentsPlugin())
    ctx.register(PeakletComponentsPlugin())
    ctx.register(PeakletPlugin())
    ctx.register(PeakletWaveformPlugin())
    ctx.register(PeakletWaveformPoolPlugin())
    ctx.register(PeakletFeaturesPlugin())
    ctx.register(PeaksPlugin())
    return ctx


def run_smoke_chain() -> dict[str, object]:
    """Materialize the records-backed hit/peaklet/peaks chain from synthetic raw files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        data_root = tmp_path / "DAQ"
        create_synthetic_vx2730_run(data_root=data_root)

        ctx = _build_context(storage_dir=tmp_path / "storage", data_root=data_root)
        run_id = "run_smoke_001"

        raw_files = ctx.get_data(run_id, "raw_files")
        products = {}
        for target in SMOKE_TARGETS:
            data = ctx.get_data(run_id, target)
            declared_dtype = ctx.get_plugin(target).output_dtype
            if data.dtype != declared_dtype:
                raise ValueError(
                    f"{target} output dtype differs from its declared contract: "
                    f"{data.dtype} != {declared_dtype}"
                )
            products[target] = {
                "count": len(data),
                "dtype": str(data.dtype),
                "fields": {name: str(data.dtype[name]) for name in data.dtype.names or ()},
            }

        return {
            "run_id": run_id,
            "raw_file_groups": len(raw_files),
            "products": products,
        }


def benchmark_hot_targets(targets: Iterable[str], repeats: int = 3) -> dict[str, dict[str, object]]:
    """Benchmark target plugins on deterministic small dataset."""
    targets = list(targets)
    if not targets:
        raise ValueError("no benchmark targets specified")
    if repeats < 1:
        raise ValueError("benchmark repeats must be positive")
    samples: dict[str, list[tuple[float, float]]] = {name: [] for name in targets}

    for _ in range(repeats):
        for target in targets:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                data_root = tmp_path / "DAQ"
                create_synthetic_vx2730_run(data_root=data_root)
                ctx = _build_context(storage_dir=tmp_path / "storage", data_root=data_root)

                run_id = "run_smoke_001"
                tracemalloc.start()
                try:
                    t0 = time.perf_counter()
                    result = ctx.get_data(run_id, target)
                    elapsed = time.perf_counter() - t0
                    _current, peak = tracemalloc.get_traced_memory()
                finally:
                    tracemalloc.stop()

                if len(result) == 0:
                    raise ValueError(f"empty benchmark output for {target} on the pulse fixture")
                if not math.isfinite(elapsed) or elapsed <= 0:
                    raise ValueError(f"invalid benchmark elapsed time for {target}: {elapsed}")
                if not math.isfinite(peak) or peak < 0:
                    raise ValueError(f"invalid benchmark peak memory for {target}: {peak}")

                samples[target].append((elapsed, peak / (1024.0 * 1024.0)))

    out: dict[str, dict[str, object]] = {}
    for target, vals in samples.items():
        times = [x[0] for x in vals]
        mems = [x[1] for x in vals]
        out[target] = {
            "sample_count": len(vals),
            "samples": [{"time_sec": elapsed, "peak_mem_mb": peak} for elapsed, peak in vals],
            "avg_time_sec": sum(times) / float(len(times)),
            "max_time_sec": max(times),
            "avg_peak_mem_mb": sum(mems) / float(len(mems)),
            "max_peak_mem_mb": max(mems),
            "median_time_sec": median(times),
            "median_peak_mem_mb": median(mems),
        }
    return out
