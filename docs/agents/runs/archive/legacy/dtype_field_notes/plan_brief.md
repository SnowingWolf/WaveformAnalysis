# plan_brief

- `task_id`: `dtype_field_notes`
- `route`: `modify_plugin`
- `workflow_cost`: `strict`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `high`
- `scope_in`:
  - Add a package-distributed, source-reviewed output-field narrative resource for all registered builtin plugin outputs.
  - Make the documentation generator use those notes while preserving explicit schema documentation as the highest priority.
  - Regenerate Auto, Agent, and static HTML references.
- `scope_out`:
  - Plugin compute behavior, output dtype layout, configuration, dependencies, published AgentDoc YAML, and model-provider configuration.
- `required_gates`:
  - Field-name coverage against registered PluginDocGenerator output fields.
  - Documentation generator and published-doc tests.
  - Wheel package-data inspection.
  - Documentation sync, anchors, impact analysis, and schema compatibility smoke.
- `executor_role`: `executor.plugin`
- `blocking_assumptions`:
  - DeepSeek-generated narratives are accepted only after deterministic field-set validation and source-review artifact inspection.

## modify_plugin Notes

- `change_level`: `L0`
- `provides_impact`: `none`
- `depends_on_impact`: `none`
- `output_contract_impact`: `documentation metadata only; dtype layout unchanged`
- `version_action`: `not required`
- `docs_sync_required`: `true`
- `execution_backend_decision`:
  - `backend`: `python`
  - `backend_reason`: `metadata resource loading and static rendering only`
  - `parallel_scope`: `none`
  - `fallback_path`: `explicit OutputSchema and source agent_doc notes remain available`
  - `benchmark_required`: `false`
