# compat_inventory

- `task_id`: `context-help-plugin-docs-20260722`
- `route`: `retire_compat`
- `workflow_cost`: `strict`
- `inventory_scope`: `Context.quickstart()`, `help("quickstart")`, and the reserved data name
- `canonical_policy`: `Context.help()` provides static navigation and registered-plugin help; `QUICKSTART_GUIDE.md` remains an ordinary document

## Compat Items

- `compat_id`: `context_quickstart_api`
  - `canonical_form`: `ctx.help("examples")` or `docs/user-guide/QUICKSTART_GUIDE.md`
  - `legacy_form`: `Context.quickstart(template="basic")`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `remove`
  - `risk_level`: `high`
  - `migration_note`: Direct removal was explicitly approved; no compatibility shim is retained.

- `compat_id`: `context_help_quickstart_topic`
  - `canonical_form`: `config`, `performance`, `examples`, `plugins`, or a registered plugin topic
  - `legacy_form`: `ctx.help("quickstart")` as a fixed navigation topic
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `remove`
  - `risk_level`: `high`
  - `migration_note`: A registered plugin with `provides="quickstart"` remains queryable by both accepted plugin topic forms.

- `compat_id`: `context_quickstart_reserved_name`
  - `canonical_form`: Reserve only active Context APIs and attributes.
  - `legacy_form`: `"quickstart"` in `Context._RESERVED_NAMES`
  - `runtime_surface`: `internal`
  - `delete_action`: `remove`
  - `risk_level`: `low`
  - `migration_note`: Registration and data access for `provides="quickstart"` are covered by tests.

## Scope Decision

- `deletion_scope_confirmed`: `true`
- `quickstart_guide_removed`: `false`
- `historical_protocol_artifacts_modified`: `false`
