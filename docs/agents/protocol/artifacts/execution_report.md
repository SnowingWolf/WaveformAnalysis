# execution_report Template

## When To Create
- 在 `executing` 阶段结束前创建。
- 进入 `reviewing` 前必须完成。

## Required Fields
- `task_id`
- `workflow_cost`
- `executor_role`
- `agent_profile`（plan 选择专项参与者时）
- `changed_paths`
- `actions_taken`
- `commands_run`
- `open_risks`
- `requested_review_focus`

## Field Rules
- `workflow_cost`
  仅允许：`light | standard | strict`
- `changed_paths`
  使用仓库相对路径的平铺列表
- `commands_run`
  记录实际执行过的命令，不记录计划命令
- `open_risks`
  只记录尚未关闭的风险，不重复已解决项
- `agent_profile`
  必须与 `plan_brief` 一致；执行中更换 profile 需记录在 `plan_drift`

## Copy-ready Template
```md
# execution_report

- `task_id`:
- `workflow_cost`: `light|standard|strict`
- `executor_role`:
- `agent_profile`:
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

## Optional Notes
- `tests_run`:
  -
- `gates_executed`:
  -
- `docs_updated`:
  -
- `plan_drift`:
  -
- `not_executed_and_why`:
  -
```

## Completion Checklist
- `workflow_cost` 已明确，且不低于任务实际风险
- 变更路径已列出
- 实际运行命令已列出
- reviewer 需要重点看的点已列出
- 若选择 `agent_profile`，执行结果已回应 `profile_plan`，并请求对应专项审查
- 未完成项及原因已显式记录
