#!/usr/bin/env python3
"""Compare hotspot plugin performance before/after changes."""

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_HARNESS = PROJECT_ROOT / "scripts" / "_quality_common.py"
DEFAULT_REPEATS = 5


BENCH_SNIPPET = r"""
import json
import os
from pathlib import Path
import runpy
import sys

checkout = Path.cwd().resolve()
sys.path.insert(0, str(checkout))
harness_path = Path(os.environ["QUALITY_HARNESS_PATH"]).resolve()
harness = runpy.run_path(str(harness_path))
report = harness["benchmark_hot_targets"](
    targets=json.loads(os.environ["QUALITY_TARGETS_JSON"]),
    repeats=int(os.environ["QUALITY_REPEATS"]),
)
module_paths = {
    name: str(Path(module.__file__).resolve())
    for name, module in sys.modules.items()
    if (name == "waveform_analysis" or name.startswith("waveform_analysis."))
    and getattr(module, "__file__", None)
}
if "waveform_analysis" not in module_paths:
    raise RuntimeError("benchmark did not import waveform_analysis")
for name, path in module_paths.items():
    if not Path(path).is_relative_to(checkout / "waveform_analysis"):
        raise RuntimeError(f"benchmark imported {name} outside checkout: {path}")
print(json.dumps({
    "benchmarks": report,
    "source": {
        "checkout": str(checkout),
        "executable": sys.executable,
        "python_version": sys.version,
        "harness": str(harness_path),
        "module_paths": module_paths,
    },
}, ensure_ascii=False, allow_nan=False))
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
    if not text:
        raise RuntimeError("benchmark command produced no JSON report")
    line = text.splitlines()[-1]
    return json.loads(line)


def _git_output(checkout: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(checkout), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {checkout}: {proc.stderr.strip()}")
    return proc.stdout.rstrip("\n")


def _run_checkout(
    checkout: Path, targets: list[str], repeats: int
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    commit = _git_output(checkout, "rev-parse", "--verify", "HEAD^{commit}")
    status_before = _git_output(checkout, "status", "--porcelain").splitlines()
    env = dict(os.environ)
    env["QUALITY_TARGETS_JSON"] = json.dumps(targets)
    env["QUALITY_REPEATS"] = str(repeats)
    env["QUALITY_HARNESS_PATH"] = str(BENCHMARK_HARNESS)
    payload = _run_subprocess_json(
        cmd=[sys.executable, "-I", "-B", "-c", BENCH_SNIPPET], cwd=checkout, env=env
    )
    source = payload["source"]
    source["commit"] = commit
    source["worktree_status_before"] = status_before
    source["worktree_status_after"] = _git_output(checkout, "status", "--porcelain").splitlines()
    source["dirty"] = bool(status_before or source["worktree_status_after"])
    return payload["benchmarks"], source


def _run_current(
    targets: list[str], repeats: int
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    return _run_checkout(PROJECT_ROOT, targets=targets, repeats=repeats)


def _run_base(
    base: str, targets: list[str], repeats: int
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    commit = _git_output(
        PROJECT_ROOT, "rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}"
    )
    with tempfile.TemporaryDirectory(prefix="wa-perf-base-") as tmpdir:
        worktree_path = Path(tmpdir) / "worktree"
        add = subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree_path), commit],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if add.returncode != 0:
            raise RuntimeError(
                f"base worktree unavailable for {base}: "
                f"{add.stderr.strip() or add.stdout.strip()}"
            )
        try:
            return _run_checkout(worktree_path, targets=targets, repeats=repeats)
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                check=True,
            )


def _pct(before: float, after: float) -> float | None:
    if before == 0:
        return 0.0 if after == 0 else None
    return ((after - before) / before) * 100.0


def _sample_errors(sample: dict[str, object], expected_repeats: int | None) -> list[str]:
    errors = []
    count = sample.get("sample_count")
    if type(count) is not int or count < 1:
        errors.append("sample_count must be a positive integer")
    elif expected_repeats is not None and count != expected_repeats:
        errors.append(f"sample_count {count} does not match requested repeats {expected_repeats}")
    measurements = [
        (field, sample.get(field), field.endswith("time_sec"))
        for field in (
            "avg_time_sec",
            "max_time_sec",
            "median_time_sec",
            "avg_peak_mem_mb",
            "max_peak_mem_mb",
            "median_peak_mem_mb",
        )
    ]
    samples = sample.get("samples")
    if not isinstance(samples, list) or not samples:
        errors.append("samples must be a nonempty list")
    else:
        if len(samples) != count:
            errors.append("samples length does not match sample_count")
        for index, item in enumerate(samples):
            if not isinstance(item, dict):
                errors.append(f"samples[{index}] must be a measurement object")
                continue
            measurements.extend(
                (
                    (f"samples[{index}].time_sec", item.get("time_sec"), True),
                    (f"samples[{index}].peak_mem_mb", item.get("peak_mem_mb"), False),
                )
            )
    for field, value, is_time in measurements:
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value < 0
            or (is_time and value == 0)
        ):
            errors.append(f"{field} must be finite and {'positive' if is_time else 'nonnegative'}")
    return errors


def compare(
    base_report: dict[str, dict[str, object]],
    current_report: dict[str, dict[str, object]],
    time_threshold_pct: float,
    mem_threshold_pct: float,
    expected_targets: list[str] | None = None,
    expected_repeats: int | None = None,
) -> dict[str, object]:
    targets = sorted(set(expected_targets or ()) | set(base_report) | set(current_report))
    rows = []
    regressions = []
    errors = []
    if not targets:
        errors.append("no benchmark targets available for comparison")

    for target in targets:
        before = base_report.get(target)
        after = current_report.get(target)
        if not before or not after:
            errors.append(f"{target}: missing benchmark data")
            rows.append(
                {
                    "target": target,
                    "status": "missing",
                    "before": before,
                    "after": after,
                }
            )
            continue

        sample_errors = [
            f"{side}: {error}"
            for side, sample in (("base", before), ("current", after))
            for error in _sample_errors(sample, expected_repeats)
        ]
        if sample_errors:
            errors.extend(f"{target}: {error}" for error in sample_errors)
            rows.append({"target": target, "status": "invalid", "errors": sample_errors})
            continue

        # Medians prevent a cold import or allocator sample dominating this tiny dataset.
        before_time = before["median_time_sec"]
        after_time = after["median_time_sec"]
        before_mem = before["median_peak_mem_mb"]
        after_mem = after["median_peak_mem_mb"]
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
            (mem_delta is None or mem_delta > mem_threshold_pct) and mem_absolute_delta > 1.0
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
        "errors": errors,
        "valid": not errors,
        "time_threshold_pct": time_threshold_pct,
        "mem_threshold_pct": mem_threshold_pct,
    }


def _delta_text(delta: float | None) -> str:
    return "n/a (zero baseline)" if delta is None else f"{delta:+.2f}%"


def _print_report(report: dict[str, object], base: str, provenance: dict[str, object]) -> None:
    print("=== performance_regression_check ===")
    print(f"base: {base}")
    print(
        "thresholds: time<=+{:.1f}%, memory<=+{:.1f}%".format(
            report["time_threshold_pct"], report["mem_threshold_pct"]
        )
    )
    print()
    for side, source in provenance.items():
        print(f"{side}: commit={source['commit']}, dirty={source['dirty']}")
        print(f"  checkout: {source['checkout']}")
        print(f"  executable: {source['executable']}")
        print(f"  waveform_analysis: {source['module_paths']['waveform_analysis']}")
    print()

    for row in report["rows"]:
        target = row["target"]
        if row.get("status") == "missing":
            print(f"- {target}: missing benchmark data")
            continue
        if row.get("status") == "invalid":
            print(f"- {target}: invalid benchmark data: {'; '.join(row['errors'])}")
            continue

        print(f"- {target}")
        print(
            "  median_time: {:.4f}s -> {:.4f}s ({})".format(
                row["before"]["median_time_sec"],
                row["after"]["median_time_sec"],
                _delta_text(row["time_delta_pct"]),
            )
        )
        print(
            "  median_peak_mem: {:.2f}MB -> {:.2f}MB ({})".format(
                row["before"]["median_peak_mem_mb"],
                row["after"]["median_peak_mem_mb"],
                _delta_text(row["mem_delta_pct"]),
            )
        )

    print()
    if report["errors"]:
        print("Benchmark comparison invalid:")
        for error in report["errors"]:
            print(f"- {error}")
    elif report["regressions"]:
        print("regressions detected:")
        for reg in report["regressions"]:
            print(
                f"- {reg['target']}: time {_delta_text(reg['time_delta_pct'])}, "
                f"mem {_delta_text(reg['mem_delta_pct'])}"
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
    if len(targets) != len(set(targets)):
        parser.error("benchmark targets must be unique")
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    if any(
        not math.isfinite(threshold) or threshold < 0
        for threshold in (args.time_threshold_pct, args.mem_threshold_pct)
    ):
        parser.error("benchmark thresholds must be finite and nonnegative")

    try:
        before, base_source = _run_base(args.base, targets=targets, repeats=args.repeats)
        after, current_source = _run_current(targets=targets, repeats=args.repeats)
        report = compare(
            base_report=before,
            current_report=after,
            time_threshold_pct=args.time_threshold_pct,
            mem_threshold_pct=args.mem_threshold_pct,
            expected_targets=targets,
            expected_repeats=args.repeats,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    provenance = {"base": base_source, "current": current_source}
    _print_report(report, base=args.base, provenance=provenance)

    payload = {
        "base": args.base,
        "targets": targets,
        "repeats": args.repeats,
        "before": before,
        "after": after,
        "provenance": provenance,
        "comparison": report,
    }

    if args.json_out:
        out = Path(args.json_out)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
            )
        except (OSError, ValueError) as exc:
            print(f"ERROR: could not write JSON report: {exc}", file=sys.stderr)
            return 2
        print(f"JSON report written to {out}")

    if not report["valid"]:
        return 2
    return 1 if report["regressions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
