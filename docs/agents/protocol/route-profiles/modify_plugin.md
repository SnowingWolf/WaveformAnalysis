# Route Profile: modify_plugin

<!-- BEGIN GENERATED: profile_summary_modify_plugin -->
## Use When
- 插件与契约改动

## Route
- `task`: `modify_plugin`
- `workflow_cost`: `standard`
- `primary_doc`: `docs/agents/workflows.md`
- `profile_doc`: `docs/agents/protocol/route-profiles/modify_plugin.md`

## Blocking Gates
- `assess_change_impact`
- `schema_compat_check`
- `doc_sync`
- `doc_anchors`

## Gate Trigger Policy
- L0 docs/comment-only changes may use light workflow with doc gates only
- L1 internal algorithm changes use standard workflow with targeted tests and impact assessment
- L2/L3 contract, dtype, dependency, or cache-lineage changes escalate to strict workflow

## Canonical Commands
- `waveform-docs generate plugins-agent --plugin <provides>`
- `python scripts/assess_change_impact.py --base HEAD`
- `python scripts/schema_compat_check.py --base HEAD --run-smoke`
- `./scripts/run_tests.sh -v -k <plugin_or_feature_keyword>`
- `scripts/check_doc_sync.sh`
- `python scripts/check_doc_anchors.py --check-sync --base HEAD`
<!-- END GENERATED: profile_summary_modify_plugin -->

## Recommended Substates
- `impact_assessed`
- `version_checked`
- `tests_selected`
- `docs_sync_required`

## Rework Policy
- 默认返工 owner：`executor.plugin`
- 仅当以下情况允许回到 `planning`：
  - `scope_changed=true`
  - 需要改 route
  - gate 结果要求重做任务分解

## Planner Template
```md
# plan_brief

- `task_id`:
- `route`: `modify_plugin`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `low|medium|high`
- `scope_in`:
- `scope_out`:
- `required_gates`:
  - `assess_change_impact`
  - `doc_sync`
  - `doc_anchors`
  -
- `executor_role`: `executor.plugin`
- `blocking_assumptions`:
  -

## modify_plugin Notes
- `change_level`: `L0|L1|L2|L3`
- `provides_impact`:
- `depends_on_impact`:
- `output_contract_impact`:
- `version_action`:
- `docs_sync_required`: `true|false`
- `execution_backend_decision`:
  - `backend`: `python|numpy|numba_serial|numba_parallel|thread_pool|process_pool`
  - `backend_reason`: `CPU-bound|memory-bound|IO-bound|GIL-released|startup-cost-sensitive`
  - `parallel_scope`: `none|file|channel|chunk|record`
  - `worker_option`:
  - `fallback_path`:
  - `benchmark_required`: `true|false`
- `must_run_commands`:
  - `python scripts/assess_change_impact.py --base HEAD`
  -
```

## Executor Template
```md
# execution_report

- `task_id`:
- `executor_role`: `executor.plugin`
- `changed_paths`:
  -
- `actions_taken`:
  -
- `commands_run`:
  -
- `open_risks`:
  -
- `requested_review_focus`:
  -

## modify_plugin Notes
- `tests_run`:
  -
- `gates_executed`:
  -
- `docs_updated`:
  -
- `version_changed`: `true|false`
- `contract_changed`: `true|false`
- `backend_implemented_as_planned`: `true|false`
- `backend_deviations`:
  -
- `not_executed_and_why`:
  -
```

## Reviewer Template
```md
# review_report

- `task_id`:
- `reviewer`: `reviewer`
- `gate_results`:
  -
- `decision`: `completed|rework_required|blocked|failed`
- `blocking_findings`:
  -
- `residual_risks`:
  -
- `follow_up_actions`:
  -

## Rework Control
- `scope_changed`: `true|false`
- `required_fixes`:
  -
- `gates_to_rerun`:
  -

## modify_plugin Review
- `version_review`:
- `contract_review`:
- `docs_review`:
- `performance_style_review`:
  - `single_parallel_layer`: `pass|fail|not_applicable`
  - `numba_parallel_evidence`: `pass|fail|not_applicable`
  - `worker_option_review`: `pass|fail|not_applicable`
  - `fallback_review`: `pass|fail|not_applicable`
- `completion_allowed`: `true|false`
```

## Typical Rework Reasons
- 契约变化但 `version` 未升级
- 字段或 dtype 变化但未执行 `schema_compat_check`
- 修改了用户可见行为但未同步 `plugins-agent` 或 `docs/agents`
- 插件算法改动缺少 `execution_backend_decision`
- 同一执行路径叠加多个并发层且缺少明确 benchmark 证据
- `execution_report` 缺少测试或 gate 结果

## Quick Fill Examples

### L1: 契约不变
- `change_level`: `L1`
- `risk_level`: `medium`
- `output_contract_impact`: `none`
- `version_action`: `patch recommended`
- `execution_backend_decision.backend`: `numba_serial`
- `performance_style_review.single_parallel_layer`: `pass`

### L2: 配置或字段变化
- `change_level`: `L2`
- `risk_level`: `high`
- `output_contract_impact`: `field or config semantic changed`
- `version_action`: `minor bump required`

### L3: 依赖链或 provides 变化
- `change_level`: `L3`
- `risk_level`: `high`
- `provides_impact`: `changed`
- `version_action`: `minor or major bump required`
