# plan_brief

- `task_id`: `retire_context_has_explicit_config`
- `route`: `retire_compat`
- `workflow_cost`: `strict`
- `lifecycle_profile`: `compat_retirement_review`
- `risk_level`: `high`
- `scope_in`: Remove the Context/domain helper, migrate DataFrame gain precedence to `ConfigValue`, and cover explicit `None` versus plugin-default `None`.
- `scope_out`: Other Context APIs, plugin dtype, provides, dependencies, versions, lineage, and cache keys.
- `required_gates`: `compat_inventory_ready`, `deletion_scope_confirmed`, `targeted_context_tests`, `doc_sync`, `doc_anchors`, `assess_change_impact`, `schema_compat_check`
- `executor_role`: `executor.config`
- `blocking_assumptions`: Direct API removal is approved and no deprecation facade is required.
