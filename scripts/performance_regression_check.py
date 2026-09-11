#!/usr/bin/env python3
"""Compare hotspot plugin performance before/after changes."""

import argparse
import json
import os
from pathlib import Path
import shutil
from statistics import median
import subprocess
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPEATS = 5


BENCH_SNIPPET = r"""
import json
import os
import tempfile
import time
import tracemalloc
from pathlib import Path
from statistics import median


# The old 12 x 128 input mostly measured Context, temporary-directory, and
# CSV-file setup.  This workload keeps the same two-channel VX2730 shape while
# giving waveform and hit plugins enough rows to dominate that fixed cost.
# It is intentionally below the scale that would make the release gate depend
# on a long-running data-processing job: 2 * 1200 * 512 = 1,228,800 samples.
SYNTHETIC_N_CHANNELS = 2
SYNTHETIC_N_EVENTS = 1200
SYNTHETIC_N_SAMPLES = 512


def create_synthetic_vx2730_run(
    data_root,
    run_name="run_smoke_001",
    n_channels=SYNTHETIC_N_CHANNELS,
    n_events=SYNTHETIC_N_EVENTS,
    n_samples=SYNTHETIC_N_SAMPLES,
):
    raw_dir = Path(data_root) / run_name / "RAW"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for ch in range(n_channels):
        csv_path = raw_dir / "TEST_CH{}_0.CSV".format(ch)
        with csv_path.open("w", encoding="utf-8") as fp:
            fp.write("HEADER;IGNORE\n")
            fp.write("HEADER;IGNORE\n")
            for event_idx in range(n_events):
                timestamp = event_idx * 1000000 + ch * 100
                row = [0, ch, timestamp, event_idx, 0, 0, 0]
                wave = [100] * n_samples
                pulse_start = 30 + (event_idx % 4)
                for j in range(pulse_start, min(pulse_start + 6, n_samples)):
                    wave[j] = 35
                row.extend(wave)
                fp.write(";".join(str(v) for v in row) + "\n")


def build_context(storage_dir, data_root):
    from waveform_analysis.core.context import Context
    from waveform_analysis.core.plugins.builtin.cpu import (
        BasicFeaturesPlugin,
        DataFramePlugin,
        GroupedEventsPlugin,
        HitFinderPlugin,
        RawFilesPlugin,
        RecordsPlugin,
        ThresholdHitPlugin,
        WavePoolPlugin,
        WaveformsPlugin,
    )

    ctx = Context(
        storage_dir=str(storage_dir),
        config={
            "data_root": str(data_root),
            "daq_adapter": "vx2730",
            "n_channels": 2,
            # Keep records construction identical and serial on v1.5.0 and
            # current.  The old process-pool path cannot pickle its local CSV
            # parser function and can otherwise return an empty bundle.
            "records.channel_workers": 1,
            "records.channel_executor": "thread",
            "records.n_jobs": 1,
            "records.use_process_pool": False,
            "records.input_source": "raw_files",
            "records.keep_on_disk": False,
            # Use the records-backed paths explicitly and keep hit finding
            # deterministic for the small benchmark input.
            "hit.wave_source": "records",
            "hit.use_filtered": False,
            "hit.use_derivative": True,
            "hit.height": 10.0,
            "hit.width": 1,
            "hit.prominence": 0.7,
            "hit.parallel": False,
            "hit.n_workers": 1,
            "hit_threshold.wave_source": "records",
            "hit_threshold.chunk_parallel": False,
            "hit_threshold.n_workers": 1,
            "hit_threshold.parallel_chunk_size": 12,
            "hit_threshold.parallel_min_records": 50_000,
            # 性能基准不启用 records asymmetry/channel cuts，避免引入
            # optional mask dependencies.
            "hit_threshold.asymmetry_cut_enabled": False,
            "hit_threshold.channel_role_cut_enabled": False,
            "basic_features.use_filtered": False,
            "enable_plugin_parallelism": False,
            "max_parallel_workers": 1,
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
    ctx.register(BasicFeaturesPlugin())
    ctx.register(DataFramePlugin())
    ctx.register(GroupedEventsPlugin())
    return ctx


TARGET_CONTRACTS = {
    "st_waveforms": {
        "fields": ("record_id", "board", "channel", "dt", "event_length", "wave"),
        "min_rows": 1,
    },
    "records": {
        "fields": (
            "record_id",
            "board",
            "channel",
            "dt",
            "wave_offset",
            "event_length",
        ),
        "min_rows": 1,
    },
    "hit": {
        "fields": ("position", "height", "integral", "timestamp", "record_id"),
        "min_rows": 1,
    },
    "hit_threshold": {
        "fields": ("position", "edge_start", "edge_end", "timestamp", "record_id"),
        "min_rows": 1,
    },
    "df": {"columns": ("record_id", "timestamp"), "min_rows": 1},
    "df_events": {"columns": ("event_id", "n_hits"), "min_rows": 1},
    "wave_pool": {"one_dimensional": True, "min_rows": 1},
}


def validate_target_output(target, value):
    contract = TARGET_CONTRACTS.get(target, {"min_rows": 1})
    if value is None:
        raise RuntimeError("target {!r} returned None; benchmark output is invalid".format(target))

    try:
        n_rows = len(value)
    except TypeError as exc:
        raise RuntimeError(
            "target {!r} returned a value without a row count; benchmark output is invalid".format(
                target
            )
        ) from exc

    min_rows = int(contract.get("min_rows", 1))
    if n_rows < min_rows:
        detail = "empty output is not a valid benchmark" if target == "hit_threshold" else "output is too short"
        raise RuntimeError(
            "target {!r} returned {} rows (minimum {}): {}".format(
                target, n_rows, min_rows, detail
            )
        )

    required_fields = tuple(contract.get("fields", ()))
    if required_fields:
        dtype = getattr(value, "dtype", None)
        names = tuple(getattr(dtype, "names", ()) or ())
        missing = [name for name in required_fields if name not in names]
        if missing:
            raise RuntimeError(
                "target {!r} is missing required fields {}; got {}".format(
                    target, missing, names
                )
            )

    required_columns = tuple(contract.get("columns", ()))
    if required_columns:
        columns_attr = getattr(value, "columns", None)
        columns = tuple(columns_attr) if columns_attr is not None else ()
        missing = [name for name in required_columns if name not in columns]
        if missing:
            raise RuntimeError(
                "target {!r} is missing required columns {}; got {}".format(
                    target, missing, columns
                )
            )

    if contract.get("one_dimensional") and getattr(value, "ndim", None) != 1:
        raise RuntimeError(
            "target {!r} must be a one-dimensional wave_pool; got ndim={!r}".format(
                target, getattr(value, "ndim", None)
            )
        )

    if target == "raw_files" and not all(group for group in value):
        raise RuntimeError("target 'raw_files' contains an empty channel group")


def summarize_target_output(value):
    summary = {"rows": int(len(value))}
    shape = getattr(value, "shape", None)
    if shape is not None:
        summary["shape"] = [int(dimension) for dimension in shape]

    dtype = getattr(value, "dtype", None)
    names = tuple(getattr(dtype, "names", ()) or ())
    if names:
        summary["fields"] = list(names)

    columns_attr = getattr(value, "columns", None)
    if columns_attr is not None:
        summary["columns"] = [str(column) for column in columns_attr]

    ndim = getattr(value, "ndim", None)
    if ndim is not None:
        summary["ndim"] = int(ndim)
    return summary


def _make_context(tmp_path):
    data_root = tmp_path / "DAQ"
    create_synthetic_vx2730_run(data_root=data_root)
    return build_context(storage_dir=tmp_path / "storage", data_root=data_root)


def _warm_up(targets):
    # Warm up imports and deterministic Numba/scipy paths once.  Every timed
    # sample below still creates a fresh dataset and Context, so warm-up never
    # measures a cache hit.
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_context(Path(tmpdir))
        for target in targets:
            validate_target_output(target, ctx.get_data("run_smoke_001", target))


def _run_pass(targets, repeats, measure_memory):
    samples = {name: {"time": [], "memory": []} for name in targets}
    output_summaries = {}
    for _ in range(repeats):
        for target in targets:
            with tempfile.TemporaryDirectory() as tmpdir:
                ctx = _make_context(Path(tmpdir))
                run_id = "run_smoke_001"

                if measure_memory:
                    tracemalloc.start()
                    try:
                        value = ctx.get_data(run_id, target)
                        _current, peak = tracemalloc.get_traced_memory()
                    finally:
                        tracemalloc.stop()
                    validate_target_output(target, value)
                    samples[target]["memory"].append(peak / (1024.0 * 1024.0))
                else:
                    t0 = time.perf_counter()
                    value = ctx.get_data(run_id, target)
                    elapsed = time.perf_counter() - t0
                    validate_target_output(target, value)
                    samples[target]["time"].append(elapsed)

                summary = summarize_target_output(value)
                previous_summary = output_summaries.setdefault(target, summary)
                if summary != previous_summary:
                    raise RuntimeError(
                        "target {!r} changed output size across repeats: {} != {}".format(
                            target, previous_summary, summary
                        )
                    )

    out = {}
    for target in targets:
        times = samples[target]["time"]
        mems = samples[target]["memory"]
        out[target] = {
            "avg_time_sec": sum(times) / float(len(times)) if times else 0.0,
            "max_time_sec": max(times) if times else 0.0,
            "avg_peak_mem_mb": sum(mems) / float(len(mems)) if mems else 0.0,
            "max_peak_mem_mb": max(mems) if mems else 0.0,
            "median_time_sec": median(times) if times else 0.0,
            "median_peak_mem_mb": median(mems) if mems else 0.0,
            "output": output_summaries[target],
            "input": {
                "n_channels": SYNTHETIC_N_CHANNELS,
                "n_events": SYNTHETIC_N_EVENTS,
                "n_samples": SYNTHETIC_N_SAMPLES,
                "total_samples": (
                    SYNTHETIC_N_CHANNELS * SYNTHETIC_N_EVENTS * SYNTHETIC_N_SAMPLES
                ),
            },
        }
    return out


def benchmark_hot_targets(targets, repeats=5):
    targets = list(dict.fromkeys(targets))
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    _warm_up(targets)
    timed = _run_pass(targets, repeats, measure_memory=False)
    memory = _run_pass(targets, repeats, measure_memory=True)
    for target in targets:
        if timed[target]["output"] != memory[target]["output"]:
            raise RuntimeError(
                "target {!r} changed output size between timed and memory passes: {} != {}".format(
                    target, timed[target]["output"], memory[target]["output"]
                )
            )
        timed[target]["avg_peak_mem_mb"] = memory[target]["avg_peak_mem_mb"]
        timed[target]["max_peak_mem_mb"] = memory[target]["max_peak_mem_mb"]
        timed[target]["median_peak_mem_mb"] = memory[target]["median_peak_mem_mb"]
    return timed


def main():
    targets = json.loads(os.environ["QUALITY_TARGETS_JSON"])
    repeats = int(os.environ.get("QUALITY_REPEATS", "5"))
    report = benchmark_hot_targets(targets=targets, repeats=repeats)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
"""


