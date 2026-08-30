# plan_brief

- `task_id`: `agent_profile_lifecycle`
- `route`: `generate_docs`
- `workflow_cost`: `strict`
- `lifecycle_profile`: `doc_only_reviewed`
- `risk_level`: `high`
- `scope_in`:
  - Replace execution-only profile selection with one lifecycle-wide `agent_profile` contract.
  - Make planning a first-class profile contribution phase with required planning outputs.
  - Keep execution route-bound and review authority independent from the selected profile.
- `scope_out`:
  - Lifecycle state changes, external agent provisioning, and plugin runtime behavior.
  - Existing unrelated documentation-site worktree changes.
- `required_gates`:
  - focused agent manifest and handoff tests
  - `render_agent_docs`
  - `doc_sync`
  - `doc_anchors`
- `executor_role`: `executor.docs`
- `agent_profile`: `none`
- `blocking_assumptions`:
  - A profile may contribute during planning without owning the `planning` state.

## Profile Planning

- `agent_profile`: `none`
- `profile_plan`:
  - No specialized profile is needed to design the generic lifecycle contract.

## generate_docs Notes

- `doc_target_scope`: `agent profile lifecycle contract and generated adapter documentation`
- `source_change_summary`: `machine contract version 3 -> 4`
- `generation_mode`: `mixed`
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest -q tests/test_render_agent_docs.py tests/test_check_agent_handoff.py`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/render_agent_docs.py --check`
  - `PATH=/home/wxy/anaconda3/envs/pyroot-kernel/bin:$PATH scripts/check_doc_sync.sh`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/check_doc_anchors.py --check-sync --base HEAD`
