# Task Lifecycle Summary

`staged` 主状态：
`created -> planning -> ready_for_execution -> executing -> reviewing -> completed`

快速路径：
- `direct`: `created -> completed`，仅只读任务，最终回复记录验证结果
- `compact`: `created -> executing -> completed`，完成前必须产出 `task_report`

可选分支：
- `planning -> awaiting_user_input`
- `planning -> awaiting_approval`
- `executing -> blocked | failed`
- `reviewing -> rework_required | blocked | failed`

返工规则：
- 默认：`rework_required -> executing`
- 仅在 `scope_changed=true` 时允许：`rework_required -> planning`

强制要求：
- `planning -> ready_for_execution` 前必须有 `plan_brief`
- `retire_compat` 在 `planning` 阶段还必须先有 `compat_inventory`
- `executing -> reviewing` 前必须有 `execution_report`
- `reviewing -> completed` 前必须有 `review_report`
- `plan_brief`、`execution_report`、`review_report` 都必须记录 `workflow_cost`
- `compact` 的 `task_report` 必须记录 `workflow_cost=light` 和 `workflow_shape=compact`
- 命中 public surface、插件契约、dtype/字段、cache lineage、compat、release、审批、破坏性动作、scope 扩大或 gate 失败时必须升级到 `staged`

阻断式审查：
- `staged` 未经 `Reviewer` 明确放行不能进入 `completed`
- `direct`/`compact` 使用内联验证，但不能绕过升级条件
- 审查发现可修复问题时必须进入 `rework_required`

## Artifact 对照
- `planning -> planning`（仅 `retire_compat`）
  必须先产出 `compat_inventory`
- `planning -> ready_for_execution`
  必须存在 `plan_brief`
- `executing -> reviewing`
  必须存在 `execution_report`
- `reviewing -> completed`
  必须存在 `review_report`
- `executing -> completed`（仅 `compact`）
  必须存在 `task_report`

## 决策值
- `workflow_cost`
  - `light`
  - `standard`
  - `strict`
- `risk_level`
  - `low`
  - `medium`
  - `high`
- `workflow_shape`
  - `direct`
  - `compact`
  - `staged`
- `review_report.decision`
  - `completed`
  - `rework_required`
  - `blocked`
  - `failed`

## 返工差异
- `rework_required -> executing`
  用于范围不变，只需修正实现、补 gate、补文档、补测试。
- `rework_required -> planning`
  仅在 `scope_changed=true` 时使用，表示任务范围、route 或 gate 选择需要重做。
