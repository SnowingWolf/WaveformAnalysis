# review_report Template

## When To Create
- 在 `reviewing` 阶段结束前创建。
- 进入 `completed`、`rework_required`、`blocked` 或 `failed` 前必须完成。

## Required Fields
- `task_id`
- `workflow_cost`
- `reviewer`
- `gate_results`
- `decision`
- `blocking_findings`
- `residual_risks`
- `follow_up_actions`
- `agent_profile`（使用专项参与者时）
- `agent_profile_review`（使用专项参与者时）

## Decision Values
- `completed`
- `rework_required`
- `blocked`
- `failed`

## Field Rules
- `workflow_cost`
  仅允许：`light | standard | strict`，必须与最终执行口径一致
- `decision`
  仅允许：`completed | rework_required | blocked | failed`
- `gate_results`
  使用平铺列表，每项包含 gate 名称和结果
- `blocking_findings`
  只记录会阻断完成态的问题
- `scope_changed`
  布尔值；仅当 `decision=rework_required` 时需要填写
- `agent_profile_review`
  核对 `profile_plan`、执行结果与 route/role 绑定，并覆盖 profile 在 reviewing 阶段声明的 `required_focus`
- `agent_profile`
  必须与 `plan_brief`、`execution_report` 使用同一个 profile id

## Copy-ready Template
```md
# review_report

- `task_id`:
- `workflow_cost`: `light|standard|strict`
- `reviewer`:
- `gate_results`:
  -
- `decision`: `completed|rework_required|blocked|failed`
- `blocking_findings`:
  -
- `residual_risks`:
  -
- `follow_up_actions`:
  -
- `agent_profile`:
- `agent_profile_review`:

## Rework Control
- `scope_changed`: `true|false`
- `required_fixes`:
  -
- `gates_to_rerun`:
  -

## Optional Notes
- `version_review`:
- `contract_review`:
- `docs_review`:
- `performance_style_review`:
  - `single_parallel_layer`: `pass|fail|not_applicable`
  - `numba_parallel_evidence`: `pass|fail|not_applicable`
  - `worker_option_review`: `pass|fail|not_applicable`
  - `fallback_review`: `pass|fail|not_applicable`
- `completion_allowed`: `true|false`
```

## Completion Checklist
- `workflow_cost` 已明确，且与 gate 结果口径一致
- `decision` 合法
- 若为 `rework_required`，已写明 `scope_changed`
- 若为 `completed`，阻断 gate 已全部通过
- 插件算法改动已审查执行后端与并发层级
- 若使用 `agent_profile`，规划贡献、执行绑定与专项必审项已覆盖
- 残余风险与后续动作已明确
