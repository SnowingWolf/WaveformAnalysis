#!/usr/bin/env python3
"""Build documentation from a checkout into an isolated, inspectable run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True

EXCLUDED = {
    ".git",
    "node_modules",
    ".next",
    "out",
    "dist",
    "export",
    "site_dist",
    "__pycache__",
    ".pytest_cache",
    ".cache",
    "runs",
    "plans",
}


def ignored(name: str) -> bool:
    return (
        name in EXCLUDED
        or name.endswith((".tsbuildinfo", ".pyc", ".log", ".tmp", ".swp", "~"))
        or name.startswith(".env")
    )


def reject_symlinks(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"symlink path is unsafe: {part}")


def input_fingerprint(workspace: Path) -> str:
    """Hash source bytes, including uncommitted inputs, without generated exports."""
    digest = hashlib.sha256()
    paths = [
        workspace / name
        for name in ("docs", "waveform_analysis", "scripts", "pyproject.toml", "AGENTS.md")
    ]
    files = []
    for path in paths:
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for directory, dirs, names in os.walk(path, followlinks=False):
                dirs[:] = sorted(d for d in dirs if not ignored(d))
                for name in dirs:
                    if (Path(directory) / name).is_symlink():
                        raise ValueError(f"symlink input is unsafe: {Path(directory) / name}")
                files.extend(Path(directory) / n for n in names if not ignored(n))
    for path in sorted(files):
        reject_symlinks(path)
        relative = path.relative_to(workspace).as_posix()
        content = path.read_bytes()
        digest.update(relative.encode() + b"\0" + str(len(content)).encode() + b"\0" + content)
    return digest.hexdigest()


def stage_site(site: Path, destination: Path, validate) -> None:
    """Prepare on the destination filesystem, then replace with rollback."""
    reject_symlinks(destination)
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"output is not a directory: {destination}")
    temporary = Path(tempfile.mkdtemp(prefix=".docs-build-", dir=destination.parent))
    candidate = temporary / "candidate"
    backup = temporary / "previous"
    try:
        shutil.copytree(site, candidate)
        validate(candidate)
        had_previous = destination.exists()
        if had_previous:
            destination.rename(backup)
        try:
            candidate.rename(destination)
        except BaseException:
            if had_previous:
                backup.rename(destination)
            raise
    finally:
        # Keep recovery evidence if even rollback fails.
        if not backup.exists() or destination.exists():
            shutil.rmtree(temporary)


def build(
    workspace: Path,
    run_id: str,
    build_root: Path,
    stage_output: bool = False,
    *,
    command_runner=None,
) -> dict:
    workspace = workspace.resolve()
    build_root = build_root.absolute()
    reject_symlinks(build_root)
    build_root = build_root.resolve()
    if build_root.is_relative_to(workspace):
        raise ValueError("build root must be outside workspace")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", run_id):
        raise ValueError("unsafe run ID")
    run = build_root / "runs" / run_id
    if any(path.is_relative_to(workspace) for path in (run, build_root / "npm-cache")):
        raise ValueError("run and cache must be outside workspace")
    reject_symlinks(run)
    reject_symlinks(build_root / "npm-cache")
    run.mkdir(parents=True, exist_ok=False)
    report = {
        "status": "running",
        "workspace": str(workspace),
        "run_id": run_id,
        "commands": [],
        "stage_output": stage_output,
        "artifacts": {
            k: str(run / v)
            for k, v in {
                "site": "site",
                "model": "site-model.json",
                "log": "build.log",
                "report": "report.json",
            }.items()
        },
    }
    started = time.monotonic()
    with (run / "build.log").open("w") as log:

        def runner(command, **kwargs):
            env = dict(kwargs.pop("env", os.environ))
            model_input = env.get("WAVEFORM_SITE_MODEL_PATH")
            if model_input and Path(model_input).is_file():
                shutil.copy2(model_input, run / "site-model.json")
            env.update(
                npm_config_cache=str(build_root / "npm-cache"),
                PYTHONPATH=str(workspace),
                PYTHONDONTWRITEBYTECODE="1",
            )
            record = {"command": command, "cwd": kwargs.get("cwd"), "exit_status": None}
            report["commands"].append(record)
            log.write(f"$ {' '.join(command)}\n")
            log.flush()
            try:
                result = (command_runner or subprocess.run)(
                    command,
                    **kwargs,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=max(1, 1800 - (time.monotonic() - started)),
                )
                record["exit_status"] = result.returncode
                return result
            except subprocess.CalledProcessError as exc:
                record["exit_status"] = exc.returncode
                raise
            except Exception as exc:
                record["error"] = str(exc)
                raise

        try:
            sys.path.insert(0, str(workspace))
            sys.path.insert(1, str(workspace / "scripts"))
            from build_docs_site_dist import _strip_trailing_whitespace

            from waveform_analysis.documentation import site_web
            from waveform_analysis.documentation.site_model import load_site_model

            if not Path(site_web.__file__).resolve().is_relative_to(workspace):
                raise RuntimeError(
                    "documentation imports are not from requested workspace; use a fresh CLI process"
                )
            report["import_source"] = str(Path(site_web.__file__).resolve())
            report["source_head"] = subprocess.check_output(
                ["git", "--no-optional-locks", "-C", str(workspace), "rev-parse", "HEAD"], text=True
            ).strip()
            report["dirty_paths"] = subprocess.check_output(
                [
                    "git",
                    "--no-optional-locks",
                    "-C",
                    str(workspace),
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                ],
                text=True,
            ).splitlines()
            report["input_fingerprint"] = input_fingerprint(workspace)
            app_source = workspace / "docs/site-next"
            for directory, dirs, names in os.walk(app_source):
                dirs[:] = [d for d in dirs if not ignored(d)]
                for name in dirs + [n for n in names if not ignored(n)]:
                    reject_symlinks(Path(directory) / name)
            shutil.copytree(
                app_source, run / "app", ignore=lambda _, names: [n for n in names if ignored(n)]
            )
            results = site_web.NextSiteBuilder(
                project_root=workspace,
                app_root=run / "app",
                install_dependencies=True,
                command_runner=runner,
            ).generate(run / "site")
            shutil.copy2(results["SITE_MODEL"], run / "site-model.json")
            model = load_site_model(run / "site-model.json")

            def validate(path):
                _strip_trailing_whitespace(path)
                site_web.validate_static_export(path, model=model, require_model=True)
                site_web.write_prebuilt_manifest(path)

            validate(run / "site")
            if stage_output:
                stage_site(
                    run / "site", workspace / "waveform_analysis/documentation/site_dist", validate
                )
            report["status"] = "success"
        except Exception as exc:
            report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
            log.write(report["error"] + "\n")
        finally:
            report["elapsed_seconds"] = round(time.monotonic() - started, 3)
            (run / "report.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n"
            )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("build")
    command.add_argument("--workspace", type=Path, required=True)
    command.add_argument("--run-id", required=True)
    command.add_argument(
        "--build-root", type=Path, default=Path(tempfile.gettempdir()) / "waveform-doc-build"
    )
    command.add_argument("--stage-output", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build(args.workspace, args.run_id, args.build_root, args.stage_output)
    except Exception as exc:
        print(f"docs-build: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
