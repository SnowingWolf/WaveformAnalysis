#!/usr/bin/env python3
"""Bounded real V1725 workload probe; never discovers or runs a whole run.

Example: python scripts/benchmark_system_workload.py --raw-file FILE --output-dir NEW_DIR
FILE is a V1725 binary at <data_root>/<run_id>/RAW/*bN*.bin.
All writes, including JIT and product caches, stay under the new output directory.
The watchdog covers worker imports, JIT, recomputations and cache reads together.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import platform
import signal
import statistics
import subprocess
import sys
import time
import weakref

MAX_INPUT_BYTES = 64 * 1024**2
MAX_RSS_BYTES = 1024**3
MAX_WORKER_SECONDS = 60.0
THREAD_VARIABLES = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMBA_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
)


def input_metadata(path: Path) -> dict:
    if path.parent.name != "RAW" or path.suffix != ".bin":
        raise ValueError("V1725 input must have the path <data_root>/<run_id>/RAW/*.bin")
    stat = path.stat()
    if not path.is_file() or stat.st_size <= 0 or stat.st_size > MAX_INPUT_BYTES:
        raise ValueError(f"input must be a nonempty file of at most {MAX_INPUT_BYTES} bytes")
    return {"path": str(path.resolve()), "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def assert_exact_payload(actual, expected) -> None:
    """Compare every bounded output field, including ordering and NaN positions."""
    import numpy as np

    if actual.dtype != expected.dtype or actual.shape != expected.shape:
        raise AssertionError("output dtype or shape changed")
    fields = actual.dtype.names or (None,)
    for field in fields:
        left, right = (actual[field], expected[field]) if field else (actual, expected)
        if not np.array_equal(left, right, equal_nan=left.dtype.kind in "fc"):
            raise AssertionError(f"output values or ordering changed: {field}")


def _proc_io() -> dict:
    return {
        key: int(value)
        for line in Path("/proc/self/io").read_text().splitlines()
        for key, value in [line.split(":", 1)]
        if key in {"rchar", "read_bytes", "wchar", "write_bytes"}
    }


def _new_context(storage_dir: Path, raw_file: Path, args: argparse.Namespace):
    from waveform_analysis import Context
    from waveform_analysis.plugins import plugins_hit, plugins_io, plugins_peaks, plugins_waveform

    config = {
        "data_root": str(raw_file.parents[2]),
        "daq_adapter": "v1725",
        "show_progress": False,
        "enable_plugin_parallelism": False,
        "records": {
            "n_jobs": 1,
            "channel_workers": 1,
            "channel_executor": "thread",
            "keep_on_disk": True,
            "memory_budget_gb": 0.25,
            "v1725_part_size": 10_000,
        },
        "hit_threshold": {
            "wave_source": args.wave_source,
            "asymmetry_cut_enabled": not args.disable_asymmetry,
            "n_workers": args.threads,
            "chunk_parallel": False,
        },
        "st_waveforms": {"use_upstream_baseline": False},
        "peaklet_waveforms": {"n_workers": 1},
    }
    context = Context(storage_dir=str(storage_dir), config=config, stats_mode="off")
    context.register(*plugins_io(), *plugins_waveform(), *plugins_hit(), *plugins_peaks())
    context._set_data(raw_file.parents[1].name, "raw_files", [[str(raw_file)]])
    return context


def _resident_arrays(context, run_id: str) -> dict:
    import numpy as np

    arrays = {
        name: value
        for (rid, name), value in context._results.items()
        if rid == run_id and isinstance(value, np.ndarray)
    }
    return {
        "arrays": {
            name: {
                "shape": list(value.shape),
                "logical_bytes": value.nbytes,
                "memmap": isinstance(value, np.memmap),
            }
            for name, value in arrays.items()
        },
        "logical_array_bytes_including_aliases": sum(value.nbytes for value in arrays.values()),
        "note": "Logical array sizes include shared mappings; they are not resident RSS.",
    }


def _run_worker(args: argparse.Namespace) -> dict:
    import numba
    import numpy as np
    import psutil
    from threadpoolctl import threadpool_info

    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo))
    raw_file = args.raw_file.resolve()
    run_id = raw_file.parents[1].name
    targets = ["records", "wave_pool"]
    if args.target != "records":
        targets.append(args.target)
    before = input_metadata(raw_file)
    expected = None
    samples = []
    first_cache = args.output_dir / "compute-0"
    for repeat in range(args.repeats + 1):
        context = _new_context(args.output_dir / f"compute-{repeat}", raw_file, args)
        workload_config = context.config.copy()
        io_before = _proc_io()
        started = time.perf_counter()
        cpu_started = time.process_time()
        outputs = {name: context.get_data(run_id, name) for name in targets}
        elapsed = time.perf_counter() - started
        cpu_elapsed = time.process_time() - cpu_started
        io_after = _proc_io()
        if expected is None:
            expected = {name: value.copy() for name, value in outputs.items()}
        for name in targets:
            assert_exact_payload(outputs[name], expected[name])
        records = outputs["records"]
        keys = np.rec.fromarrays(
            [records[name] for name in ("timestamp", "pid", "board", "channel")]
        )
        if not np.array_equal(np.argsort(keys, kind="stable"), np.arange(len(keys))):
            raise AssertionError("records are not sorted by the canonical key")
        if int(records["event_length"].sum()) != len(outputs["wave_pool"]):
            raise AssertionError("wave pool and record lengths disagree")
        samples.append(
            {
                "state": (
                    "first_call_empty_jit_cache" if repeat == 0 else "warm_jit_fresh_product_cache"
                ),
                "wall_seconds": elapsed,
                "cpu_seconds": cpu_elapsed,
                "io_delta": {key: io_after[key] - value for key, value in io_before.items()},
                "rss_after_bytes": psutil.Process().memory_info().rss,
                "os_threads_after": psutil.Process().num_threads(),
                "resident_arrays": _resident_arrays(context, run_id),
                "phases": {key: float(value) for key, value in context.profiler.durations.items()},
                "exact_to_first_call": True,
            }
        )
        del records, keys, outputs, context
        gc.collect()

    cache_samples = []
    context = None
    for repeat in range(args.repeats):
        context = _new_context(first_cache, raw_file, args)
        if not all(context._is_cache_hit(run_id, name, load=False) for name in targets):
            raise AssertionError("expected task-local product cache is missing")
        io_before = _proc_io()
        started = time.perf_counter()
        outputs = {name: context.get_data(run_id, name) for name in targets}
        map_elapsed = time.perf_counter() - started
        started = time.perf_counter()
        for name in targets:
            assert_exact_payload(outputs[name], expected[name])
        touch_elapsed = time.perf_counter() - started
        io_after = _proc_io()
        cache_samples.append(
            {
                "map_wall_seconds": map_elapsed,
                "touch_and_exact_compare_seconds": touch_elapsed,
                "io_delta": {key: io_after[key] - value for key, value in io_before.items()},
                "rss_after_bytes": psutil.Process().memory_info().rss,
                "exact_to_first_call": True,
                "plugin_compute_calls": sum(
                    count
                    for key, count in context.profiler.counts.items()
                    if key.startswith("plugin.") and key.endswith(".compute")
                ),
            }
        )
        if repeat != args.repeats - 1:
            del outputs, context
            gc.collect()

    refs = {name: weakref.ref(value) for name, value in outputs.items()}
    del outputs
    context.clear_cache_for(run_id, clear_disk=False, verbose=False)
    gc.collect()
    cleanup = {
        "public_arrays_still_alive": [name for name, ref in refs.items() if ref() is not None],
        "public_result_keys_remaining": [
            name for rid, name in context._results if rid == run_id and name in targets
        ],
        "note": "Weak references observe Python object retention; allocator RSS may remain high after release.",
    }
    after = input_metadata(raw_file)
    if before != after:
        raise AssertionError("source size or mtime changed during the probe")
    return {
        "schema_version": 1,
        "input_before": before,
        "input_after": after,
        "run_id": run_id,
        "target": args.target,
        "workload_config": workload_config,
        "runtime": {
            "python": sys.executable,
            "version": platform.python_version(),
            "numpy": np.__version__,
            "numba": numba.__version__,
            "numba_threads": numba.get_num_threads(),
            "thread_env": {key: os.environ[key] for key in THREAD_VARIABLES},
            "affinity_cpu_count": len(os.sched_getaffinity(0)),
            "native_threadpools": threadpool_info(),
            "os_thread_names": [
                (task / "comm").read_text().strip() for task in Path("/proc/self/task").iterdir()
            ],
        },
        "output": {
            name: {
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "logical_bytes": value.nbytes,
            }
            for name, value in expected.items()
        },
        "compute_samples": samples,
        "cache_samples": cache_samples,
        "warm_wall_median_seconds": statistics.median(
            sample["wall_seconds"] for sample in samples[1:]
        ),
        "cache_map_wall_median_seconds": statistics.median(
            sample["map_wall_seconds"] for sample in cache_samples
        ),
        "cleanup": cleanup,
        "limits": {
            "worker_seconds": MAX_WORKER_SECONDS,
            "worker_process_tree_rss_bytes": MAX_RSS_BYTES,
            "input_bytes": MAX_INPUT_BYTES,
        },
        "caveats": [
            "First call includes JIT but no OS/NAS page-cache flush; this is not cold physical I/O.",
            "Recomputation includes source reads and task-local product writes; it is not compute-only timing.",
            "One b1 file does not exercise file fan-out or establish representative b0 peak physics.",
            "Process-tree RSS is sampled; brief peaks between samples may be missed.",
        ],
    }


def _watch_worker(command: list[str], output_dir: Path, env: dict) -> dict:
    import psutil

    started = time.monotonic()
    peak_rss = 0
    peak_threads = 0
    with (output_dir / "worker.log").open("w") as log:
        child = subprocess.Popen(
            command, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True
        )
        process = psutil.Process(child.pid)
        exceeded = None
        try:
            while child.poll() is None:
                rss = threads = 0
                try:
                    processes = [process, *process.children(recursive=True)]
                    for item in processes:
                        try:
                            rss += item.memory_info().rss
                            threads += item.num_threads()
                        except psutil.NoSuchProcess:
                            pass
                except psutil.NoSuchProcess:
                    pass
                peak_rss = max(peak_rss, rss)
                peak_threads = max(peak_threads, threads)
                if rss > MAX_RSS_BYTES:
                    exceeded = "process_tree_rss"
                elif time.monotonic() - started > MAX_WORKER_SECONDS:
                    exceeded = "worker_wall_time"
                if exceeded:
                    break
                time.sleep(0.02)
        finally:
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            returncode = child.wait()
    return {
        "returncode": returncode,
        "limit_exceeded": exceeded,
        "peak_sampled_process_tree_rss_bytes": peak_rss,
        "peak_sampled_process_tree_threads": peak_threads,
        "wall_seconds_including_imports": time.monotonic() - started,
        "sample_interval_seconds": 0.02,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-file",
        type=Path,
        required=True,
        help="completed V1725 binary at <data_root>/<run_id>/RAW/*.bin",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--target", choices=("records", "hit_threshold", "peaks"), default="records"
    )
    parser.add_argument("--threads", type=int, choices=(1, 2), default=1)
    parser.add_argument("--repeats", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--wave-source", choices=("records", "st_waveforms"), default="records")
    parser.add_argument("--disable-asymmetry", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        payload = _run_worker(args)
        (args.output_dir / "report.json").write_text(json.dumps(payload, indent=2))
        return 0
    input_metadata(args.raw_file)
    args.output_dir = args.output_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    repo = Path(__file__).resolve().parents[1]
    (args.output_dir / "benchmark_source.py").write_text(Path(__file__).read_text())
    for arguments, filename in (
        (["rev-parse", "HEAD"], "git-head.txt"),
        (["diff", "--", "waveform_analysis"], "source-working-tree.patch"),
    ):
        completed = subprocess.run(
            ["git", "-C", str(repo), *arguments], check=True, capture_output=True, text=True
        )
        (args.output_dir / filename).write_text(completed.stdout)
    for name in ("tmp", "numba", "mplconfig"):
        (args.output_dir / name).mkdir()
    env = dict(os.environ)
    env.update({key: str(args.threads) for key in THREAD_VARIABLES})
    env.update(
        {
            "TMPDIR": str(args.output_dir / "tmp"),
            "NUMBA_CACHE_DIR": str(args.output_dir / "numba"),
            "MPLCONFIGDIR": str(args.output_dir / "mplconfig"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--raw-file",
        str(args.raw_file.resolve()),
        "--output-dir",
        str(args.output_dir),
        "--target",
        args.target,
        "--threads",
        str(args.threads),
        "--repeats",
        str(args.repeats),
        "--wave-source",
        args.wave_source,
        "--worker",
    ]
    if args.disable_asymmetry:
        command.append("--disable-asymmetry")
    watchdog = _watch_worker(command, args.output_dir, env)
    (args.output_dir / "watchdog.json").write_text(json.dumps(watchdog, indent=2))
    print(json.dumps({"output_dir": str(args.output_dir), **watchdog}))
    return 0 if watchdog["returncode"] == 0 and watchdog["limit_exceeded"] is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
