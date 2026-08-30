# Deprecated: `compat_inventory` artifact path

> **Deprecated.** This compatibility path is retained for links and historical
> readers only. New and active tasks must use one canonical
> `docs/agents/runs/current/<task-id>/task.yaml` record. Do not create or update
> a standalone `compat_inventory.md`.

The old field names (`task_id`, `route`, `inventory_scope`,
`canonical_policy`, `compat_items`, `compat_id`, `kind`, `canonical_form`,
`legacy_form`, `location`, `runtime_surface`, `delete_action`, `risk_level`,
`required_gates`, `migration_note`, and `review_decision`) are represented in
`task.yaml` under its versioned `spec`/`status` contract. Historical reports
remain immutable under `docs/agents/runs/archive/legacy/`; this file is not live
state.

For the canonical record format and lifecycle rules, see
`docs/agents/protocol/README.md` and `docs/agents/lifecycle.md`.