def _run_subprocess_json(cmd: list[str], cwd: Path, env: dict[str, str]) -> dict[str, object]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "command failed: {}\n{}\n{}".format(" ".join(cmd), proc.stdout, proc.stderr)
        )
    text = proc.stdout.strip()
    # Keep last line only in case the environment prints warnings.
    line = text.splitlines()[-1] if text else "{}"
    payload = json.loads(line)
    if not isinstance(payload, dict):
        raise RuntimeError(f"benchmark command returned non-object JSON: {type(payload).__name__}")
    return payload


def _benchmark_env(targets: list[str], repeats: int) -> dict[str, str]:
    env = dict(os.environ)
    env["QUALITY_TARGETS_JSON"] = json.dumps(targets)
    env["QUALITY_REPEATS"] = str(repeats)
    # Hash iteration order and hidden threaded math settings must be the same
    # for the detached baseline and the current worktree.
    env["PYTHONHASHSEED"] = "0"
    env["OMP_NUM_THREADS"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    return env


def _run_benchmark(cwd: Path, targets: list[str], repeats: int) -> dict[str, object]:
    return _run_subprocess_json(
        cmd=[sys.executable, "-c", BENCH_SNIPPET],
        cwd=cwd,
        env=_benchmark_env(targets, repeats),
    )


def _run_current(targets: list[str], repeats: int) -> dict[str, dict[str, float]]:
    return _run_benchmark(PROJECT_ROOT, targets=targets, repeats=repeats)


def _resolve_base_sha(base: str) -> str:
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", f"{base}^{{commit}}"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if resolved.returncode != 0:
        detail = resolved.stderr.strip() or resolved.stdout.strip()
        raise RuntimeError(f"failed to resolve performance baseline {base!r}: {detail}")
    base_sha = resolved.stdout.strip()
    if len(base_sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in base_sha):
        raise RuntimeError(
            f"performance baseline {base!r} did not resolve to a full commit SHA: {base_sha!r}"
        )
    return base_sha.lower()


def _run_base(
    base: str, targets: list[str], repeats: int
) -> tuple[dict[str, dict[str, float]], str]:
    base_sha = _resolve_base_sha(base)
    tmpdir = tempfile.mkdtemp(prefix="wa-perf-base-")
    worktree_path = Path(tmpdir) / "worktree"
    worktree_added = False

    try:
        add = subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree_path), base_sha],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if add.returncode != 0:
            detail = add.stderr.strip() or add.stdout.strip() or f"exit status {add.returncode}"
            raise RuntimeError(
                f"failed to create performance baseline worktree for {base_sha}: {detail}"
            )
        worktree_added = True

        report = _run_benchmark(worktree_path, targets=targets, repeats=repeats)
        return report, base_sha
    finally:
        active_error = sys.exc_info()[1]
        cleanup_error = None
        if worktree_added:
            try:
                remove = subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree_path)],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                )
                if remove.returncode != 0:
                    cleanup_error = (
                        remove.stderr.strip()
                        or remove.stdout.strip()
                        or f"exit status {remove.returncode}"
                    )
            except Exception as exc:
                cleanup_error = str(exc)
        shutil.rmtree(tmpdir, ignore_errors=True)
        if cleanup_error:
            message = (
                f"failed to remove performance baseline worktree {worktree_path}: "
                f"{cleanup_error}"
            )
            if active_error is None:
                raise RuntimeError(message)
            if hasattr(active_error, "add_note"):
                active_error.add_note(message)


