# Route Profile: performance_regression_check

<!-- BEGIN GENERATED: profile_summary_performance_regression_check -->
## Use When
- 热点插件性能回归检查

## Route
- `task`: `performance_regression_check`
- `primary_doc`: `docs/agents/workflows.md`
- `profile_doc`: `docs/agents/protocol/route-profiles/performance_regression_check.md`

## Blocking Gates
- `performance_report_generated`

## Canonical Commands
- `python scripts/performance_regression_check.py --base HEAD`
<!-- END GENERATED: profile_summary_performance_regression_check -->

## Rework Policy
- 默认返工 owner：`executor.qa`
- 仅当以下情况允许回到 `planning`：
  - `scope_changed=true`
  - baseline 或阈值选择错误
  - 需要改 route，转为 release 聚合检查

## Planner Template
```md
# plan_brief

- `task_id`:
- `route`: `performance_regression_check`
- `lifecycle_profile`: `qa_review`
- `risk_level`: `low|medium|high`
- `scope_in`:
- `scope_out`:
- `required_gates`:
  - `performance_report_generated`
- `executor_role`: `executor.qa`
- `blocking_assumptions`:
  -

## performance_regression_check Notes
- `baseline_reference`:
- `benchmark_scope`:
- `threshold_policy`:
- `must_run_commands`:
  - `python scripts/performance_regression_check.py --base HEAD`
- `expected_hot_plugins`:
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
  - `python scripts/performance_regression_check.py --base HEAD`
- `open_risks`:
  -
- `requested_review_focus`:
  -

## performance_regression_check Notes
- `benchmark_targets`:
  -
- `threshold_decision`:
- `regression_summary`:
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
  - `performance_report_generated: pass|fail`
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
  - `performance_report_generated`

## performance_regression_check Review
- `baseline_review`:
- `metric_review`:
- `completion_allowed`: `true|false`
```
