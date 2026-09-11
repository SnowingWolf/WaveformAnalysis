# Deprecated: `task_report` artifact path

> **Deprecated.** This compatibility path is retained for links and historical
> readers only. New and active tasks must use one canonical
> `docs/agents/runs/current/<task-id>/task.yaml` record. Do not create or update
> a standalone `task_report.md`.

The old field names (`task_id`, `route`, `workflow_cost`, `workflow_shape`,
`scope`, `actions_taken`, `changed_paths`, `verification`, `decision`,
`commit_status`, `open_risks`, `agent_profile`, `profile_plan`, and
`agent_profile_review`) are represented in `task.yaml` under its versioned
`spec`/`status` contract. Historical reports remain immutable under
`docs/agents/runs/archive/legacy/`; this file is not live state.

For the canonical record format and lifecycle rules, see
`docs/agents/protocol/README.md` and `docs/agents/lifecycle.md`.
