# Route Profile Template

## Route
- `task`
- `lifecycle_profile`
- `handoff_sequence`

## Use When
- 说明该 route 适用的任务类型

## Substates
- route 子状态列表

## Blocking Gates
- 进入 `completed` 前必须通过的 gate 列表

## Rework Policy
- 默认返工 owner
- 何时允许回到 `planning`

## Planner Template
```md
# plan_brief
- `task_id`:
- `route`:
- `lifecycle_profile`:
- `risk_level`:
- `scope_in`:
- `scope_out`:
- `required_gates`:
  -
- `executor_role`:
- `blocking_assumptions`:
  -
```

## Executor Template
```md
# execution_report
- `task_id`:
- `executor_role`:
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
```

## Reviewer Template
```md
# review_report
- `task_id`:
- `reviewer`:
- `gate_results`:
  -
- `decision`:
- `blocking_findings`:
  -
- `residual_risks`:
  -
- `follow_up_actions`:
  -
- `scope_changed`:
- `required_fixes`:
  -
```
