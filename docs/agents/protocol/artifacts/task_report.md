# task_report Template

## When To Create
- 仅在 `workflow_shape=compact` 时创建。
- 从 `executing` 进入 `completed` 前完成；同一 agent 可以内联计划、执行与复核，但必须显式记录检查结果。

## Required Fields
- `task_id`
- `route`
- `workflow_cost`
- `workflow_shape`
- `scope`
- `actions_taken`
- `changed_paths`
- `verification`
- `decision`
- `commit_status`
- `open_risks`
- `agent_profile`（选择专项参与者时）
- `profile_plan`（选择专项参与者时）
- `agent_profile_review`（选择专项参与者时）

## Field Rules
- `workflow_cost` 必须为 `light`，`workflow_shape` 必须为 `compact`。
- mutation 仅限低风险、局部、可回滚的 scoped write。
- `verification` 记录实际执行的检查及 PASS/FAIL，不记录计划命令。
- `decision` 仅允许 `completed | escalate_to_staged | blocked | failed`。
- 命中任一升级条件或 gate 失败时，必须使用 `escalate_to_staged`，不得在 compact 内继续扩大范围。
- `commit_status` 必须写 `committed: <hash>` 或 `uncommitted: <reason>`。

## Copy-ready Template
```md
# task_report

- `task_id`:
- `route`:
- `workflow_cost`: `light`
- `workflow_shape`: `compact`
- `scope`:
- `actions_taken`:
  -
- `changed_paths`:
  -
- `verification`:
  -
- `decision`: `completed|escalate_to_staged|blocked|failed`
- `commit_status`:
- `open_risks`:
  -
- `agent_profile`:
- `profile_plan`:
  -
- `agent_profile_review`:
  -
```

## Completion Checklist
- 任务仍满足低风险、局部、可回滚边界。
- 实际变更和验证结果均已记录。
- 未命中任何强制升级条件。
- 提交状态已明确。
- 若使用 `agent_profile`，专项计划、执行结果和专项复核均已在本报告内闭环。
