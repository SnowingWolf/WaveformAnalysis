# Route Profile: assess_change_impact

<!-- BEGIN GENERATED: profile_summary_assess_change_impact -->
## Use When
- 改动影响面扫描与 version 风险检查

## Route
- `task`: `assess_change_impact`
- `primary_doc`: `docs/agents/workflows.md`
- `profile_doc`: `docs/agents/protocol/route-profiles/assess_change_impact.md`

## Blocking Gates
- `impact_report_generated`

## Canonical Commands
- `python scripts/assess_change_impact.py --base HEAD`
<!-- END GENERATED: profile_summary_assess_change_impact -->

## Recommended Substates
- `impact_diff_collected`

## Rework Policy
- 默认返工 owner：`executor.qa`
- 仅当以下情况允许回到 `planning`：
  - `scope_changed=true`
  - 基线引用错误
  - 影响面分析范围定义错误

## Planner Template
```md
# plan_brief

- `task_id`:
- `route`: `assess_change_impact`
- `lifecycle_profile`: `qa_review`
- `risk_level`: `low|medium|high`
- `scope_in`:
- `scope_out`:
- `required_gates`:
  - `impact_report_generated`
- `executor_role`: `executor.qa`
- `blocking_assumptions`:
  -

## assess_change_impact Notes
- `change_scope`:
- `base_reference`:
- `expected_risk_focus`:
  - `provides`
  - `depends_on`
  - `output_dtype`
  - `version`
- `must_run_commands`:
  - `python scripts/assess_change_impact.py --base HEAD`
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
  - `python scripts/assess_change_impact.py --base HEAD`
- `open_risks`:
  -
- `requested_review_focus`:
  -

## assess_change_impact Notes
- `changed_plugins`:
  -
- `downstream_impacts`:
  -
- `version_risks`:
  -
- `contract_risks`:
  -
- `impact_report_summary`:
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
  - `impact_report_generated: pass|fail`
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
  - `impact_report_generated`

## assess_change_impact Review
- `impact_coverage_review`:
- `downstream_review`:
- `version_review`:
- `completion_allowed`: `true|false`
```

## Typical Rework Reasons
- 未覆盖关键契约字段变化
- 列出了改动插件，但未列出下游受影响插件
- 发现 `output_dtype` 或依赖变化，但未指出 `version` 风险
- `execution_report` 缺少基线引用或影响摘要

## Quick Fill Examples

### 低风险内部改动
- `risk_level`: `low`
- `expected_risk_focus`: `internal algorithm only`
- `version_risks`: `none obvious`

### 契约相关改动
- `risk_level`: `high`
- `expected_risk_focus`: `depends_on, output_dtype, version`
- `downstream_impacts`: `multiple dependent plugins affected`
