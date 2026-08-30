#!/usr/bin/env python3
"""Shared task-scope and Git change discovery helpers.

This module only reads a task record and observes Git; it never executes a
task command. A task scope is declared under ``spec.scope`` and recorded
execution paths live under ``status.execution.changed_paths``.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_ARCHIVE_YEAR_RE = re.compile(r"^[0-9]{4}$")


class ScopeError(ValueError):
    """Raised when a task scope is malformed or unsafe."""


@dataclass(frozen=True)
class TaskScope:
    """Validated scope information loaded from one task YAML file."""

    task_path: Path
    base_sha: str
    allowed_paths: tuple[str, ...]
    recorded_changed_paths: tuple[str, ...]


@dataclass(frozen=True)
class ScopeReport:
    """Observed paths split into task scope and unrelated dirty paths."""

    base_sha: str
    all_changed_paths: tuple[str, ...]
    in_scope_paths: tuple[str, ...]
    out_of_scope_paths: tuple[str, ...]
    recorded_changed_paths: tuple[str, ...] = ()
    recorded_out_of_scope_paths: tuple[str, ...] = ()

    @property
    def has_recorded_scope_error(self) -> bool:
        return bool(self.recorded_out_of_scope_paths)

    def to_dict(self) -> dict[str, object]:
        return {
            "base_sha": self.base_sha,
            "all_changed_paths": list(self.all_changed_paths),
            "in_scope_paths": list(self.in_scope_paths),
            "out_of_scope_paths": list(self.out_of_scope_paths),
            "recorded_changed_paths": list(self.recorded_changed_paths),
            "recorded_out_of_scope_paths": list(self.recorded_out_of_scope_paths),
        }


def _run_git(args: Sequence[str], *, project_root: Path = PROJECT_ROOT) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise ScopeError(f"git command failed: git {' '.join(args)}\n{detail}")
    return proc.stdout


def _run_git_bytes(args: Sequence[str], *, project_root: Path = PROJECT_ROOT) -> bytes:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(project_root),
        capture_output=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="replace").strip()
        raise ScopeError(f"git command failed: git {' '.join(args)}\n{detail}")
    return proc.stdout


def normalize_repo_path(value: str) -> str:
    """Return a safe repository-relative POSIX path."""

    if not isinstance(value, str):
        raise ScopeError(f"repository path must be a string, got {type(value).__name__}")
    raw = value.strip()
    if not raw:
        raise ScopeError("repository path must not be empty")
    if "\x00" in raw:
        raise ScopeError("repository path must not contain NUL")

    normalized = raw.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise ScopeError(f"repository path must be relative: {value!r}")
    pure = PurePosixPath(normalized)
    if pure.is_absolute():
        raise ScopeError(f"repository path must be relative: {value!r}")

    parts: list[str] = []
    for part in pure.parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise ScopeError(f"repository path escapes the repository: {value!r}")
        parts.append(part)
    return "/".join(parts) or "."


def normalize_paths(values: Iterable[str], *, field: str = "paths") -> tuple[str, ...]:
    """Normalize, deduplicate, and sort repository-relative paths."""

    normalized: set[str] = set()
    for value in values:
        try:
            normalized.add(normalize_repo_path(value))
        except ScopeError as exc:
            raise ScopeError(f"invalid {field}: {exc}") from exc
    return tuple(sorted(normalized))


def path_is_allowed(path: str, allowed_paths: Iterable[str]) -> bool:
    """Return whether a path equals or is below an allowed directory prefix."""

    normalized = normalize_repo_path(path)
    for allowed in allowed_paths:
        prefix = normalize_repo_path(allowed)
        if prefix == "." or normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    return False


def _resolve_task_path(task: str | Path, project_root: Path) -> Path:
    root = project_root.resolve()
    candidate = Path(task)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ScopeError(f"task file is outside the repository: {task}") from exc
    if not resolved.is_file():
        raise ScopeError(f"task file does not exist: {task}")
    managed_root = root / "docs" / "agents" / "runs"
    try:
        relative = resolved.relative_to(managed_root)
    except ValueError as exc:
        raise ScopeError(
            "task file must be docs/agents/runs/current/<id>/task.yaml or "
            "docs/agents/runs/archive/<YYYY>/<id>/task.yaml"
        ) from exc

    parts = relative.parts
    if len(parts) == 3 and parts[0] == "current" and parts[2] == "task.yaml":
        task_id = parts[1]
    elif (
        len(parts) == 4
        and parts[0] == "archive"
        and _ARCHIVE_YEAR_RE.fullmatch(parts[1])
        and parts[3] == "task.yaml"
    ):
        task_id = parts[2]
    else:
        raise ScopeError(
            "task file must be docs/agents/runs/current/<id>/task.yaml or "
            "docs/agents/runs/archive/<YYYY>/<id>/task.yaml"
        )
    if not _TASK_ID_RE.fullmatch(task_id):
        raise ScopeError(f"task directory has an invalid id: {task_id!r}")
    return resolved


def _mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ScopeError(f"{field} must be a mapping")
    return value


def _string_list(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise ScopeError(f"{field} must be a list")
    if not all(isinstance(item, str) for item in value):
        raise ScopeError(f"{field} entries must be strings")
    return tuple(value)


def resolve_commit(ref: str, *, project_root: Path = PROJECT_ROOT) -> str:
    """Resolve a Git ref to its complete commit SHA."""

    if not isinstance(ref, str) or not ref.strip():
        raise ScopeError("Git base must be a non-empty string")
    resolved = _run_git(
        ["rev-parse", "--verify", f"{ref.strip()}^{{commit}}"],
        project_root=project_root,
    ).strip()
    if not _FULL_SHA_RE.fullmatch(resolved):
        raise ScopeError(f"Git base did not resolve to a complete commit SHA: {ref}")
    return resolved.lower()


def load_task_scope(task: str | Path, *, project_root: Path = PROJECT_ROOT) -> TaskScope:
    """Load and validate v6 scope fields from one task YAML file."""

    task_path = _resolve_task_path(task, project_root)
    try:
        payload = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ScopeError(f"failed to read task YAML {task_path}: {exc}") from exc

    root = _mapping(payload, field="task YAML")
    metadata = _mapping(root.get("metadata"), field="metadata")
    directory_id = task_path.parent.name
    metadata_id = metadata.get("id")
    if metadata_id != directory_id:
        raise ScopeError(
            "task metadata.id must match its task directory: "
            f"{metadata_id!r} != {directory_id!r}"
        )
    spec = _mapping(root.get("spec"), field="spec")
    scope = _mapping(spec.get("scope"), field="spec.scope")
    raw_base = scope.get("base_sha")
    if not isinstance(raw_base, str) or not _FULL_SHA_RE.fullmatch(raw_base.strip()):
        raise ScopeError("spec.scope.base_sha must be a complete 40-character commit SHA")
    base_sha = resolve_commit(raw_base.strip(), project_root=project_root)

    raw_allowed = scope.get("allowed_paths")
    allowed_values = _string_list(raw_allowed, field="spec.scope.allowed_paths")
    if not allowed_values:
        raise ScopeError("spec.scope.allowed_paths must contain at least one path")
    allowed_paths = normalize_paths(allowed_values, field="spec.scope.allowed_paths")

    status = root.get("status", {})
    status_map = _mapping({} if status is None else status, field="status")
    execution = status_map.get("execution", {})
    execution_map = _mapping({} if execution is None else execution, field="status.execution")
    recorded_values = _string_list(
        execution_map.get("changed_paths", []),
        field="status.execution.changed_paths",
    )
    recorded_paths = normalize_paths(recorded_values, field="status.execution.changed_paths")
    return TaskScope(task_path, base_sha, allowed_paths, recorded_paths)


def resolve_base(
    base: str | None = None,
    task: str | Path | None = None,
    *,
    project_root: Path = PROJECT_ROOT,
) -> str:
    """Resolve the effective base, preferring a task's stable SHA."""

    if task is not None:
        task_scope = load_task_scope(task, project_root=project_root)
        if base and base != "HEAD":
            requested = resolve_commit(base, project_root=project_root)
            if requested != task_scope.base_sha:
                raise ScopeError(
                    "--base conflicts with task spec.scope.base_sha: "
                    f"{requested} != {task_scope.base_sha}"
                )
        return task_scope.base_sha
    return resolve_commit(base or "HEAD", project_root=project_root)


