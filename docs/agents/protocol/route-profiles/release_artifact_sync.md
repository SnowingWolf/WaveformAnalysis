# Route Profile: release_artifact_sync

<!-- BEGIN GENERATED: profile_summary_release_artifact_sync -->
## Use When
- 发布前版本、文档与检查结果统一校验

## Route
- `task`: `release_artifact_sync`
- `primary_doc`: `docs/agents/workflows.md`
- `profile_doc`: `docs/agents/protocol/route-profiles/release_artifact_sync.md`
- `aliases`: `release_check`

## Blocking Gates
- `release_artifacts_consistent`

## Canonical Commands
- `python scripts/release_artifact_sync.py --base HEAD`
<!-- END GENERATED: profile_summary_release_artifact_sync -->

## Recommended Substates
- `release_inputs_resolved`

## Rework Policy
- 默认返工 owner：`executor.qa`
- 仅当以下情况允许回到 `planning`：
  - `scope_changed=true`
  - 发布目标或基线引用错误
  - 聚合检查范围定义错误

## Planner Template
```md
# plan_brief

- `task_id`:
- `route`: `release_artifact_sync`
- `lifecycle_profile`: `release_review`
- `risk_level`: `low|medium|high`
- `scope_in`:
- `scope_out`:
- `required_gates`:
  - `release_artifacts_consistent`
- `executor_role`: `executor.qa`
- `blocking_assumptions`:
  -

## release_artifact_sync Notes
- `release_target_or_base_reference`:
- `release_scope`:
- `expected_release_artifacts`:
  - `version/changelog`
  - `generated docs sync`
  - `doc sync + anchors`
  - `key tests`
  - `perf regression`
- `skip_tests`: `true|false`
- `skip_perf`: `true|false`
- `must_run_commands`:
  - `python scripts/release_artifact_sync.py --base HEAD`
- `review_focus`:
  -
```

## Executor Template
```md
# execution_report

- `task_id`:
- `executor_role`: `executor.qa`
- `changed_paths`:
  -
- `actions_taken`:
  -
- `commands_run`:
  - `python scripts/release_artifact_sync.py --base HEAD`
- `open_risks`:
  -
- `requested_review_focus`:
  -

## release_artifact_sync Notes
- `version_changelog_status`: `pass|fail|skipped`
- `generated_docs_sync_status`: `pass|fail|skipped`
- `doc_sync_anchors_status`: `pass|fail|skipped`
- `key_tests_status`: `pass|fail|skipped`
- `perf_regression_status`: `pass|fail|skipped`
- `skipped_checks_and_why`:
  -
- `release_sync_summary`:
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
  - `release_artifacts_consistent: pass|fail`
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
  - `release_artifacts_consistent`

## release_artifact_sync Review
- `release_consistency_review`:
- `skip_policy_review`:
- `artifact_review`:
- `completion_allowed`: `true|false`
```

## Typical Rework Reasons
- 版本或 `CHANGELOG` 状态不一致
- 生成文档与仓库文档不一致
- `doc_sync` 或 `doc_anchors` 未通过
- 关键测试或性能回归被跳过，但未说明理由
- `review_report` 未明确记录聚合检查结果

## Quick Fill Examples

### 标准发布前检查
- `risk_level`: `high`
- `skip_tests`: `false`
- `skip_perf`: `false`
- `expected_release_artifacts`: `full release gate set`

### 跳过性能检查的紧急发布核对
- `risk_level`: `high`
- `skip_tests`: `false`
- `skip_perf`: `true`
- `skipped_checks_and_why`: `perf baseline unavailable for emergency validation`
