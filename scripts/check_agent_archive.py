#!/usr/bin/env python3
"""Verify the legacy agent-artifact archive against an immutable Git base.

The first migration commit is checked against the files that existed at the
base commit under ``docs/agents/protocol/artifacts``.  Later commits are
checked against the archive manifest and archive bytes already present at the
base commit.  In both modes the current manifest is only an index to verify;
the Git base supplies the independent bytes and file set.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = Path("docs/agents/runs/archive/legacy/MANIFEST.json")
ARCHIVE_ROOT = Path("docs/agents/runs/archive/legacy")
LEGACY_ARTIFACT_ROOT = Path("docs/agents/protocol/artifacts")
GENERIC_TEMPLATES = frozenset(
    {
        "plan_brief.md",
        "execution_report.md",
        "review_report.md",
        "task_report.md",
        "compat_inventory.md",
    }
)
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class ArchiveVerificationError(ValueError):
    """Raised for Git or manifest input that cannot be verified."""


def _run_git(project_root: Path, args: list[str]) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        command = " ".join(["git", *args])
        raise ArchiveVerificationError(f"{command} failed: {detail}")
    return result.stdout


def _resolve_base(project_root: Path, base: str) -> str:
    raw = _run_git(project_root, ["rev-parse", "--verify", f"{base}^{{commit}}"])
    resolved = raw.decode("ascii", errors="strict").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", resolved):
        raise ArchiveVerificationError(f"base did not resolve to a full commit SHA: {base}")
    return resolved


def _git_blob(project_root: Path, commit: str, path: str) -> bytes:
    return _run_git(project_root, ["show", f"{commit}:{path}"])


def _git_blob_optional(project_root: Path, commit: str, path: str) -> bytes | None:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}:{path}"],
        cwd=project_root,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        return None
    return _git_blob(project_root, commit, path)


def _git_paths(project_root: Path, commit: str, root: Path) -> set[str]:
    raw = _run_git(
        project_root,
        ["ls-tree", "-r", "--name-only", "-z", commit, "--", root.as_posix()],
    )
    return {
        item.decode("utf-8")
        for item in raw.split(b"\0")
        if item and item.decode("utf-8").endswith(".md")
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchiveVerificationError(f"cannot read manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArchiveVerificationError(f"manifest {path} must contain a JSON object")
    return value


def _safe_relative(value: Any, prefix: Path) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    path = PurePosixPath(value)
    prefix_parts = prefix.parts
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    if path.parts[: len(prefix_parts)] != prefix_parts:
        return None
    return path.as_posix()


def _manifest_entries(manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    issues: list[str] = []
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        return [], ["manifest.entries must be a list"]
    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            issues.append(f"manifest.entries[{index}] must be an object")
            continue
        entries.append(entry)
    return entries, issues


def _archive_files(project_root: Path) -> tuple[set[str], list[str]]:
    archive_root = project_root / ARCHIVE_ROOT
    if not archive_root.exists():
        return set(), [f"archive root does not exist: {ARCHIVE_ROOT}"]
    issues: list[str] = []
    paths: set[str] = set()
    for path in archive_root.rglob("*.md"):
        relative = path.relative_to(project_root).as_posix()
        if path.name == "README.md":
            continue
        if path.is_symlink():
            issues.append(f"archived file must not be a symlink: {relative}")
            continue
        paths.add(relative)
    return paths, issues


def _entry_map(entries: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("archive_path")): entry
        for entry in entries
        if isinstance(entry.get("archive_path"), str)
    }


def _entry_signature(entry: dict[str, Any]) -> tuple[Any, ...]:
    return (
        entry.get("original_path"),
        entry.get("archive_path"),
        entry.get("task_id"),
        entry.get("artifact_type"),
        entry.get("size"),
        entry.get("sha256"),
    )


def _validate_manifest_shape(
    project_root: Path, manifest: dict[str, Any], entries: list[dict[str, Any]]
) -> list[str]:
    issues: list[str] = []
    if manifest.get("hash_algorithm") != "sha256":
        issues.append("manifest.hash_algorithm must be sha256")
    if manifest.get("file_count") != len(entries):
        issues.append(
            f"manifest.file_count={manifest.get('file_count')!r} does not match "
            f"entries={len(entries)}"
        )
    archive_root = project_root / ARCHIVE_ROOT
    seen_original: set[str] = set()
    seen_archive: set[str] = set()
    total_bytes = 0
    for index, entry in enumerate(entries):
        original = _safe_relative(entry.get("original_path"), LEGACY_ARTIFACT_ROOT)
        archived = _safe_relative(entry.get("archive_path"), ARCHIVE_ROOT)
        if original is None:
            issues.append(f"entries[{index}].original_path escapes legacy artifact root")
        elif original in seen_original:
            issues.append(f"duplicate original_path: {original}")
        else:
            seen_original.add(original)
        if archived is None:
            issues.append(f"entries[{index}].archive_path escapes archive root")
        elif archived in seen_archive:
            issues.append(f"duplicate archive_path: {archived}")
        else:
            seen_archive.add(archived)
            archive_path = project_root / archived
            try:
                archive_path.resolve().relative_to(archive_root.resolve())
            except ValueError:
                issues.append(f"entries[{index}].archive_path resolves outside archive root")
            if archive_path.is_symlink():
                issues.append(f"entries[{index}].archive_path must not be a symlink")

        size = entry.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            issues.append(f"entries[{index}].size must be a non-negative integer")
        else:
            total_bytes += size
        if not isinstance(entry.get("sha256"), str) or not SHA256_RE.fullmatch(entry["sha256"]):
            issues.append(f"entries[{index}].sha256 must be a 64-character hex digest")

    if manifest.get("total_bytes") != total_bytes:
        issues.append(
            f"manifest.total_bytes={manifest.get('total_bytes')!r} does not match "
            f"entry sizes={total_bytes}"
        )
    return issues


def _compare_current_archive_files(
    project_root: Path, entries: list[dict[str, Any]], archive_files: set[str]
) -> list[str]:
    expected = {
        entry.get("archive_path") for entry in entries if isinstance(entry.get("archive_path"), str)
    }
    issues: list[str] = []
    missing = sorted(expected - archive_files)
    extra = sorted(archive_files - expected)
    if missing:
        issues.append("archive files missing from working tree: " + ", ".join(missing))
    if extra:
        issues.append("archive files absent from manifest: " + ", ".join(extra))
    return issues


def _compare_blob(
    label: str, content: bytes, expected_size: Any, expected_sha256: Any
) -> list[str]:
    issues: list[str] = []
    actual_sha256 = hashlib.sha256(content).hexdigest()
    if isinstance(expected_size, int) and len(content) != expected_size:
        issues.append(f"{label}: size {len(content)} != manifest {expected_size}")
    if isinstance(expected_sha256, str) and actual_sha256 != expected_sha256:
        issues.append(f"{label}: sha256 {actual_sha256} != manifest {expected_sha256}")
    return issues


def _verify_first_migration(
    project_root: Path,
    base_commit: str,
    entries: list[dict[str, Any]],
) -> list[str]:
    issues: list[str] = []
    base_files = _git_paths(project_root, base_commit, LEGACY_ARTIFACT_ROOT)
    expected_originals = {path for path in base_files if Path(path).name not in GENERIC_TEMPLATES}
    current_originals = {
        entry.get("original_path")
        for entry in entries
        if isinstance(entry.get("original_path"), str)
    }
    missing = sorted(expected_originals - current_originals)
    extra = sorted(current_originals - expected_originals)
    if missing:
        issues.append("base artifact files missing from manifest: " + ", ".join(missing))
    if extra:
        issues.append("manifest original_path not present at base: " + ", ".join(extra))

    for entry in entries:
        original = entry.get("original_path")
        archived = entry.get("archive_path")
        if not isinstance(original, str) or not isinstance(archived, str):
            continue
        try:
            base_content = _git_blob(project_root, base_commit, original)
        except ArchiveVerificationError as exc:
            issues.append(f"{original}: cannot read base blob: {exc}")
            continue
        current_path = project_root / archived
        if not current_path.is_file() or current_path.is_symlink():
            continue
        current_content = current_path.read_bytes()
        if current_content != base_content:
            issues.append(f"{archived}: bytes differ from base {original}")
        issues.extend(
            _compare_blob(archived, current_content, len(base_content), entry.get("sha256"))
        )
    return issues


def _verify_against_existing_archive(
    project_root: Path,
    base_commit: str,
    manifest: dict[str, Any],
    entries: list[dict[str, Any]],
    base_manifest: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    base_entries, base_entry_issues = _manifest_entries(base_manifest)
    issues.extend(f"base {issue}" for issue in base_entry_issues)
    if base_entry_issues:
        return issues

    if manifest.get("file_count") != base_manifest.get("file_count"):
        issues.append("current and base manifest file_count differ")
    if manifest.get("total_bytes") != base_manifest.get("total_bytes"):
        issues.append("current and base manifest total_bytes differ")
    current_signatures = sorted(_entry_signature(entry) for entry in entries)
    base_signatures = sorted(_entry_signature(entry) for entry in base_entries)
    if current_signatures != base_signatures:
        issues.append("current manifest entries drift from base manifest")

    base_archive_files = {
        path
        for path in _git_paths(project_root, base_commit, ARCHIVE_ROOT)
        if Path(path).name != "README.md"
    }
    current_archive_files, archive_file_issues = _archive_files(project_root)
    issues.extend(archive_file_issues)
    if current_archive_files != base_archive_files:
        issues.append("current archive file set drifts from base archive file set")

    current_map = _entry_map(entries)
    base_map = _entry_map(base_entries)
    for archive_path in sorted(set(current_map) | set(base_map)):
        if archive_path not in current_map or archive_path not in base_map:
            continue
        try:
            base_content = _git_blob(project_root, base_commit, archive_path)
        except ArchiveVerificationError as exc:
            issues.append(f"{archive_path}: cannot read base archive blob: {exc}")
            continue
        current_path = project_root / archive_path
        if not current_path.is_file() or current_path.is_symlink():
            continue
        current_content = current_path.read_bytes()
        if current_content != base_content:
            issues.append(f"{archive_path}: bytes differ from base archive")
        issues.extend(
            _compare_blob(
                archive_path,
                current_content,
                current_map[archive_path].get("size"),
                current_map[archive_path].get("sha256"),
            )
        )
    return issues


def verify_archive(
    project_root: Path = PROJECT_ROOT,
    base: str = "HEAD",
    manifest_path: Path = MANIFEST_PATH,
) -> list[str]:
    """Return archive drift issues; an empty list means verification passed."""

    try:
        base_commit = _resolve_base(project_root, base)
        manifest = _load_manifest(project_root / manifest_path)
    except ArchiveVerificationError as exc:
        return [str(exc)]

    entries, issues = _manifest_entries(manifest)
    issues.extend(_validate_manifest_shape(project_root, manifest, entries))
    archive_files, archive_file_issues = _archive_files(project_root)
    issues.extend(archive_file_issues)
    issues.extend(_compare_current_archive_files(project_root, entries, archive_files))
    if issues:
        return issues

    base_manifest_bytes = _git_blob_optional(project_root, base_commit, manifest_path.as_posix())
    if base_manifest_bytes is None:
        issues.extend(_verify_first_migration(project_root, base_commit, entries))
        return issues

    try:
        base_manifest = json.loads(base_manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"base manifest is not valid JSON: {exc}"]
    if not isinstance(base_manifest, dict):
        return ["base manifest must contain a JSON object"]
    issues.extend(
        _verify_against_existing_archive(
            project_root, base_commit, manifest, entries, base_manifest
        )
    )
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD", help="Git commit to compare against")
    parser.add_argument("--project-root", "--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    issues = verify_archive(project_root, args.base, args.manifest)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1
    print(f"PASS: legacy archive verified against {args.base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
