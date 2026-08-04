# compat_inventory

- `task_id`: `retire_context_has_explicit_config`
- `route`: `retire_compat`
- `workflow_cost`: `strict`
- `inventory_scope`: `Context` explicit-configuration source query
- `canonical_policy`: Call `Context.get_config_value()` and inspect `ConfigValue.source` or `ConfigValue.is_explicit()`.

## compat_items

- `compat_id`: `context_has_explicit_config`
  - `kind`: `public_python_api`
  - `canonical_form`: `Context.get_config_value(plugin, name, adapter_name=...).is_explicit()`
  - `legacy_form`: `Context.has_explicit_config(plugin, name, adapter_name=None)`
  - `location`: `Context`, `ContextConfigDomain`, and `DataFramePlugin`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `remove`
  - `risk_level`: `high`
  - `required_gates`: `targeted_context_tests`, `doc_sync`, `doc_anchors`, `assess_change_impact`, `schema_compat_check`
  - `migration_note`: Direct removal was user-approved; `ConfigValue` remains the canonical source metadata API.
  - `review_decision`: `approved`
