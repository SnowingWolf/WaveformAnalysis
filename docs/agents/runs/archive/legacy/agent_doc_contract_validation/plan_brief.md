# plan_brief

- `task_id`: `agent_doc_contract_validation`
- `route`: `modify_plugin`
- `workflow_cost`: `strict`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `high`
- `scope_in`:
  - Add deterministic source contract facts and block generated AgentDoc claims that contradict them.
  - Cover `raw_files` output type, option defaults, and returned-call arguments.
- `scope_out`:
  - Plugin compute behavior, existing published YAML, and model-provider configuration.
- `required_gates`:
  - Focused documentation DAG tests.
  - Documentation sync and anchors.
  - Change impact and schema compatibility smoke checks.
- `executor_role`: `executor.plugin`
- `blocking_assumptions`:
  - Existing untracked local artifacts remain outside the scoped commit.

## modify_plugin Notes

- `change_level`: `L2`
- `provides_impact`: `none`
- `depends_on_impact`: `none`
- `output_contract_impact`: `documentation DAG PluginFacts contract only`
- `version_action`: `documentation DAG version 1 -> 2`
- `docs_sync_required`: `true`
- `execution_backend_decision`:
  - `backend`: `python`
  - `backend_reason`: `source inspection and string validation only`
  - `parallel_scope`: `none`
  - `fallback_path`: `reject candidate before semantic verification`
  - `benchmark_required`: `false`
