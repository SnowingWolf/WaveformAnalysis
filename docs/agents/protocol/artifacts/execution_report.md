# Deprecated: `execution_report` artifact path

> **Deprecated.** This compatibility path is retained for links and historical
> readers only. New and active tasks must use one canonical
> `docs/agents/runs/current/<task-id>/task.yaml` record. Do not create or update
> a standalone `execution_report.md`.

The old field names (`task_id`, `workflow_cost`, `workflow_shape`,
`executor_role`, `agent_profile`, `changed_paths`, `actions_taken`,
`commands_run`, `open_risks`, and `requested_review_focus`) are represented in
`task.yaml` under its versioned `spec`/`status` contract. Historical reports
remain immutable under `docs/agents/runs/archive/legacy/`; this file is not live
state.

For the canonical record format and lifecycle rules, see
`docs/agents/protocol/README.md` and `docs/agents/lifecycle.md`.
