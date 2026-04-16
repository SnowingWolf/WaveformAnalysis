# Task Lifecycle Summary

统一主状态：
`created -> planning -> ready_for_execution -> executing -> reviewing -> completed`

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

阻断式审查：
- `Reviewer` 未明确放行前，任务不能进入 `completed`
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

## 决策值
- `risk_level`
  - `low`
  - `medium`
  - `high`
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
