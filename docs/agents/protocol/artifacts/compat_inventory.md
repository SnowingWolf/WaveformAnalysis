# compat_inventory Template

## When To Create
- 仅用于 `retire_compat` route。
- 在 `planning` 阶段完成，并先于 `plan_brief` 锁定删除范围。
- 进入 `ready_for_execution` 前必须完成。

## Required Fields
- `task_id`
- `route`
- `inventory_scope`
- `canonical_policy`
- `compat_items`

## Item Required Fields
- `compat_id`
- `kind`
- `canonical_form`
- `legacy_form`
- `location`
- `runtime_surface`
- `delete_action`
- `risk_level`
- `required_gates`
- `migration_note`
- `review_decision`

## Field Rules
- `route`
  固定为 `retire_compat`
- `canonical_policy`
  明确“入口允许兼容，内部只认规范形态”的收敛规则
- `compat_items`
  使用平铺列表；每个条目只描述一个兼容面
- `kind`
  仅允许：`config_alias | deprecated_option | import_alias | route_alias | legacy_data_shape | fallback_path | docs_redirect | other`
- `runtime_surface`
  仅允许：`public_cli | public_python_api | config | plugin_contract | docs_only | internal`
- `delete_action`
  仅允许：`remove | keep | migrate_to_central_compat | defer`
- `risk_level`
  仅允许：`low | medium | high`
- `review_decision`
  仅允许：`approved | needs_confirmation | blocked | deferred`
- 中高风险条目若触及 `public_cli`、`public_python_api`、`plugin_contract`，必须在 `migration_note` 中写明迁移或确认要求

## Copy-ready Template
```md
# compat_inventory

- `task_id`:
- `route`: `retire_compat`
- `inventory_scope`:
- `canonical_policy`: `entry-only compat; internal code uses canonical form only`

## compat_items
- `compat_id`:
  - `kind`: `config_alias|deprecated_option|import_alias|route_alias|legacy_data_shape|fallback_path|docs_redirect|other`
  - `canonical_form`:
  - `legacy_form`:
  - `location`:
  - `runtime_surface`: `public_cli|public_python_api|config|plugin_contract|docs_only|internal`
  - `delete_action`: `remove|keep|migrate_to_central_compat|defer`
  - `risk_level`: `low|medium|high`
  - `required_gates`:
    -
  - `migration_note`:
  - `review_decision`: `approved|needs_confirmation|blocked|deferred`
```

## Completion Checklist
- 每个兼容项都已对应到单一规范形态
- 每个待删除项都已标注风险等级和必跑 gate
- 中高风险项已明确迁移说明或确认要求
- 不存在未归类、未决策的兼容项
