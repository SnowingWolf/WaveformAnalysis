# Route Profile: generate_docs

<!-- BEGIN GENERATED: profile_summary_generate_docs -->
## Use When
- 文档生成、引用同步与锚点检查

## Route
- `task`: `generate_docs`
- `primary_doc`: `docs/agents/references.md`
- `profile_doc`: `docs/agents/protocol/route-profiles/generate_docs.md`

## Blocking Gates
- `doc_sync`
- `doc_anchors`

## Canonical Commands
- `waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/`
- `waveform-docs generate plugins-agent -o docs/plugins/reference/agent/`
- `scripts/check_doc_sync.sh`
- `python scripts/check_doc_anchors.py --check-sync --base HEAD`
<!-- END GENERATED: profile_summary_generate_docs -->

## Recommended Substates
- `doc_targets_resolved`
- `sync_checks_pending`

## Rework Policy
- 默认返工 owner：`executor.docs`
- 仅当以下情况允许回到 `planning`：
  - `scope_changed=true`
  - 文档目标范围判断错误
  - 需要重新决定是生成文档还是手写更新

## Planner Template
```md
# plan_brief

- `task_id`:
- `route`: `generate_docs`
- `lifecycle_profile`: `doc_only_reviewed`
- `risk_level`: `low|medium|high`
- `scope_in`:
- `scope_out`:
- `required_gates`:
  - `doc_sync`
  - `doc_anchors`
- `executor_role`: `executor.docs`
- `blocking_assumptions`:
  -

## generate_docs Notes
- `doc_target_scope`:
- `source_change_summary`:
- `generation_mode`: `plugins-auto|plugins-agent|mixed|manual`
- `must_run_commands`:
  - `scripts/check_doc_sync.sh`
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
- `docs_expected_to_change`:
  -
```

## Executor Template
```md
# execution_report

- `task_id`:
- `executor_role`: `executor.docs`
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

## generate_docs Notes
- `docs_generated`:
  -
- `docs_updated_manually`:
  -
- `gates_executed`:
  - `doc_sync`
  - `doc_anchors`
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
  - `doc_sync`
  - `doc_anchors`

## generate_docs Review
- `coverage_review`:
- `anchor_review`:
- `completion_allowed`: `true|false`
```

## Typical Rework Reasons
- 文档生成后未覆盖实际改动范围
- 仅更新了生成产物，未补充必要的说明文档
- `doc_sync` 或 `doc_anchors` 未通过
- `execution_report` 未明确哪些文档是自动生成、哪些是手工修改

## Quick Fill Examples

### 插件文档刷新
- `generation_mode`: `plugins-agent`
- `risk_level`: `low`
- `docs_expected_to_change`: `docs/plugins/reference/agent/**`

### 混合更新
- `generation_mode`: `mixed`
- `risk_level`: `medium`
- `source_change_summary`: `generated reference + hand-written guide updates`
