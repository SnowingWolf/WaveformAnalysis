from scripts import check_agent_handoff
from scripts.change_scope import classify_status_lines


def test_summarize_status_counts_categories():
    summary = check_agent_handoff.summarize_status(
        [
            "M  docs/agents/workflows.md",
            " M AGENTS.md",
            "MM scripts/check_doc_sync.sh",
            "?? scripts/check_agent_handoff.py",
        ]
    )

    assert summary.staged == 2
    assert summary.unstaged == 2
    assert summary.untracked == 1
    assert not summary.clean


def test_evaluate_handoff_passes_when_clean():
    code, message = check_agent_handoff.evaluate_handoff([])
    assert code == 0
    assert "PASS" in message


def test_evaluate_handoff_fails_without_reason():
    code, message = check_agent_handoff.evaluate_handoff([" M AGENTS.md"])
    assert code == 1
    assert "FAIL" in message


def test_evaluate_handoff_allows_explicit_uncommitted_reason():
    code, message = check_agent_handoff.evaluate_handoff(
        [" M AGENTS.md"],
        allow_uncommitted=True,
        reason="用户未要求提交",
    )
    assert code == 0
    assert "未提交：用户未要求提交" in message


def test_evaluate_final_note_passes_with_required_handoff_text():
    code, message = check_agent_handoff.evaluate_final_note(
        "已运行 git status --short 与 git diff --stat。已提交：abc1234"
    )
    assert code == 0
    assert "PASS" in message


def test_evaluate_final_note_fails_when_commit_state_missing():
    code, message = check_agent_handoff.evaluate_final_note(
        "已运行 git status --short 与 git diff --stat。"
    )
    assert code == 1
    assert "已提交/未提交状态" in message


def test_task_scope_only_blocks_in_scope_status_lines():
    in_scope, out_of_scope = classify_status_lines(
        [
            " M scripts/check_agent_handoff.py",
            " M waveform_analysis/analysis/accessors/peak.py",
            "?? docs/notes.txt",
        ],
        ["scripts/check_agent_handoff.py"],
    )

    assert in_scope == [" M scripts/check_agent_handoff.py"]
    assert out_of_scope == [
        " M waveform_analysis/analysis/accessors/peak.py",
        "?? docs/notes.txt",
    ]
    code, message = check_agent_handoff.evaluate_handoff(in_scope)
    assert code == 1
    assert "FAIL" in message


def test_task_scope_allows_only_unrelated_dirty_status_lines():
    in_scope, out_of_scope = classify_status_lines(
        [" M waveform_analysis/analysis/accessors/peak.py"],
        ["scripts/"],
    )

    assert in_scope == []
    assert out_of_scope == [" M waveform_analysis/analysis/accessors/peak.py"]
    code, message = check_agent_handoff.evaluate_handoff(in_scope)
    assert code == 0
    assert "PASS" in message