def _pct(before: float, after: float) -> float:
    if before <= 0:
        return 0.0
    return ((after - before) / before) * 100.0


def compare(
    base_report: dict[str, dict[str, float]],
    current_report: dict[str, dict[str, float]],
    time_threshold_pct: float,
    mem_threshold_pct: float,
) -> dict[str, object]:
    targets = sorted(set(base_report.keys()) | set(current_report.keys()))
    rows = []
    regressions = []

    for target in targets:
        before = base_report.get(target)
        after = current_report.get(target)
        if not before or not after:
            missing_row = {
                "target": target,
                "status": "missing",
                "before": before,
                "after": after,
            }
            rows.append(missing_row)
            regressions.append(
                {
                    "target": target,
                    "status": "missing",
                    "reason": "missing benchmark data",
                }
            )
            continue

        # Prefer medians for release decisions: the synthetic benchmark is
        # intentionally tiny, so one cold import or allocator sample can
        # dominate an average.  Older JSON reports remain compatible through
        # the avg-field fallback.
        before_time = before.get("median_time_sec", before["avg_time_sec"])
        after_time = after.get("median_time_sec", after["avg_time_sec"])
        before_mem = before.get("median_peak_mem_mb", before["avg_peak_mem_mb"])
        after_mem = after.get("median_peak_mem_mb", after["avg_peak_mem_mb"])
        time_delta = _pct(before_time, after_time)
        mem_delta = _pct(before_mem, after_mem)

        row = {
            "target": target,
            "before": before,
            "after": after,
            "time_delta_pct": time_delta,
            "mem_delta_pct": mem_delta,
        }
        rows.append(row)

        # A sub-megabyte tracemalloc difference is measurement noise for this
        # smoke dataset; require both the percentage and a 1 MB absolute rise
        # before treating memory as a regression.
        mem_absolute_delta = after_mem - before_mem
        if time_delta > time_threshold_pct or (
            mem_delta > mem_threshold_pct and mem_absolute_delta > 1.0
        ):
            regressions.append(
                {
                    "target": target,
                    "time_delta_pct": time_delta,
                    "mem_delta_pct": mem_delta,
                }
            )

    return {
        "rows": rows,
        "regressions": regressions,
        "time_threshold_pct": time_threshold_pct,
        "mem_threshold_pct": mem_threshold_pct,
    }


