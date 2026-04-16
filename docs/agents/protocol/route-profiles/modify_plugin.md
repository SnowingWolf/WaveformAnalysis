# Route Profile: modify_plugin

<!-- BEGIN GENERATED: profile_summary_modify_plugin -->
## Use When
- 插件与契约改动

## Route
- `task`: `modify_plugin`
- `primary_doc`: `docs/agents/workflows.md`
- `profile_doc`: `docs/agents/protocol/route-profiles/modify_plugin.md`

## Blocking Gates
- `assess_change_impact`
- `schema_compat_check`
- `doc_sync`
- `doc_anchors`

## Canonical Commands
- `waveform-docs generate plugins-agent --plugin <provides>`
- `python scripts/assess_change_impact.py --base HEAD`
- `python scripts/schema_compat_check.py --base HEAD --run-smoke`
- `./scripts/run_tests.sh -v -k <plugin_or_feature_keyword>`
- `scripts/check_doc_sync.sh`
- `python scripts/check_doc_anchors.py --check-sync --base HEAD`
<!-- END GENERATED: profile_summary_modify_plugin -->

## Recommended Substates
- `impact_assessed`
- `version_checked`
- `tests_selected`
- `docs_sync_required`

## Rework Policy
- 默认返工 owner：`executor.plugin`
- 仅当以下情况允许回到 `planning`：
  - `scope_changed=true`
  - 需要改 route
  - gate 结果要求重做任务分解

## Planner Template
```md
# plan_brief

- `task_id`:
- `route`: `modify_plugin`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `low|medium|high`
- `scope_in`:
- `scope_out`:
- `required_gates`:
  - `assess_change_impact`
  - `doc_sync`
  - `doc_anchors`
  -
- `executor_role`: `executor.plugin`
- `blocking_assumptions`:
  -

## modify_plugin Notes
- `change_level`: `L0|L1|L2|L3`
- `provides_impact`:
- `depends_on_impact`:
- `output_contract_impact`:
- `version_action`:
- `docs_sync_required`: `true|false`
- `must_run_commands`:
  - `python scripts/assess_change_impact.py --base HEAD`
  -
```

## Executor Template
```md
# execution_report

- `task_id`:
- `executor_role`: `executor.plugin`
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

## modify_plugin Notes
- `tests_run`:
  -
- `gates_executed`:
  -
- `docs_updated`:
  -
- `version_changed`: `true|false`
- `contract_changed`: `true|false`
- `not_executed_and_why`:
  -
```

## Reviewer Template
```md
# review_report

- `task_id`:
- `reviewer`: `reviewer`
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

## modify_plugin Review
- `version_review`:
- `contract_review`:
- `docs_review`:
- `completion_allowed`: `true|false`
```

## Typical Rework Reasons
- 契约变化但 `version` 未升级
- 字段或 dtype 变化但未执行 `schema_compat_check`
- 修改了用户可见行为但未同步 `plugins-agent` 或 `docs/agents`
- `execution_report` 缺少测试或 gate 结果

## Quick Fill Examples

### L1: 契约不变
- `change_level`: `L1`
- `risk_level`: `medium`
- `output_contract_impact`: `none`
- `version_action`: `patch recommended`

### L2: 配置或字段变化
- `change_level`: `L2`
- `risk_level`: `high`
- `output_contract_impact`: `field or config semantic changed`
- `version_action`: `minor bump required`

### L3: 依赖链或 provides 变化
- `change_level`: `L3`
- `risk_level`: `high`
- `provides_impact`: `changed`
- `version_action`: `minor or major bump required`
