from __future__ import annotations

from pathlib import Path
import subprocess

import pytest
import yaml

from scripts import check_doc_anchors
from scripts.change_scope import (
    ScopeError,
    build_scope_report,
    classify_paths,
    discover_changed_paths,
    load_task_scope,
    normalize_repo_path,
    path_is_allowed,
    status_line_paths,
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _git_repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "tests@example.invalid")
    _git(root, "config", "user.name", "scope tests")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("before\n", encoding="utf-8")
    _git(root, "add", "src/app.py")
    _git(root, "commit", "-qm", "initial")
    return root, _git(root, "rev-parse", "HEAD")


def _task_path(root: Path, task_id: str = "demo", *, archive_year: str | None = None) -> Path:
    if archive_year is None:
        return root / "docs" / "agents" / "runs" / "current" / task_id / "task.yaml"
    return root / "docs" / "agents" / "runs" / "archive" / archive_year / task_id / "task.yaml"


def _write_scope_task(
    root: Path,
    base: str,
    *,
    task_id: str = "demo",
    archive_year: str | None = None,
    allowed_paths: list[str] | None = None,
    recorded_paths: list[str] | None = None,
) -> Path:
    task_path = _task_path(root, task_id, archive_year=archive_year)
    task_path.parent.mkdir(parents=True)
    task_path.write_text(
        yaml.safe_dump(
            {
                "metadata": {"id": task_id},
                "spec": {
                    "scope": {
                        "base_sha": base,
                        "allowed_paths": allowed_paths or ["src"],
                    }
                },
                "status": {
                    "execution": {"changed_paths": recorded_paths or []},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return task_path


def test_normalize_paths_reject_traversal_and_use_component_boundaries():
    assert normalize_repo_path("./scripts//check.py") == "scripts/check.py"
    assert path_is_allowed("scripts/check.py", ["scripts"])
    assert not path_is_allowed("scripts-extra/check.py", ["scripts"])
    assert classify_paths(["src/a.py", "src2/b.py"], ["src"]) == (
        ("src/a.py",),
        ("src2/b.py",),
    )
    with pytest.raises(ScopeError):
        normalize_repo_path("../outside.txt")
    with pytest.raises(ScopeError):
        normalize_repo_path("C:/outside.txt")


def test_discover_changed_paths_includes_staged_unstaged_and_untracked(tmp_path):
    root, base = _git_repo(tmp_path)
    (root / "src" / "app.py").write_text("staged\n", encoding="utf-8")
    _git(root, "add", "src/app.py")
    (root / "src" / "working.py").write_text("untracked\n", encoding="utf-8")
    (root / "notes.txt").write_text("unrelated\n", encoding="utf-8")
    assert discover_changed_paths(base, project_root=root) == (
        "notes.txt",
        "src/app.py",
        "src/working.py",
    )


def test_task_report_classifies_dirty_paths_and_recorded_scope(tmp_path):
    root, base = _git_repo(tmp_path)
    (root / "src" / "app.py").write_text("after\n", encoding="utf-8")
    (root / "outside.py").write_text("unrelated\n", encoding="utf-8")
    task_path = _write_scope_task(
        root,
        base,
        allowed_paths=["src"],
        recorded_paths=["src/app.py"],
    )
    report = build_scope_report(task=task_path, project_root=root)
    assert report.base_sha == base
    assert report.in_scope_paths == ("src/app.py",)
    assert report.out_of_scope_paths == (
        "docs/agents/runs/current/demo/task.yaml",
        "outside.py",
    )
    assert report.recorded_out_of_scope_paths == ()
    assert not report.has_recorded_scope_error


def test_task_recorded_changed_path_outside_scope_is_blocking(tmp_path):
    root, base = _git_repo(tmp_path)
    task_path = _write_scope_task(
        root,
        base,
        allowed_paths=["src"],
        recorded_paths=["outside.py"],
    )
    report = build_scope_report(task=task_path, project_root=root)
    assert report.recorded_out_of_scope_paths == ("outside.py",)
    assert report.has_recorded_scope_error


def test_task_scope_accepts_only_current_or_year_partitioned_archive_records(tmp_path):
    root, base = _git_repo(tmp_path)
    current = _write_scope_task(root, base)
    archived = _write_scope_task(root, base, archive_year="2026")

    assert load_task_scope(current, project_root=root).task_path == current
    assert load_task_scope(archived, project_root=root).task_path == archived

    outside = root / "task.yaml"
    outside.write_text(
        yaml.safe_dump(
            {
                "metadata": {"id": "demo"},
                "spec": {"scope": {"base_sha": base, "allowed_paths": ["src"]}},
                "status": {"execution": {"changed_paths": []}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ScopeError, match="docs/agents/runs/current/<id>/task.yaml"):
        load_task_scope(outside, project_root=root)


@pytest.mark.parametrize(
    "archive_year,task_id",
    [("legacy", "demo"), ("2026", "other")],
)
def test_task_scope_rejects_invalid_archive_layout_or_metadata_mismatch(
    tmp_path, archive_year, task_id
):
    root, base = _git_repo(tmp_path)
    if archive_year == "legacy":
        path = _task_path(root, task_id, archive_year=archive_year)
        path.parent.mkdir(parents=True)
        metadata_id = task_id
    else:
        path = _task_path(root, "demo", archive_year=archive_year)
        path.parent.mkdir(parents=True)
        metadata_id = task_id
    path.write_text(
        yaml.safe_dump(
            {
                "metadata": {"id": metadata_id},
                "spec": {"scope": {"base_sha": base, "allowed_paths": ["src"]}},
                "status": {"execution": {"changed_paths": []}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ScopeError):
        load_task_scope(path, project_root=root)


def test_doc_anchor_scope_errors_are_not_downgraded_to_empty_changes(monkeypatch):
    def fail(*_args, **_kwargs):
        raise ScopeError("invalid base")

    monkeypatch.setattr(check_doc_anchors, "discover_changed_paths", fail)
    with pytest.raises(ScopeError, match="invalid base"):
        check_doc_anchors.get_changed_files("bad-base")


def test_pr_workflow_uses_complete_base_for_non_task_gates():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github" / "workflows" / "agent-workflow-check.yml"
    ).read_text(encoding="utf-8")
    assert 'python scripts/assess_change_impact.py --base "${PR_BASE_SHA}"' in workflow
    assert 'python scripts/schema_compat_check.py --base "${PR_BASE_SHA}" --run-smoke' in workflow
    assert 'python scripts/check_agent_archive.py --base "${PR_BASE_SHA}"' in workflow
    assert "--task" not in workflow


def test_status_line_paths_handles_porcelain_rename():
    assert status_line_paths("R  old/name.py -> new/name.py") == (
        "old/name.py",
        "new/name.py",
    )
    assert status_line_paths("?? scripts/new.py") == ("scripts/new.py",)
