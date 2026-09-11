# Deprecated: `review_report` artifact path

> **Deprecated.** This compatibility path is retained for links and historical
> readers only. New and active tasks must use one canonical
> `docs/agents/runs/current/<task-id>/task.yaml` record. Do not create or update
> a standalone `review_report.md`.

The old field names (`task_id`, `workflow_cost`, `workflow_shape`, `reviewer`,
`gate_results`, `decision`, `blocking_findings`, `residual_risks`,
`follow_up_actions`, `agent_profile`, and `agent_profile_review`) are
represented in `task.yaml` under its versioned `spec`/`status` contract.
Historical reports remain immutable under
`docs/agents/runs/archive/legacy/`; this file is not live state.

For the canonical record format and lifecycle rules, see
`docs/agents/protocol/README.md` and `docs/agents/lifecycle.md`.
