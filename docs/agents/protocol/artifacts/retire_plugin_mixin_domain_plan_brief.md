# plan_brief

- `task_id`: `retire_plugin_mixin_domain`
- `route`: `retire_compat`
- `workflow_cost`: `strict`
- `lifecycle_profile`: `compat_retirement_review`
- `risk_level`: `high`
- `scope_in`:
  - Move PluginMixin registration, validation, dynamic dependency, and DAG resolution behavior into ContextPluginDomain.
  - Remove Context inheritance from PluginMixin and delete the legacy module/import path.
  - Remove Context.register_plugin_() and migrate repository call sites to Context.register().
  - Preserve Context.resolve_dependencies() as a public delegating API.
  - Update execution, lineage, dependency tree, cache-clear script, tests, and Context architecture documentation.
- `scope_out`:
  - Plugin provides, depends_on declarations, dtype, versions, lineage format, and cache key format.
  - The unrelated dirty RecordsBundle import cycle and Context configuration API cleanup.
  - Unrelated deleted documents, notebooks, archives, and untracked workspace files.
- `required_gates`:
  - `compat_inventory_ready`
  - `deletion_scope_confirmed`
  - `targeted_context_tests`
  - `doc_sync`
  - `doc_anchors`
  - `assess_change_impact`
  - `schema_compat_check`
- `executor_role`: `executor.config`
- `blocking_assumptions`:
  - User approved direct removal of the public register_plugin_() API with no compatibility facade or deprecation period.
  - The RecordsBundle circular import remained outside this task and was resolved in a separate prerequisite commit before final gates.

## retire_compat Notes

- `compat_inventory_required`: `true`
- `compat_inventory_path`: `docs/agents/protocol/artifacts/retire_plugin_mixin_domain_compat_inventory.md`
- `executor_role_override`: `executor.config`
- `deletion_policy`: `balanced`
- `must_run_commands`:
  - `pytest -q tests/test_context_plugin_domain.py tests/test_context_core.py tests/test_cache_optimization.py tests/plugins/test_plugin_versioning.py tests/test_storage_backends.py tests/test_strax_adapter.py tests/test_time_range_query.py tests/contracts/test_plugin_contracts.py`
  - `scripts/check_doc_sync.sh` with the project Python first on PATH
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
  - `python scripts/assess_change_impact.py --base HEAD`
  - `python scripts/schema_compat_check.py --base HEAD --run-smoke`
- `public_surface_confirmation_required`: `true`, satisfied by the user plan
- `high_risk_items_redirected`: `false`