def _print_report(report: dict[str, object], base: str, base_sha: str) -> None:
    print("=== performance_regression_check ===")
    print(f"base: {base}")
    print(f"base_sha: {base_sha}")
    print(
        "thresholds: time<=+{:.1f}%, memory<=+{:.1f}%".format(
            report["time_threshold_pct"], report["mem_threshold_pct"]
        )
    )
    print()
    for row in report["rows"]:
        target = row["target"]
        if row.get("status") == "missing":
            print(f"- {target}: missing benchmark data")
            continue

        print(f"- {target}")
        print(
            "  median_time: {:.4f}s -> {:.4f}s ({:+.2f}%)".format(
                row["before"].get("median_time_sec", row["before"]["avg_time_sec"]),
                row["after"].get("median_time_sec", row["after"]["avg_time_sec"]),
                row["time_delta_pct"],
            )
        )
        print(
            "  median_peak_mem: {:.2f}MB -> {:.2f}MB ({:+.2f}%)".format(
                row["before"].get("median_peak_mem_mb", row["before"]["avg_peak_mem_mb"]),
                row["after"].get("median_peak_mem_mb", row["after"]["avg_peak_mem_mb"]),
                row["mem_delta_pct"],
            )
        )

    print()
    if report["regressions"]:
        print("regressions detected:")
        for reg in report["regressions"]:
            if reg.get("status") == "missing":
                print("- {target}: {reason}".format(**reg))
            else:
                print(
                    "- {target}: time {time_delta_pct:+.2f}%, mem {mem_delta_pct:+.2f}%".format(
                        **reg
                    )
                )
    else:
        print("No performance regression detected.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare hotspot plugin performance before/after")
    parser.add_argument("--base", default="HEAD", help="Git base ref (default: HEAD)")
    parser.add_argument(
        "--targets",
        default="st_waveforms,hit,hit_threshold,df,df_events",
        help="Comma-separated targets (default: st_waveforms,hit,hit_threshold,df,df_events)",
    )
    parser.add_argument(
        "--repeats", type=int, default=DEFAULT_REPEATS, help="Benchmark repeats per target"
    )
    parser.add_argument("--time-threshold-pct", type=float, default=10.0)
    parser.add_argument("--mem-threshold-pct", type=float, default=15.0)
    parser.add_argument("--json-out", default=None, help="Write report JSON to path")
    args = parser.parse_args()

    targets = [x.strip() for x in args.targets.split(",") if x.strip()]
    if not targets:
        print("ERROR: no targets specified", file=sys.stderr)
        return 2

    try:
        before, base_sha = _run_base(args.base, targets=targets, repeats=args.repeats)
        after = _run_current(targets=targets, repeats=args.repeats)
        report = compare(
            base_report=before,
            current_report=after,
            time_threshold_pct=args.time_threshold_pct,
            mem_threshold_pct=args.mem_threshold_pct,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _print_report(report, base=args.base, base_sha=base_sha)

    payload = {
        "base": args.base,
        "base_sha": base_sha,
        "targets": targets,
        "before": before,
        "after": after,
        "comparison": report,
    }

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON report written to {out}")

    return 1 if report["regressions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
