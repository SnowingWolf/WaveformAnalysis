# Route Profile: modify_code

<!-- BEGIN GENERATED: profile_summary_modify_code -->
## Use When
- 普通核心、accessor、visualization 与 refactor 代码改动

## Route
- `task`: `modify_code`
- `workflow_cost`: `standard`
- `primary_doc`: `docs/agents/workflows.md`
- `profile_doc`: `docs/agents/protocol/route-profiles/modify_code.md`
- `executor_role`: `executor.code`
- `aliases`: `modify_context`, `refactor`

## Blocking Gates
- `assess_change_impact`
- `schema_compat_check`
- `doc_sync`
- `doc_anchors`

## Gate Trigger Policy
- ordinary internal code changes use standard staged workflow with targeted tests
- public surface, dtype/field, dependency, cache-lineage, or compatibility changes escalate to strict workflow
- docs coupled to a code contract change inherit the source route cost

## Canonical Commands
- `python scripts/assess_change_impact.py --base HEAD`
- `python scripts/schema_compat_check.py --base HEAD --run-smoke`
- `./scripts/run_tests.sh -v -k <component_or_feature_keyword>`
- `scripts/check_doc_sync.sh`
- `python scripts/check_doc_anchors.py --check-sync --base HEAD`
<!-- END GENERATED: profile_summary_modify_code -->

> This is the canonical profile for ordinary core, accessor, visualization,
> and refactor code changes. Its executor role is `executor.code`; it is a
> separate profile from `modify_plugin.md`, which remains responsible for
> plugin behavior and plugin-contract changes.

## Recommended Substates

- `impact_assessed`
- `scope_checked`
- `tests_selected`
- `docs_sync_required`

## Workflow Shape

- Ordinary internal code changes use `staged` with `Planner -> Executor -> Reviewer`.
- Public surface, dtype/field, dependency, cache-lineage, compatibility, release,
  approval, destructive, scope, or gate-failure triggers require `strict`/`staged`
  handling according to the manifest contract.

## Rework Policy

- Default executor role: `executor.code`.
- Reviewer findings return to `rework_required`; unchanged scope returns to
  `executing`, while changed scope returns to `planning` and increments generation.

## Planner Template

```md
# plan_brief

- `task_id`:
- `route`: `modify_code`
- `workflow_cost`: `standard|strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `low|medium|high`
- `scope_in`:
  -
- `scope_out`:
  -
- `required_gates`:
  - `assess_change_impact`
  - `schema_compat_check`
  - `doc_sync`
  - `doc_anchors`
- `executor_role`: `executor.code`
- `agent_profile`: `graph_engineer|none`
- `profile_plan`:
  -
- `blocking_assumptions`:
  -
```

## Executor Template

```md
# execution_report

- `task_id`:
- `executor_role`: `executor.code`
- `agent_profile`: `graph_engineer|none`
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
- `agent_profile`: `graph_engineer|none`
- `agent_profile_review`:

## Rework Control

- `scope_changed`: `true|false`
- `required_fixes`:
  -
- `gates_to_rerun`:
  -
```

## modify_code Review

- Confirm the actual changed paths remain inside `task.yaml.spec.scope.allowed_paths`.
- Run the route's impact, schema, documentation, and anchor gates; contract or
  cache-lineage changes must use strict handling.
- If public behavior, fields, dtype, or compatibility semantics change, record
  the compatibility decision and documentation impact before reviewer approval.
- `executor.code` implements the scoped change; only `reviewer` may approve the
  terminal state.
