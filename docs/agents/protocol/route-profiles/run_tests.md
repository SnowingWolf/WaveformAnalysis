# Route Profile: run_tests

<!-- BEGIN GENERATED: profile_summary_run_tests -->
## Use When
- 定向或全量测试执行

## Route
- `task`: `run_tests`
- `primary_doc`: `AGENTS.md`
- `profile_doc`: `docs/agents/protocol/route-profiles/run_tests.md`

## Blocking Gates
- `requested_tests_complete`

## Canonical Commands
- `./scripts/run_tests.sh`
- `pytest -v`
<!-- END GENERATED: profile_summary_run_tests -->

## Rework Policy
- 默认返工 owner：`executor.qa`
- 仅当以下情况允许回到 `planning`：
  - `scope_changed=true`
  - 测试目标、关键字或环境选择错误
  - 需要改 route，转为兼容检查或发布前检查

## Planner Template
```md
# plan_brief

- `task_id`:
- `route`: `run_tests`
- `lifecycle_profile`: `qa_review`
- `risk_level`: `low|medium|high`
- `scope_in`:
- `scope_out`:
- `required_gates`:
  - `requested_tests_complete`
- `executor_role`: `executor.qa`
- `blocking_assumptions`:
  -

## run_tests Notes
- `test_target`:
- `keyword_or_path`:
- `env_assumption`:
- `must_run_commands`:
  - `./scripts/run_tests.sh`
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
  -
- `open_risks`:
  -
- `requested_review_focus`:
  -

## run_tests Notes
- `tests_selected`:
  -
- `tests_run`:
  -
- `test_results_summary`:
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
  - `requested_tests_complete: pass|fail`
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
  - `requested_tests_complete`

## run_tests Review
- `scope_review`:
- `result_review`:
- `completion_allowed`: `true|false`
```
