# plan_brief Template

## When To Create
- 在 `planning` 阶段结束前创建。
- 进入 `ready_for_execution` 前必须完成。

## Required Fields
- `task_id`
- `route`
- `lifecycle_profile`
- `risk_level`
- `scope_in`
- `scope_out`
- `required_gates`
- `executor_role`
- `blocking_assumptions`

## Field Rules
- `risk_level`
  仅允许：`low | medium | high`
- `required_gates`
  使用平铺列表，不写嵌套结构
- `blocking_assumptions`
  只记录会阻止进入 `executing` 的前提，不写一般性备注

## Copy-ready Template
```md
# plan_brief

- `task_id`:
- `route`:
- `lifecycle_profile`:
- `risk_level`: `low|medium|high`
- `scope_in`:
- `scope_out`:
- `required_gates`:
  -
- `executor_role`:
- `blocking_assumptions`:
  -

## Optional Notes
- `change_level`:
- `must_run_commands`:
  -
- `needs_user_input`:
  -
- `needs_approval`:
  -
```

## Completion Checklist
- `route` 与 route profile 一致
- `required_gates` 已明确
- `executor_role` 已明确
- 没有缺失会阻止执行的前提
