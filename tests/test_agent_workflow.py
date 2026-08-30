from __future__ import annotations

from argparse import Namespace
import builtins
import json
from pathlib import Path

import pytest
import yaml

from scripts import agent_workflow


def _manifest() -> dict:
    return agent_workflow._load_manifest(agent_workflow.PROJECT_ROOT)


def _task(task_id: str = "demo-task", *, shape: str = "staged") -> dict:
    return {
        "api_version": agent_workflow.API_VERSION,
        "kind": agent_workflow.KIND,
        "metadata": {
            "id": task_id,
            "generation": 1,
            "created_at": "2026-08-31T00:00:00Z",
            "updated_at": "2026-08-31T00:00:00Z",
        },
        "spec": {
            "goal": "exercise the workflow contract",
            "route": "modify_code",
            "workflow_cost": "standard",
            "workflow_shape": shape,
            "risk_level": "low",
            "scope": {
                "base_sha": "a" * 40,
                "allowed_paths": ["scripts", "tests/test_agent_workflow.py"],
            },
            "acceptance_criteria": ["the task validates"],
            "required_gates": ["targeted_tests"],
            "assignment": {
                "planner_role": "planner",
                "executor_role": "executor.code",
                "reviewer_role": "reviewer",
            },
        },
        "status": {
            "state": "created",
            "transitions": [],
            "plan_sha256": None,
            "execution": {},
            "review": {},
            "approval": {},
            "handoff": {},
        },
    }


def _namespace(task_id: str, target: str, **overrides: object) -> Namespace:
    values = {
        "task_id": task_id,
        "to_state": target,
        "to_option": None,
        "scope_changed": False,
        "actor": None,
        "condition": None,
        "approval_evidence": None,
        "approval_json": None,
        "execution_json": None,
        "review_json": None,
        "handoff_json": None,
    }
    values.update(overrides)
    return Namespace(**values)


def _write_task(root: Path, task: dict) -> Path:
    path = root / agent_workflow.CURRENT_ROOT / task["metadata"]["id"] / "task.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(task, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def test_manifest_is_v6_and_declares_canonical_code_route_and_aliases():
    manifest = _manifest()
    assert manifest["version"] == 6
    role_ids = {entry["id"] for entry in manifest["agent_roles"]}
    assert "executor.code" in role_ids
    route, was_alias = agent_workflow.resolve_route(manifest, "modify_context")
    assert route["task"] == "modify_code"
    assert was_alias is True
    assert agent_workflow.route_info(manifest, "refactor")["canonical_route"] == "modify_code"
    assert route["profile_doc"] == "docs/agents/protocol/route-profiles/modify_code.md"
    assert agent_workflow.validate_manifest(manifest) == []