def _split_nul(output: bytes) -> list[str]:
    return [
        item.decode("utf-8", errors="surrogateescape") for item in output.split(b"\x00") if item
    ]


def discover_changed_paths(base: str, *, project_root: Path = PROJECT_ROOT) -> tuple[str, ...]:
    """Collect tracked ``base..working-tree`` and non-ignored untracked paths."""

    resolved_base = resolve_commit(base, project_root=project_root)
    tracked = _split_nul(
        _run_git_bytes(
            [
                "-c",
                "core.quotepath=false",
                "diff",
                "--name-only",
                "--no-renames",
                "-z",
                resolved_base,
            ],
            project_root=project_root,
        )
    )
    untracked = _split_nul(
        _run_git_bytes(
            ["-c", "core.quotepath=false", "ls-files", "--others", "--exclude-standard", "-z"],
            project_root=project_root,
        )
    )
    return normalize_paths([*tracked, *untracked], field="Git changed paths")


def classify_paths(
    paths: Iterable[str],
    allowed_paths: Iterable[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split paths into allowed and unrelated paths."""

    normalized_paths = normalize_paths(paths, field="Git changed paths")
    normalized_allowed = normalize_paths(allowed_paths, field="allowed paths")
    in_scope = tuple(path for path in normalized_paths if path_is_allowed(path, normalized_allowed))
    out_of_scope = tuple(path for path in normalized_paths if path not in in_scope)
    return in_scope, out_of_scope


def build_scope_report(
    *,
    base: str | None = None,
    task: str | Path | None = None,
    project_root: Path = PROJECT_ROOT,
) -> ScopeReport:
    """Observe and classify the working tree for an optional task scope."""

    task_scope = load_task_scope(task, project_root=project_root) if task is not None else None
    effective_base = resolve_base(base, task, project_root=project_root)
    all_paths = discover_changed_paths(effective_base, project_root=project_root)
    if task_scope is None:
        in_scope, out_of_scope = all_paths, ()
        recorded_paths, recorded_out = (), ()
    else:
        in_scope, out_of_scope = classify_paths(all_paths, task_scope.allowed_paths)
        recorded_paths = task_scope.recorded_changed_paths
        _recorded_in, recorded_out = classify_paths(recorded_paths, task_scope.allowed_paths)
    return ScopeReport(
        effective_base,
        all_paths,
        in_scope,
        out_of_scope,
        recorded_paths,
        recorded_out,
    )


def _decode_status_path(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        try:
            decoded = ast.literal_eval(value)
            if isinstance(decoded, str):
                return decoded
        except (SyntaxError, ValueError):
            pass
    return value


def status_line_paths(line: str) -> tuple[str, ...]:
    """Extract one or both repository paths from porcelain-v1 status text."""

    if not line or len(line) < 3:
        return ()
    body = line[3:].strip()
    if not body:
        return ()
    if " -> " in body:
        old, new = body.split(" -> ", 1)
        return (_decode_status_path(old), _decode_status_path(new))
    return (_decode_status_path(body),)


def classify_status_lines(
    lines: Iterable[str],
    allowed_paths: Iterable[str],
) -> tuple[list[str], list[str]]:
    """Split porcelain status lines while keeping rename pairs safe."""

    allowed = normalize_paths(allowed_paths, field="allowed paths")
    in_scope: list[str] = []
    out_of_scope: list[str] = []
    for line in lines:
        paths = status_line_paths(line)
        if any(path_is_allowed(path, allowed) for path in paths):
            in_scope.append(line)
        else:
            out_of_scope.append(line)
    return in_scope, out_of_scope


def _print_paths(title: str, paths: Iterable[str]) -> None:
    print(title)
    values = list(paths)
    if not values:
        print("  (none)")
    else:
        for path in values:
            print(f"  {path}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect task-scoped Git changes")
    parser.add_argument("command", nargs="?", choices=("report", "base"), default="report")
    parser.add_argument("--base", default=None, help="Git base ref (default: HEAD, or task base)")
    parser.add_argument("--task", default=None, help="Task YAML containing spec.scope")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        if args.command == "base":
            print(resolve_base(args.base, args.task))
            return 0
        report = build_scope_report(base=args.base, task=args.task)
    except ScopeError as exc:
        print(f"ERROR: {exc}")
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"scope base: {report.base_sha}")
        _print_paths("changed paths (in scope):", report.in_scope_paths)
        _print_paths(
            "out-of-scope dirty paths (reported, non-blocking):", report.out_of_scope_paths
        )
        if report.recorded_changed_paths:
            _print_paths("task status.execution.changed_paths:", report.recorded_changed_paths)
        if report.recorded_out_of_scope_paths:
            _print_paths(
                "ERROR: recorded changed paths outside allowed_paths:",
                report.recorded_out_of_scope_paths,
            )
    return 1 if report.has_recorded_scope_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
