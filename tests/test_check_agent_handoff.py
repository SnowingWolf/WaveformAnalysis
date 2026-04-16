from scripts import check_agent_handoff


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
