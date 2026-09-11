# plan_brief

- `task_id`: `workflow_shape_fast_path`
- `route`: `generate_docs`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `protocol_change_reviewed`
- `risk_level`: `high`
- `scope_in`:
  - Add machine-readable `direct`, `compact`, and `staged` workflow shapes.
  - Permit low-risk light tasks to collapse formal handoffs while retaining inline verification.
  - Keep public, contract, lineage, compatibility, release, approval, and destructive work on staged flow.
  - Add a compact `task_report` template and state transition requirements.
- `scope_out`:
  - Runtime scheduler implementation, external agent provisioning, plugin behavior, and unrelated dirty files.
- `required_gates`:
  - focused manifest/lifecycle/template tests
  - `render_agent_docs`
  - `doc_sync`
  - `doc_anchors`
- `executor_role`: `executor.docs`
- `agent_profile`: `none`
- `blocking_assumptions`:
  - `direct` is read-only and has no repository artifact; the final response is the handoff record.
  - `compact` uses one `task_report` with inline verification and may use one actor for all checkpoints.
  - Any escalation trigger selects `staged` before completion.

## Profile Planning

- `agent_profile`: `none`
- `profile_plan`:
  - Compact tasks may still select a lifecycle-wide profile, but its planning, execution, and review fields are folded into `task_report`.

## generate_docs Notes

- `doc_target_scope`: `workflow shape machine contract, lifecycle transitions, and protocol templates`
- `source_change_summary`: `machine contract version 4 -> 5`
- `generation_mode`: `mixed`
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest -q tests/test_render_agent_docs.py tests/test_check_agent_handoff.py`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/render_agent_docs.py --check`
  - `PATH=/home/wxy/anaconda3/envs/pyroot-kernel/bin:$PATH scripts/check_doc_sync.sh`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/check_doc_anchors.py --check-sync --base HEAD`
