# Task Lifecycle Summary

活动任务的唯一记录是
`docs/agents/runs/current/<task-id>/task.yaml`；本页只提供兼容摘要。状态、迁移条件和 route 默认值从 `docs/agents/index.yaml` 读取，字段由 `docs/agents/schema/agent-task.schema.json` 校验。

## Shape 与迁移

- `staged`：`created -> planning -> ready_for_execution -> executing -> reviewing -> completed`，必须保留 Planner、Executor、Reviewer 边界。
- `compact`：轻量低风险任务可使用内联检查；完成前仍须在 `task.yaml.status.execution` 记录验证结果。
- `direct`：仅只读简单任务，可直接在最终交接中报告验证结果，不创建仓库任务记录。
- `awaiting_user_input`、`awaiting_approval`、`blocked`、`rework_required`、`failed`、`cancelled` 是正式状态，不能用普通进度文字替代。
- 默认返工为 `reviewing -> rework_required -> executing`；只有 `scope_changed=true` 才能回到 `planning`。

## Task record 对照

`task.yaml` 的 `spec` 保存 `goal`、`route`、`workflow_cost`、`workflow_shape`、`risk_level`、`scope`、`acceptance_criteria`、`required_gates` 和 `assignment`；`status` 保存当前 state、transition history、`plan_sha256`、execution/review/approval/handoff 证据。

scope 或验收条件发生变化时，必须递增 `metadata.generation`，重新进入 `planning`，并清除旧的执行、审查与批准结论。审批只能绑定当前 spec digest；CLI 不替 agent 执行 gate，也不替用户批准。

## Deprecated artifacts

旧的 `plan_brief`、`compat_inventory`、`execution_report`、`review_report` 和 `task_report` 路径只作兼容链接，不能作为活动状态。历史副本位于 `docs/agents/runs/archive/legacy/`，由 manifest 校验后只读保存。

## 决策与证据

- `workflow_cost` 只能是 `light`、`standard` 或 `strict`；route 默认值与允许 shape 由 manifest 生成。
- `risk_level` 只能是 `low`、`medium` 或 `high`。
- `workflow_shape` 只能是 `direct`、`compact` 或 `staged`。
- 阻断 gate 的结果、未执行原因、review decision 和后续动作必须写入 `task.yaml.status`，不能只写在聊天消息中。