def test_schema_declares_required_v1_contract():
    schema = json.loads(agent_workflow.TASK_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["api_version"]["const"] == agent_workflow.API_VERSION
    assert schema["properties"]["kind"]["const"] == agent_workflow.KIND
    assert set(schema["$defs"]["metadata"]["required"]) == {
        "id",
        "generation",
        "created_at",
        "updated_at",
    }
    assert set(schema["$defs"]["spec"]["required"]) >= {
        "goal",
        "route",
        "workflow_cost",
        "workflow_shape",
        "risk_level",
        "scope",
        "acceptance_criteria",
        "required_gates",
        "assignment",
    }
    assert set(schema["$defs"]["status"]["required"]) >= {
        "state",
        "transitions",
        "plan_sha256",
        "execution",
        "review",
        "approval",
        "handoff",
    }


def test_canonical_spec_digest_is_order_independent():
    task = _task()
    spec = task["spec"]
    reordered = {key: spec[key] for key in reversed(list(spec))}
    assert agent_workflow.canonical_spec_sha256(spec) == agent_workflow.canonical_spec_sha256(
        reordered
    )


def test_validate_task_rejects_absolute_parent_and_empty_scope_paths():
    manifest = _manifest()
    for invalid in ("/tmp/secret", "../outside", "nested/../../outside", ""):
        task = _task()
        task["spec"]["scope"]["allowed_paths"] = [invalid]
        issues = agent_workflow.validate_task(task, manifest=manifest)
        assert any("allowed_paths[0]" in issue for issue in issues), invalid
    task = _task()
    task["spec"]["scope"]["allowed_paths"] = []
    issues = agent_workflow.validate_task(task, manifest=manifest)
    assert any("at least one path" in issue for issue in issues)
    strict_issues = agent_workflow.validate_task(task, manifest=manifest, strict=True)
    assert any("minItems" in issue or "non-empty" in issue for issue in strict_issues)


def test_strict_validation_uses_checked_in_schema_and_requires_transition_at():
    task = _task()
    task["status"].update(
        {
            "state": "planning",
            "transitions": [{"from": None, "to": "planning"}],
        }
    )
    issues = agent_workflow.validate_task(
        task, manifest=_manifest(), strict=True, project_root=agent_workflow.PROJECT_ROOT
    )
    assert any("status.transitions[0].at" in issue for issue in issues)
    assert any(issue.startswith("JSON Schema violation") for issue in issues)


def test_strict_validation_fails_closed_when_jsonschema_is_unavailable(monkeypatch):
    real_import = builtins.__import__

    def import_without_jsonschema(name, *args, **kwargs):
        if name == "jsonschema":
            raise ImportError("simulated missing dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_jsonschema)
    with pytest.raises(agent_workflow.WorkflowError, match="jsonschema is required"):
        agent_workflow.validate_task(_task(), manifest=_manifest(), strict=True)


def test_transition_ready_freezes_spec_and_detects_later_spec_drift(tmp_path: Path, monkeypatch):
    manifest = _manifest()
    task = _task()
    path = _write_task(tmp_path, task)
    monkeypatch.setattr(agent_workflow, "_load_manifest", lambda _: manifest)
    monkeypatch.setattr(agent_workflow, "_validate_manifest", lambda *_: [])
    agent_workflow.transition_task(_namespace("demo-task", "planning"), tmp_path)
    agent_workflow.transition_task(_namespace("demo-task", "ready_for_execution"), tmp_path)
    ready = agent_workflow._load_yaml(path)
    expected = agent_workflow.canonical_spec_sha256(ready["spec"])
    assert ready["status"]["plan_sha256"] == expected
    assert (
        agent_workflow.validate_task(
            ready, manifest=manifest, task_path=path, project_root=tmp_path
        )
        == []
    )
    ready["spec"]["goal"] = "changed after approval"
    assert any(
        "does not match the current canonical spec" in issue
        for issue in agent_workflow.validate_task(
            ready, manifest=manifest, task_path=path, project_root=tmp_path
        )
    )


def test_scope_changed_replanning_increments_generation_and_clears_evidence(
    tmp_path: Path, monkeypatch
):
    manifest = _manifest()
    task = _task()
    digest = agent_workflow.canonical_spec_sha256(task["spec"])
    task["status"].update(
        {
            "state": "rework_required",
            "transitions": [
                {"from": None, "to": "planning", "at": "x"},
                {"from": "planning", "to": "ready_for_execution", "at": "x"},
                {"from": "ready_for_execution", "to": "executing", "at": "x"},
                {"from": "executing", "to": "reviewing", "at": "x"},
                {"from": "reviewing", "to": "rework_required", "at": "x"},
            ],
            "plan_sha256": digest,
            "execution": {"commands": ["test"]},
            "review": {"decision": "rework_required"},
            "approval": {"evidence": ["approval"], "plan_sha256": digest},
            "handoff": {"owner": "executor.code"},
        }
    )
    path = _write_task(tmp_path, task)
    monkeypatch.setattr(agent_workflow, "_load_manifest", lambda _: manifest)
    monkeypatch.setattr(agent_workflow, "_validate_manifest", lambda *_: [])
    agent_workflow.transition_task(
        _namespace("demo-task", "planning", scope_changed=True), tmp_path
    )
    replanned = agent_workflow._load_yaml(path)
    assert replanned["metadata"]["generation"] == 2
    assert replanned["status"]["state"] == "planning"
    assert replanned["status"]["plan_sha256"] is None
    assert replanned["status"]["execution"] == {}
    assert replanned["status"]["review"] == {}
    assert replanned["status"]["approval"] == {}
    assert replanned["status"]["handoff"] == {}
    assert (
        agent_workflow.validate_task(
            replanned, manifest=manifest, task_path=path, project_root=tmp_path
        )
        == []
    )


def test_approval_evidence_must_bind_current_plan_digest(tmp_path: Path, monkeypatch):
    manifest = _manifest()
    task = _task()
    digest = agent_workflow.canonical_spec_sha256(task["spec"])
    task["status"].update(
        {
            "state": "awaiting_approval",
            "transitions": [
                {"from": None, "to": "planning", "at": "x"},
                {"from": "planning", "to": "awaiting_approval", "at": "x"},
            ],
            "plan_sha256": digest,
        }
    )
    path = _write_task(tmp_path, task)
    monkeypatch.setattr(agent_workflow, "_load_manifest", lambda _: manifest)
    monkeypatch.setattr(agent_workflow, "_validate_manifest", lambda *_: [])
    with pytest.raises(agent_workflow.WorkflowError, match="approval evidence"):
        agent_workflow.transition_task(
            _namespace(
                "demo-task",
                "ready_for_execution",
                approval_json=json.dumps({"evidence": ["stale"], "plan_sha256": "b" * 64}),
            ),
            tmp_path,
        )
    assert path.exists()


def test_staged_completion_requires_execution_review_gates_and_reviewer_actor(
    tmp_path: Path, monkeypatch
):
    manifest = _manifest()
    monkeypatch.setattr(agent_workflow, "_load_manifest", lambda _: manifest)
    monkeypatch.setattr(agent_workflow, "_validate_manifest", lambda *_: [])
    task = _task("staged-evidence")
    path = _write_task(tmp_path, task)

    agent_workflow.transition_task(_namespace("staged-evidence", "planning"), tmp_path)
    agent_workflow.transition_task(_namespace("staged-evidence", "ready_for_execution"), tmp_path)
    agent_workflow.transition_task(_namespace("staged-evidence", "executing"), tmp_path)
    with pytest.raises(agent_workflow.WorkflowError, match="execution evidence"):
        agent_workflow.transition_task(_namespace("staged-evidence", "reviewing"), tmp_path)

    execution = {"execution_report": {"commands_run": ["pytest"], "verification": "PASS"}}
    agent_workflow.transition_task(
        _namespace(
            "staged-evidence",
            "reviewing",
            actor="executor.code",
            execution_json=json.dumps(execution),
        ),
        tmp_path,
    )
    digest = agent_workflow.canonical_spec_sha256(agent_workflow._load_yaml(path)["spec"])
    review = {
        "reviewer_actor": "reviewer",
        "decision": "completed",
        "plan_sha256": digest,
        "gate_results": {"targeted_tests": "PASS"},
    }
    with pytest.raises(agent_workflow.WorkflowError, match="requires reviewer actor"):
        agent_workflow.transition_task(
            _namespace(
                "staged-evidence",
                "completed",
                actor="executor.code",
                review_json=json.dumps(review),
            ),
            tmp_path,
        )

    failed_review = dict(review)
    failed_review["gate_results"] = {"targeted_tests": "FAIL"}
    with pytest.raises(agent_workflow.WorkflowError, match="required gate"):
        agent_workflow.transition_task(
            _namespace(
                "staged-evidence",
                "completed",
                actor="reviewer",
                review_json=json.dumps(failed_review),
            ),
            tmp_path,
        )

    agent_workflow.transition_task(
        _namespace(
            "staged-evidence",
            "completed",
            actor="reviewer",
            review_json=json.dumps(review),
        ),
        tmp_path,
    )
    completed = agent_workflow._load_yaml(path)
    assert completed["status"]["state"] == "completed"


def test_managed_task_and_archive_paths_reject_symlinks(tmp_path: Path):
    outside = tmp_path / "outside-task.yaml"
    outside.write_text("not a managed task", encoding="utf-8")
    linked_task = tmp_path / agent_workflow.CURRENT_ROOT / "linked" / "task.yaml"
    linked_task.parent.mkdir(parents=True)
    linked_task.symlink_to(outside)
    with pytest.raises(agent_workflow.WorkflowError, match="must not be a symlink"):
        agent_workflow._task_path("linked", tmp_path, allow_archive=False)

    archive_root = tmp_path / agent_workflow.ARCHIVE_ROOT
    archive_root.mkdir(parents=True)
    outside_archive = tmp_path / "outside-archive"
    outside_archive.mkdir()
    (archive_root / "2026").symlink_to(outside_archive, target_is_directory=True)
    with pytest.raises(agent_workflow.WorkflowError, match="archive destination"):
        agent_workflow._archive_destination(tmp_path, "2026", "demo")


def test_compact_and_direct_shortcuts_freeze_their_plan(tmp_path: Path, monkeypatch):
    manifest = _manifest()
    monkeypatch.setattr(agent_workflow, "_load_manifest", lambda _: manifest)
    monkeypatch.setattr(agent_workflow, "_validate_manifest", lambda *_: [])
    compact = _task("compact-task", shape="compact")
    compact["spec"]["route"] = "debug_cache"
    compact["spec"]["workflow_cost"] = "light"
    compact["spec"]["assignment"]["executor_role"] = "executor.config"
    compact_path = _write_task(tmp_path, compact)
    agent_workflow.transition_task(_namespace("compact-task", "executing"), tmp_path)
    with pytest.raises(agent_workflow.WorkflowError, match="execution/task report evidence"):
        agent_workflow.transition_task(_namespace("compact-task", "completed"), tmp_path)
    agent_workflow.transition_task(
        _namespace(
            "compact-task",
            "completed",
            execution_json=json.dumps({"task_report": {"verification": "PASS"}}),
        ),
        tmp_path,
    )
    compact_after = agent_workflow._load_yaml(compact_path)
    assert compact_after["status"]["plan_sha256"] == agent_workflow.canonical_spec_sha256(
        compact_after["spec"]
    )
    direct = _task("direct-task", shape="direct")
    direct["spec"]["route"] = "debug_cache"
    direct["spec"]["workflow_cost"] = "light"
    direct["spec"]["assignment"]["executor_role"] = "executor.config"
    direct_path = _write_task(tmp_path, direct)
    agent_workflow.transition_task(_namespace("direct-task", "completed"), tmp_path)
    direct_after = agent_workflow._load_yaml(direct_path)
    assert direct_after["status"]["plan_sha256"] == agent_workflow.canonical_spec_sha256(
        direct_after["spec"]
    )
