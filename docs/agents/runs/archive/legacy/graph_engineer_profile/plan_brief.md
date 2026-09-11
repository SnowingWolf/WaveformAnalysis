# plan_brief

- `contract_version`: `3`（历史记录，已由 v4 lifecycle-wide profile contract 取代）

- `task_id`: `graph_engineer_profile`
- `route`: `generate_docs`
- `workflow_cost`: `strict`
- `lifecycle_profile`: `doc_only_reviewed`
- `risk_level`: `high`
- `scope_in`:
  - Add a machine-readable `graph_engineer` agent profile without adding a lifecycle role.
  - Validate profile-to-role and profile-to-route bindings.
  - Document profile selection in shared artifacts and the skills adapter.
- `scope_out`:
  - Plugin runtime behavior, graph algorithms, external agent installation, and orchestration transport.
  - Existing unrelated documentation-site worktree changes.
- `required_gates`:
  - `tests/test_render_agent_docs.py`
  - `render_agent_docs`
  - `doc_sync`
  - `doc_anchors`
- `executor_role`: `executor.docs`
- `blocking_assumptions`:
  - `graph_engineer` is an executor specialization and cannot replace the blocking reviewer.

## generate_docs Notes

- `doc_target_scope`: `agent machine contract and generated adapter documentation`
- `source_change_summary`: `docs/agents/index.yaml becomes the profile definition source`
- `generation_mode`: `mixed`
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest -q tests/test_render_agent_docs.py`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/render_agent_docs.py --check`
  - `PATH=/home/wxy/anaconda3/envs/pyroot-kernel/bin:$PATH scripts/check_doc_sync.sh`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/check_doc_anchors.py --check-sync --base HEAD`
- `docs_expected_to_change`:
  - `AGENTS.md`
  - `docs/agents/index.yaml`
  - `docs/agents/workflows.md`
  - `docs/agents/lifecycle.md`
  - `docs/agents/adapters/skills.md`
  - `docs/agents/protocol/README.md`
  - `docs/agents/protocol/artifacts/{plan_brief,execution_report,review_report}.md`
  - `scripts/render_agent_docs.py`
  - `tests/test_render_agent_docs.py`
