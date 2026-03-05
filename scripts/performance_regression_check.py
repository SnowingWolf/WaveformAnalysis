#!/usr/bin/env python3
"""Compare hotspot plugin performance before/after changes."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Tuple

from _quality_common import benchmark_hot_targets

PROJECT_ROOT = Path(__file__).resolve().parent.parent


BENCH_SNIPPET = r"""
import json
import os
import tempfile
import time
import tracemalloc
from pathlib import Path


def create_synthetic_vx2730_run(data_root, run_name="run_smoke_001", n_channels=2, n_events=12, n_samples=128):
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
        EventsPlugin,
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
            "events.use_filtered": False,
            "show_progress": False,
        },
        stats_mode="off",
    )
    ctx.register(RawFilesPlugin())
    ctx.register(WaveformsPlugin())
    ctx.register(HitFinderPlugin())
    ctx.register(BasicFeaturesPlugin())
    ctx.register(DataFramePlugin())
    ctx.register(EventsPlugin())
    return ctx


def benchmark_hot_targets(targets, repeats=2):
    samples = {name: [] for name in targets}
    for _ in range(repeats):
        for target in targets:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                data_root = tmp_path / "DAQ"
                create_synthetic_vx2730_run(data_root=data_root)
                ctx = build_context(storage_dir=tmp_path / "storage", data_root=data_root)
                run_id = "run_smoke_001"

                tracemalloc.start()
                t0 = time.perf_counter()
                _ = ctx.get_data(run_id, target)
                elapsed = time.perf_counter() - t0
                _current, peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()

                samples[target].append((elapsed, peak / (1024.0 * 1024.0)))

    out = {}
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


def main():
    targets = json.loads(os.environ["QUALITY_TARGETS_JSON"])
    repeats = int(os.environ.get("QUALITY_REPEATS", "2"))
    report = benchmark_hot_targets(targets=targets, repeats=repeats)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
"""


def _run_subprocess_json(cmd: List[str], cwd: Path, env: Dict[str, str]) -> Dict[str, object]:
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
    return json.loads(line)


def _run_current(targets: List[str], repeats: int) -> Dict[str, Dict[str, float]]:
    return benchmark_hot_targets(targets=targets, repeats=repeats)


def _run_base(
    base: str, targets: List[str], repeats: int
) -> Tuple[Dict[str, Dict[str, float]], str]:
    tmpdir = tempfile.mkdtemp(prefix="wa-perf-base-")
    worktree_path = Path(tmpdir) / "worktree"
    fallback_note = ""

    try:
        add = subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree_path), base],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if add.returncode != 0:
            fallback_note = (
                f"fallback: base worktree unavailable ({add.stderr.strip() or add.stdout.strip()})"
            )
            return benchmark_hot_targets(targets=targets, repeats=repeats), fallback_note

        env = dict(os.environ)
        env["QUALITY_TARGETS_JSON"] = json.dumps(targets)
        env["QUALITY_REPEATS"] = str(repeats)

        report = _run_subprocess_json(
            cmd=[sys.executable, "-c", BENCH_SNIPPET],
            cwd=worktree_path,
            env=env,
        )
        return report, fallback_note
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        shutil.rmtree(tmpdir, ignore_errors=True)


def _pct(before: float, after: float) -> float:
    if before <= 0:
        return 0.0
    return ((after - before) / before) * 100.0


def compare(
    base_report: Dict[str, Dict[str, float]],
    current_report: Dict[str, Dict[str, float]],
    time_threshold_pct: float,
    mem_threshold_pct: float,
) -> Dict[str, object]:
    targets = sorted(set(base_report.keys()) | set(current_report.keys()))
    rows = []
    regressions = []

    for target in targets:
        before = base_report.get(target)
        after = current_report.get(target)
        if not before or not after:
            rows.append(
                {
                    "target": target,
                    "status": "missing",
                    "before": before,
                    "after": after,
                }
            )
            continue

        time_delta = _pct(before["avg_time_sec"], after["avg_time_sec"])
        mem_delta = _pct(before["avg_peak_mem_mb"], after["avg_peak_mem_mb"])

        row = {
            "target": target,
            "before": before,
            "after": after,
            "time_delta_pct": time_delta,
            "mem_delta_pct": mem_delta,
        }
        rows.append(row)

        if time_delta > time_threshold_pct or mem_delta > mem_threshold_pct:
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


def _print_report(report: Dict[str, object], base: str) -> None:
    print("=== performance_regression_check ===")
    print(f"base: {base}")
    print(
        "thresholds: time<=+{:.1f}%, memory<=+{:.1f}%".format(
            report["time_threshold_pct"], report["mem_threshold_pct"]
        )
    )
    print()
    if report.get("base_note"):
        print("{}".format(report["base_note"]))
        print()

    for row in report["rows"]:
        target = row["target"]
        if row.get("status") == "missing":
            print(f"- {target}: missing benchmark data")
            continue

        print(f"- {target}")
        print(
            "  time: {:.4f}s -> {:.4f}s ({:+.2f}%)".format(
                row["before"]["avg_time_sec"],
                row["after"]["avg_time_sec"],
                row["time_delta_pct"],
            )
        )
        print(
            "  peak_mem: {:.2f}MB -> {:.2f}MB ({:+.2f}%)".format(
                row["before"]["avg_peak_mem_mb"],
                row["after"]["avg_peak_mem_mb"],
                row["mem_delta_pct"],
            )
        )

    print()
    if report["regressions"]:
        print("regressions detected:")
        for reg in report["regressions"]:
            print(
                "- {target}: time {time_delta_pct:+.2f}%, mem {mem_delta_pct:+.2f}%".format(**reg)
            )
    else:
        print("No performance regression detected.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare hotspot plugin performance before/after")
    parser.add_argument("--base", default="HEAD", help="Git base ref (default: HEAD)")
    parser.add_argument(
        "--targets",
        default="st_waveforms,hit,df,events",
        help="Comma-separated targets (default: st_waveforms,hit,df,events)",
    )
    parser.add_argument("--repeats", type=int, default=2, help="Benchmark repeats per target")
    parser.add_argument("--time-threshold-pct", type=float, default=10.0)
    parser.add_argument("--mem-threshold-pct", type=float, default=15.0)
    parser.add_argument("--json-out", default=None, help="Write report JSON to path")
    args = parser.parse_args()

    targets = [x.strip() for x in args.targets.split(",") if x.strip()]
    if not targets:
        print("ERROR: no targets specified", file=sys.stderr)
        return 2

    try:
        before, base_note = _run_base(args.base, targets=targets, repeats=args.repeats)
        after = _run_current(targets=targets, repeats=args.repeats)
        report = compare(
            base_report=before,
            current_report=after,
            time_threshold_pct=args.time_threshold_pct,
            mem_threshold_pct=args.mem_threshold_pct,
        )
        report["base_note"] = base_note
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _print_report(report, base=args.base)

    payload = {
        "base": args.base,
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
