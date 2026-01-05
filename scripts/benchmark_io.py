#!/usr/bin/env python3
"""Simple I/O benchmark for CSV parsing: compares combinations of chunksize and n_jobs.

Usage:
    python scripts/benchmark_io.py --n-files 50 --n-channels 2 --n-samples 200 --reps 3
"""

import argparse
import shutil
import tempfile
import time
from pathlib import Path

from waveform_analysis import WaveformDataset

# Simple helper (self-contained) to create CSV files similar to tests.utils


def make_simple_csv(dirpath: Path, ch: int, idx: int, tag: int, n_samples: int = 50):
    fname = dirpath / f"RUN_CH{ch}_{idx}.CSV"
    header = "HEADER;X;TIMETAG;" + ";".join(f"S{i}" for i in range(n_samples)) + "\n"
    body = "".join(
        f"v;1;{tag + i};" + ";".join(str((tag + i + j) % 100) for j in range(n_samples)) + "\n" for i in range(2)
    )
    fname.write_text(header + body, encoding="utf-8")


def create_fake_run(tmpdir: Path, n_channels: int, n_files: int, n_samples: int):
    run_dir = tmpdir / "50V_OV_circulation_20thr"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for ch in range(6, 6 + n_channels):
        for i in range(n_files):
            tag = 1000 + i
            make_simple_csv(raw_dir, ch, i, tag, n_samples=n_samples)
    return tmpdir


def bench(n_files: int, n_channels: int, n_samples: int, chunksize_list, n_jobs_list, reps: int):
    tmpdir = Path(tempfile.mkdtemp(prefix="bench_"))
    try:
        create_fake_run(tmpdir, n_channels, n_files, n_samples)
        data_root = tmpdir
        print(f"Created fake run at {tmpdir} ({n_channels} channels x {n_files} files)")

        for chunksize in chunksize_list:
            for n_jobs in n_jobs_list:
                t0 = time.perf_counter()
                # run several reps
                times = []
                for _ in range(reps):
                    ds = WaveformDataset(
                        run_name="50V_OV_circulation_20thr",
                        n_channels=n_channels,
                        start_channel_slice=6,
                        load_waveforms=True,
                        data_root=str(data_root),
                    )
                    ds.load_raw_data()
                    t1 = time.perf_counter()
                    ds.extract_waveforms(chunksize=chunksize, n_jobs=n_jobs)
                    t2 = time.perf_counter()
                    times.append(t2 - t1)
                    # clear to free memory
                    ds.clear_waveforms()
                avg = sum(times) / len(times)
                chk = "None" if chunksize is None else str(chunksize)
                print(f"chunksize={chk:>4} n_jobs={n_jobs:2} -> avg extract time: {avg:.3f}s (reps={reps})")
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-files", type=int, default=20)
    parser.add_argument("--n-channels", type=int, default=2)
    parser.add_argument("--n-samples", type=int, default=200)
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument(
        "--chunksizes",
        nargs="*",
        default=["None", "1000", "500"],
        help="List of chunk sizes. Use 'None' to disable chunking for that run.",
    )
    parser.add_argument("--n-jobs", type=int, nargs="*", default=[1, 2])
    args = parser.parse_args()

    # Normalize chunksizes: 'None' -> None, otherwise int
    chunksizes = [None if s.lower() == "none" else int(s) for s in args.chunksizes]
    bench(args.n_files, args.n_channels, args.n_samples, chunksizes, args.n_jobs, args.reps)
