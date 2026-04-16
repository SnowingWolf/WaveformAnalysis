# review_report Template

## When To Create
- 在 `reviewing` 阶段结束前创建。
- 进入 `completed`、`rework_required`、`blocked` 或 `failed` 前必须完成。

## Required Fields
- `task_id`
- `reviewer`
- `gate_results`
- `decision`
- `blocking_findings`
- `residual_risks`
- `follow_up_actions`

## Decision Values
- `completed`
- `rework_required`
- `blocked`
- `failed`

## Field Rules
- `decision`
  仅允许：`completed | rework_required | blocked | failed`
- `gate_results`
  使用平铺列表，每项包含 gate 名称和结果
- `blocking_findings`
  只记录会阻断完成态的问题
- `scope_changed`
  布尔值；仅当 `decision=rework_required` 时需要填写

## Copy-ready Template
```md
# review_report

- `task_id`:
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
- `completion_allowed`: `true|false`
```

## Completion Checklist
- `decision` 合法
- 若为 `rework_required`，已写明 `scope_changed`
- 若为 `completed`，阻断 gate 已全部通过
- 残余风险与后续动作已明确
