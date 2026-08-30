# Deprecated: `plan_brief` artifact path

> **Deprecated.** This compatibility path is retained for links and historical
> readers only. New and active tasks must use one canonical
> `docs/agents/runs/current/<task-id>/task.yaml` record. Do not create or update
> a standalone `plan_brief.md`.

The old field names (`task_id`, `route`, `workflow_cost`, `workflow_shape`,
`lifecycle_profile`, `risk_level`, `scope_in`, `scope_out`, `required_gates`,
`executor_role`, `agent_profile`, `profile_plan`, and
`blocking_assumptions`) are represented in `task.yaml` under its versioned
`spec`/`status` contract. Historical reports remain immutable under
`docs/agents/runs/archive/legacy/`; this file is not live state.

For the canonical record format and lifecycle rules, see
`docs/agents/protocol/README.md` and `docs/agents/lifecycle.md`.
