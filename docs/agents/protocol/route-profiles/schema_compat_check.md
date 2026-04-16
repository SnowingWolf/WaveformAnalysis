# Route Profile: schema_compat_check

<!-- BEGIN GENERATED: profile_summary_schema_compat_check -->
## Use When
- dtype、字段兼容与关键链路冒烟

## Route
- `task`: `schema_compat_check`
- `primary_doc`: `docs/agents/workflows.md`
- `profile_doc`: `docs/agents/protocol/route-profiles/schema_compat_check.md`

## Blocking Gates
- `schema_report_generated`
- `smoke_chain_passed`

## Canonical Commands
- `python scripts/schema_compat_check.py --base HEAD --run-smoke`
<!-- END GENERATED: profile_summary_schema_compat_check -->

## Recommended Substates
- `schema_diff_detected`
- `smoke_required`

## Rework Policy
- 默认返工 owner：`executor.qa`
- 仅当以下情况允许回到 `planning`：
  - `scope_changed=true`
  - 基线引用错误
  - 需要改 route 或调整检查范围

## Planner Template
```md
# plan_brief

- `task_id`:
- `route`: `schema_compat_check`
- `lifecycle_profile`: `qa_review`
- `risk_level`: `low|medium|high`
- `scope_in`:
- `scope_out`:
- `required_gates`:
  - `schema_report_generated`
  - `smoke_chain_passed`
- `executor_role`: `executor.qa`
- `blocking_assumptions`:
  -

## schema_compat_check Notes
- `change_scope`:
- `base_reference`:
- `smoke_chain_required`: `true|false`
- `must_run_commands`:
  - `python scripts/schema_compat_check.py --base HEAD --run-smoke`
- `expected_contract_focus`:
  -
```

## Executor Template
```md
# execution_report

- `task_id`:
- `executor_role`: `executor.qa`
- `changed_paths`:
  -
- `actions_taken`:
  -
- `commands_run`:
  - `python scripts/schema_compat_check.py --base HEAD --run-smoke`
- `open_risks`:
  -
- `requested_review_focus`:
  -

## schema_compat_check Notes
- `schema_diff_summary`:
  -
- `migration_notes`:
  -
- `smoke_chain_result`:
- `gates_executed`:
  - `schema_report_generated`
  - `smoke_chain_passed`
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
  - `schema_report_generated`
  - `smoke_chain_passed`

## schema_compat_check Review
- `schema_review`:
- `migration_review`:
- `smoke_review`:
- `completion_allowed`: `true|false`
```

## Typical Rework Reasons
- 发现字段或 dtype 变化，但迁移说明不完整
- 冒烟链路未跑通或结果未记录
- `execution_report` 未说明 diff 范围或基线引用
- schema 风险存在，但 `review_report` 未明确后续动作

## Quick Fill Examples

### 仅字段检查
- `risk_level`: `medium`
- `smoke_chain_required`: `false`
- `expected_contract_focus`: `dtype and field additions only`

### 字段变化 + 固定冒烟
- `risk_level`: `high`
- `smoke_chain_required`: `true`
- `expected_contract_focus`: `field rename, dtype change, downstream compatibility`
