"""Exercise the managed runner with real Git and bounded fake agent responses."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

_module = importlib.util.spec_from_file_location(
    "managed_workflow", Path(__file__).parents[1] / "scripts" / "managed_workflow.py"
)
workflow = importlib.util.module_from_spec(_module)
_module.loader.exec_module(workflow)


@pytest.fixture
def setup(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    workflow.git(repo, "init")
    workflow.git(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    workflow.git(repo, "config", "user.name", "Test Runner")
    workflow.git(repo, "config", "user.email", "test@example.invalid")
    (repo / "result.txt").write_text("before\n")
    workflow.git(repo, "add", ".")
    workflow.git(repo, "commit", "-m", "initial")
    task = tmp_path / "task.yaml"
    spec = {
        "goal": "Update result",
        "scope": {
            "base_sha": workflow.git(repo, "rev-parse", "HEAD"),
            "allowed_paths": ["result.txt"],
        },
        "required_gates": ["content"],
        "acceptance_criteria": ["result is after"],
    }
    task.write_text(yaml.safe_dump({"spec": spec}))
    root = repo / ".git" / "managed-workflow"
    root.mkdir()
    args = SimpleNamespace(
        task=str(task), test=['content=test "$(cat result.txt)" = after'], max_reworks=2, timeout=10
    )
    return repo, root, args


def fake_agent(monkeypatch, decisions=("pass",), edits=None):
    calls = []
    review_count = 0

    def invoke(worktree, prompt, output, log, timeout, schema=None):
        nonlocal review_count
        calls.append("reviewer" if schema else "executor")
        log.write_text("fake agent\n")
        if schema:
            decision = decisions[min(review_count, len(decisions) - 1)]
            review_count += 1
            report = json.dumps(
                {
                    "decision": decision,
                    "report": "reviewed",
                    "findings": [] if decision == "pass" else ["fix result"],
                }
            )
        else:
            if edits:
                edits(worktree)
            else:
                (worktree / "result.txt").write_text("after\n")
            report = "Changed result."
        output.write_text(report)
        return report

    monkeypatch.setattr(workflow, "agent", invoke)
    return calls


def control(repo, root, state, command):
    return workflow.control(SimpleNamespace(command=command, run_id=state["id"]), repo, root)


def only_state(root):
    return json.loads(next(root.glob("*/state.json")).read_text())


def test_run_waits_and_accept_fast_forwards(setup, monkeypatch):
    repo, root, args = setup
    calls = fake_agent(monkeypatch)
    before = workflow.git(repo, "rev-parse", "HEAD")
    state = workflow.run(args, repo, root)
    assert calls == ["executor", "reviewer"]
    assert state["state"] == "awaiting_acceptance"
    assert workflow.git(repo, "rev-parse", "HEAD") == before
    assert (repo / "result.txt").read_text() == "before\n"
    evidence = Path(state["attempts"][0]["artifacts"])
    assert "+after" in (evidence / "diff.patch").read_text()
    assert json.loads((evidence / "tests.json").read_text())[0]["exit_code"] == 0
    accepted = control(repo, root, state, "accept")
    assert accepted["state"] == "integrated"
    assert workflow.git(repo, "rev-parse", "HEAD") == state["reviewed_head"]
    assert (repo / "result.txt").read_text() == "after\n"


def test_review_rework_is_bounded(setup, monkeypatch):
    repo, root, args = setup
    calls = fake_agent(monkeypatch, ("rework",))
    args.max_reworks = 1
    with pytest.raises(workflow.WorkflowError, match="budget exhausted"):
        workflow.run(args, repo, root)
    assert calls == ["executor", "reviewer", "executor", "reviewer"]
    assert only_state(root)["state"] == "failed"


def test_review_rework_then_pass(setup, monkeypatch):
    repo, root, args = setup
    fake_agent(monkeypatch, ("rework", "pass"))
    state = workflow.run(args, repo, root)
    assert len(state["attempts"]) == 2
    assert state["state"] == "awaiting_acceptance"


def test_failing_gate_overrides_reviewer_pass(setup, monkeypatch):
    repo, root, args = setup
    fake_agent(monkeypatch)
    args.test = ["content=exit 9"]
    args.max_reworks = 0
    with pytest.raises(workflow.WorkflowError, match="budget exhausted"):
        workflow.run(args, repo, root)
    assert only_state(root)["attempts"][0]["tests"][0]["exit_code"] == 9


def test_missing_gate_fails_before_worktree(setup):
    repo, root, args = setup
    args.test = ["other=true"]
    with pytest.raises(workflow.WorkflowError, match="missing --test"):
        workflow.run(args, repo, root)
    assert not list(root.glob("*/state.json"))


def test_scope_violation_is_preserved_and_not_committed(setup, monkeypatch):
    repo, root, args = setup
    fake_agent(monkeypatch, edits=lambda w: (w / "outside.txt").write_text("bad"))
    with pytest.raises(workflow.WorkflowError, match="out-of-scope"):
        workflow.run(args, repo, root)
    state = only_state(root)
    assert state["state"] == "failed"
    assert (Path(state["worktree"]) / "outside.txt").exists()
    assert workflow.git(state["worktree"], "rev-parse", "HEAD") == state["base_sha"]


@pytest.mark.parametrize(
    "tamper,match",
    [
        ("dirty_target", "target worktree must be clean"),
        ("dirty_managed", "reviewed worktree changed"),
        ("head_managed", "reviewed worktree changed"),
        ("target_advance", "target HEAD changed"),
        ("spec", "Task Spec changed"),
    ],
)
def test_accept_rejects_stale_or_dirty_snapshot(setup, monkeypatch, tamper, match):
    repo, root, args = setup
    fake_agent(monkeypatch)
    state = workflow.run(args, repo, root)
    if tamper == "dirty_target":
        (repo / "unrelated").write_text("dirty")
    elif tamper == "dirty_managed":
        (Path(state["worktree"]) / "result.txt").write_text("unreviewed")
    elif tamper == "head_managed":
        workflow.git(state["worktree"], "commit", "--allow-empty", "-m", "unreviewed")
    elif tamper == "target_advance":
        workflow.git(repo, "commit", "--allow-empty", "-m", "new target")
    else:
        task = Path(args.task)
        content = yaml.safe_load(task.read_text())
        content["spec"]["goal"] = "different"
        task.write_text(yaml.safe_dump(content))
    with pytest.raises(workflow.WorkflowError, match=match):
        control(repo, root, state, "accept")
    assert only_state(root)["state"] == "awaiting_acceptance"


def test_rejected_attempt_cannot_be_accepted(setup, monkeypatch):
    repo, root, args = setup
    fake_agent(monkeypatch)
    state = workflow.run(args, repo, root)
    assert control(repo, root, state, "reject")["state"] == "rejected"
    assert Path(state["worktree"]).exists()
    with pytest.raises(workflow.WorkflowError, match="requires awaiting_acceptance"):
        control(repo, root, state, "accept")


def test_active_attempt_prevents_second_run(setup, monkeypatch):
    repo, root, args = setup
    fake_agent(monkeypatch)
    workflow.run(args, repo, root)
    with pytest.raises(workflow.WorkflowError, match="active attempt"):
        workflow.run(args, repo, root)


def test_agent_failure_saved(setup, monkeypatch):
    repo, root, args = setup

    def fail(*a, **kw):
        raise workflow.WorkflowError("agent unavailable")

    monkeypatch.setattr(workflow, "agent", fail)
    with pytest.raises(workflow.WorkflowError, match="agent unavailable"):
        workflow.run(args, repo, root)
    assert only_state(root)["state"] == "failed"


def test_gate_cannot_mutate_snapshot(setup, monkeypatch):
    repo, root, args = setup
    fake_agent(monkeypatch)
    args.test = ["content=echo changed > result.txt"]
    with pytest.raises(workflow.WorkflowError, match="test commands changed"):
        workflow.run(args, repo, root)
    assert only_state(root)["state"] == "failed"


def test_dirty_target_is_not_copied_into_managed_worktree(setup, monkeypatch):
    repo, root, args = setup
    (repo / "local-only.txt").write_text("uncommitted")
    fake_agent(monkeypatch)
    state = workflow.run(args, repo, root)
    assert not (Path(state["worktree"]) / "local-only.txt").exists()
    assert (repo / "local-only.txt").read_text() == "uncommitted"
    with pytest.raises(workflow.WorkflowError, match="target worktree must be clean"):
        control(repo, root, state, "accept")


def test_logged_command_timeout_stops_shell_children(tmp_path):
    import subprocess
    import time

    marker = tmp_path / "late-write"
    with pytest.raises(subprocess.TimeoutExpired):
        workflow.logged_command(
            f"sleep 0.3; touch {marker}", tmp_path / "timeout.log", 0.05, shell=True
        )
    time.sleep(0.4)
    assert not marker.exists()


def test_scope_preserves_leading_space_paths(setup):
    repo, root, args = setup
    (repo / " result.txt").write_text("outside")
    with pytest.raises(workflow.WorkflowError, match="out-of-scope"):
        workflow.check_scope(repo, workflow.git(repo, "rev-parse", "HEAD"), ["result.txt"])
