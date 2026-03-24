#!/usr/bin/env python3
"""Shared helpers for agent quality checks."""

from collections.abc import Iterable
from pathlib import Path
import tempfile
import time
import tracemalloc


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
                timestamp = event_idx * 1_000_000 + ch * 100
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
        BasicFeaturesPlugin,
        DataFramePlugin,
        GroupedEventsPlugin,
        HitFinderPlugin,
        RawFilesPlugin,
        WaveformsPlugin,
    )

    ctx = Context(
        storage_dir=str(storage_dir),
        config={
            "data_root": str(data_root),
            "daq_adapter": "vx2730",
            "n_channels": 2,
            "hit.use_filtered": False,
            "basic_features.use_filtered": False,
            "show_progress": False,
        },
        stats_mode="detailed",
    )
    ctx.register(RawFilesPlugin())
    ctx.register(WaveformsPlugin())
    ctx.register(HitFinderPlugin())
    ctx.register(BasicFeaturesPlugin())
    ctx.register(DataFramePlugin())
    ctx.register(GroupedEventsPlugin())
    return ctx


def run_smoke_chain() -> dict[str, object]:
    """Run fixed smoke chain: raw_files -> st_waveforms -> hit -> df -> df_events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        data_root = tmp_path / "DAQ"
        create_synthetic_vx2730_run(data_root=data_root)

        ctx = _build_context(storage_dir=tmp_path / "storage", data_root=data_root)
        run_id = "run_smoke_001"

        raw_files = ctx.get_data(run_id, "raw_files")
        st_waveforms = ctx.get_data(run_id, "st_waveforms")
        hit = ctx.get_data(run_id, "hit")
        df = ctx.get_data(run_id, "df")
        events = ctx.get_data(run_id, "df_events")

        events_columns = getattr(events, "columns", None)

        return {
            "run_id": run_id,
            "raw_file_groups": len(raw_files) if raw_files is not None else 0,
            "st_waveforms_count": len(st_waveforms) if st_waveforms is not None else 0,
            "hit_count": len(hit) if hit is not None else 0,
            "df_rows": len(df) if df is not None else 0,
            "events_count": len(events) if events is not None else 0,
            "st_waveforms_fields": list(getattr(st_waveforms.dtype, "names", ()) or ()),
            "events_fields": list(events_columns) if events_columns is not None else [],
        }


def benchmark_hot_targets(targets: Iterable[str], repeats: int = 3) -> dict[str, dict[str, float]]:
    """Benchmark target plugins on deterministic small dataset."""
    targets = list(targets)
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
                t0 = time.perf_counter()
                _ = ctx.get_data(run_id, target)
                elapsed = time.perf_counter() - t0
                _current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()

                samples[target].append((elapsed, peak / (1024.0 * 1024.0)))

    out: dict[str, dict[str, float]] = {}
    for target, vals in samples.items():
        if not vals:
            out[target] = {
                "avg_time_sec": 0.0,
                "max_time_sec": 0.0,
                "avg_peak_mem_mb": 0.0,
                "max_peak_mem_mb": 0.0,
            }
            continue

        times = [x[0] for x in vals]
        mems = [x[1] for x in vals]
        out[target] = {
            "avg_time_sec": sum(times) / float(len(times)),
            "max_time_sec": max(times),
            "avg_peak_mem_mb": sum(mems) / float(len(mems)),
            "max_peak_mem_mb": max(mems),
        }
    return out
