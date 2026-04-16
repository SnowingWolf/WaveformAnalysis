# Route Profile: debug_cache

<!-- BEGIN GENERATED: profile_summary_debug_cache -->
## Use When
- 缓存、lineage 与执行链排障

## Route
- `task`: `debug_cache`
- `primary_doc`: `docs/agents/workflows.md`
- `profile_doc`: `docs/agents/protocol/route-profiles/debug_cache.md`

## Blocking Gates
- `diagnosis_reproduced`

## Canonical Commands
- `waveform-cache diagnose --run <run_id> --dry-run`
- `python scripts/check_doc_anchors.py --check-sync --base HEAD`
<!-- END GENERATED: profile_summary_debug_cache -->

## Rework Policy
- 默认返工 owner：`executor.config`
- 仅当以下情况允许回到 `planning`：
  - `scope_changed=true`
  - `run_id`、target 或复现路径定义错误
  - 需要改 route 或补充更高层诊断上下文

## Planner Template
```md
# plan_brief

- `task_id`:
- `route`: `debug_cache`
- `lifecycle_profile`: `diagnostic_review`
- `risk_level`: `low|medium|high`
- `scope_in`:
- `scope_out`:
- `required_gates`:
  - `diagnosis_reproduced`
- `executor_role`: `executor.config`
- `blocking_assumptions`:
  -

## debug_cache Notes
- `run_id`:
- `target`:
- `reproduction_path`:
- `must_run_commands`:
  - `waveform-cache diagnose --run <run_id> --dry-run`
- `expected_root_cause_area`:
  -
```

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
  - `waveform-cache diagnose --run <run_id> --dry-run`
- `open_risks`:
  -
- `requested_review_focus`:
  -

## debug_cache Notes
- `preview_result`:
- `diagnosis_summary`:
  -
- `probable_root_cause`:
- `next_corrective_action`:
- `not_executed_and_why`:
  -
```

## Reviewer Template
```md
# review_report

- `task_id`:
- `reviewer`: `reviewer`
- `gate_results`:
  - `diagnosis_reproduced: pass|fail`
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
  - `diagnosis_reproduced`

## debug_cache Review
- `reproduction_review`:
- `root_cause_review`:
- `completion_allowed`: `true|false`
```
