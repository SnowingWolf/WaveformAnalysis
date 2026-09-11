from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from scripts import check_agent_archive


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _write_manifest(root: Path, content: bytes) -> None:
    archive_path = check_agent_archive.ARCHIVE_ROOT / "demo-task" / "execution_report.md"
    manifest = {
        "kind": "HistoricalAgentArtifactArchiveManifest",
        "version": 1,
        "hash_algorithm": "sha256",
        "source_root": check_agent_archive.LEGACY_ARTIFACT_ROOT.as_posix(),
        "archive_root": check_agent_archive.ARCHIVE_ROOT.as_posix(),
        "file_count": 1,
        "total_bytes": len(content),
        "entries": [
            {
                "original_path": (
                    check_agent_archive.LEGACY_ARTIFACT_ROOT / "demo_execution_report.md"
                ).as_posix(),
                "archive_path": archive_path.as_posix(),
                "task_id": "demo-task",
                "artifact_type": "execution_report",
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        ],
    }
    manifest_path = root / check_agent_archive.MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def test_archive_verifier_checks_first_migration_and_later_base_archive(tmp_path: Path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "archive-test@example.invalid")
    _git(tmp_path, "config", "user.name", "archive-test")

    original = tmp_path / check_agent_archive.LEGACY_ARTIFACT_ROOT / "demo_execution_report.md"
    original.parent.mkdir(parents=True)
    content = b"original report bytes\n"
    original.write_bytes(content)
    _git(tmp_path, "add", str(check_agent_archive.LEGACY_ARTIFACT_ROOT))
    _git(tmp_path, "commit", "-qm", "base")

    archived = tmp_path / check_agent_archive.ARCHIVE_ROOT / "demo-task" / "execution_report.md"
    archived.parent.mkdir(parents=True)
    archived.write_bytes(content)
    _write_manifest(tmp_path, content)

    # The migration commit has no archive manifest at its base, so original_path
    # must be resolved from the base artifact tree and compared byte-for-byte.
    assert check_agent_archive.verify_archive(tmp_path, "HEAD") == []

    _git(tmp_path, "add", str(check_agent_archive.ARCHIVE_ROOT))
    _git(tmp_path, "commit", "-qm", "archive")
    assert check_agent_archive.verify_archive(tmp_path, "HEAD") == []

    archived.write_bytes(b"tampered report bytes\n")
    issues = check_agent_archive.verify_archive(tmp_path, "HEAD")
    assert any("bytes differ from base archive" in issue for issue in issues)


def test_archive_verifier_rejects_manifest_paths_outside_archive_root(tmp_path: Path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "archive-test@example.invalid")
    _git(tmp_path, "config", "user.name", "archive-test")
    _git(tmp_path, "commit", "--allow-empty", "-qm", "base")

    archive_root = tmp_path / check_agent_archive.ARCHIVE_ROOT
    archive_root.mkdir(parents=True)
    manifest_path = tmp_path / check_agent_archive.MANIFEST_PATH
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "hash_algorithm": "sha256",
                "file_count": 1,
                "total_bytes": 0,
                "entries": [
                    {
                        "original_path": "docs/agents/protocol/artifacts/demo.md",
                        "archive_path": "docs/agents/runs/archive/legacy/../outside.md",
                        "size": 0,
                        "sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    # No Git base is needed to establish the path-safety failure.
    issues = check_agent_archive.verify_archive(tmp_path, "HEAD")

    assert any("archive_path escapes archive root" in issue for issue in issues)
