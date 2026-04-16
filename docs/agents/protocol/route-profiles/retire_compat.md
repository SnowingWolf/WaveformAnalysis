# Route Profile: retire_compat

<!-- BEGIN GENERATED: profile_summary_retire_compat -->
## Use When
- 兼容冗余识别、分级与删除

## Route
- `task`: `retire_compat`
- `primary_doc`: `docs/agents/workflows.md`
- `profile_doc`: `docs/agents/protocol/route-profiles/retire_compat.md`

## Blocking Gates
- `compat_inventory_ready`
- `deletion_scope_confirmed`
- `doc_sync`
- `doc_anchors`
- `impact_assessed_if_needed`
- `schema_checked_if_needed`

## Canonical Commands
- `scripts/check_doc_sync.sh`
- `python scripts/check_doc_anchors.py --check-sync --base HEAD`
- `python scripts/assess_change_impact.py --base HEAD`
- `python scripts/schema_compat_check.py --base HEAD --run-smoke`
- `waveform-docs generate plugins-agent -o docs/plugins/reference/agent/`
<!-- END GENERATED: profile_summary_retire_compat -->

## Recommended Substates
- `inventory_built`
- `risk_banded`
- `deletion_scope_confirmed`
- `gates_selected`

## Deletion Policy
- 默认策略：平衡删除。
- 仅允许入口兼容层保留双写/别名；内部实现必须收敛到规范形态。
- `low` 风险项可直接进入删除计划。
- `medium` 风险项必须写明迁移说明，并在需要时进入 `awaiting_user_input`。
- `high` 风险项不得直接作为普通冗余清理删除，必须转为 `modify_plugin` 或独立迁移任务。

## Risk Bands
- `low`
  - 内部 fallback
  - 重复文档跳转
  - 未被公开入口引用的 compat helper
- `medium`
  - 配置别名
  - deprecated option
  - import path alias
- `high`
  - `provides`
  - `depends_on`
  - `output_dtype`
  - 正式数据字段
  - 公开 CLI 参数
  - cache lineage / 正式数据契约

## Rework Policy
- 默认返工 owner：`executor.config`
- 仅当以下情况允许回到 `planning`：
  - `scope_changed=true`
  - `compat_inventory` 分类错误
  - 删除范围涉及新的 public surface 或插件契约
  - 需要把高风险删除拆分为 `modify_plugin`

## Planner Template
```md
# plan_brief

- `task_id`:
- `route`: `retire_compat`
- `lifecycle_profile`: `compat_retirement_review`
- `risk_level`: `low|medium|high`
- `scope_in`:
- `scope_out`:
- `required_gates`:
  - `compat_inventory_ready`
  - `deletion_scope_confirmed`
  - `doc_sync`
  - `doc_anchors`
  -
- `executor_role`: `executor.config`
- `blocking_assumptions`:
  -

## retire_compat Notes
- `compat_inventory_required`: `true`
- `executor_role_override`: `executor.config|executor.plugin|executor.docs`
- `deletion_policy`: `balanced`
- `must_run_commands`:
  - `scripts/check_doc_sync.sh`
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
  -
- `public_surface_confirmation_required`: `true|false`
- `high_risk_items_redirected`: `true|false`
```

## Planner Requirements
- 先填写 `artifacts/compat_inventory.md`，再生成 `plan_brief`。
- 若存在 `medium/high` 风险且触及 `public_cli`、`public_python_api`、`plugin_contract`，必须进入 `awaiting_user_input` 后才能进入 `ready_for_execution`。
- `compat_inventory` 中标为 `defer` 或 `blocked` 的项不得进入本轮删除范围。

## Executor Template
```md
# execution_report

- `task_id`:
- `executor_role`: `executor.config`
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

## retire_compat Notes
- `compat_items_removed`:
  -
- `compat_items_kept`:
  -
- `migration_updates`:
  -
- `gates_executed`:
  - `doc_sync`
  - `doc_anchors`
  -
- `not_executed_and_why`:
  -
```

## Reviewer Template
```md
# review_report

- `task_id`:
- `reviewer`: `reviewer`
- `gate_results`:
  - `compat_inventory_ready: pass|fail`
  - `deletion_scope_confirmed: pass|fail`
  - `doc_sync: pass|fail`
  - `doc_anchors: pass|fail`
  - `impact_assessed_if_needed: pass|fail|skipped`
  - `schema_checked_if_needed: pass|fail|skipped`
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
  - `compat_inventory_ready`
  - `deletion_scope_confirmed`
  - `doc_sync`
  - `doc_anchors`
  -

## retire_compat Review
- `inventory_review`:
- `risk_band_review`:
- `migration_review`:
- `completion_allowed`: `true|false`
```

## Must Reject
- 缺少 `compat_inventory`
- 删除项没有 `canonical_form` / `legacy_form`
- 中高风险项被按低风险删除
- 触及插件契约却未执行 `assess_change_impact`
- 触及字段、dtype、配置语义却未执行 `schema_compat_check`
- 删除用户可见兼容入口但文档未同步

## Quick Fill Examples

### 低风险内部 fallback 删除
- `risk_level`: `low`
- `executor_role_override`: `executor.config`
- `public_surface_confirmation_required`: `false`

### 配置别名收敛
- `risk_level`: `medium`
- `executor_role_override`: `executor.config`
- `public_surface_confirmation_required`: `true`
- `must_run_commands`: `doc sync + schema_compat_check if config semantics change`

### 发现契约级兼容债
- `risk_level`: `high`
- `high_risk_items_redirected`: `true`
- `follow_up_actions`: `split into modify_plugin or dedicated migration task`
