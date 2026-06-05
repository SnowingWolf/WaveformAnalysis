# Agent Plan Registry

This directory is the shared plan registry for human users and AI agents.

When starting a new task, read this file first, then read `active.yaml`, then open the relevant plan file under `current/`.

This registry does not replace task-level artifacts such as `plan_brief`, `execution_report`, or `review_report`. It only indexes active plans and records cross-session status.

---

## Current Active Plan

| task_id | status | route | owner_role | plan | next_action | updated_at |
|---|---|---|---|---|---|---|
| get-data-output-unification | doing | modify_context | executor | [current/get-data-output-unification.md](current/get-data-output-unification.md) | Unify ctx.get_data output behavior | 2026-06-05 |

---

## Todo

| task_id | route | owner_role | plan | next_action |
|---|---|---|---|---|
| hit-threshold-ragged-optimization | modify_plugin | executor | [current/hit-threshold-ragged-optimization.md](current/hit-threshold-ragged-optimization.md) | Optimize records ragged waveform access |
| hit-merged-peaklet-responsibility | refactor | planner | [current/hit-merged-peaklet-responsibility.md](current/hit-merged-peaklet-responsibility.md) | Clarify plugin responsibility boundaries |

---

## Blocked

| task_id | reason | required_decision | plan |
|---|---|---|---|

---

## Done

| task_id | completed_at | summary | archive |
|---|---|---|---|

---

## Cancelled

| task_id | cancelled_at | reason | archive |
|---|---|---|---|

---

## Operating Rules

1. Read this file before starting an Agent task.
2. Read `active.yaml` to identify machine-readable active plans.
3. Work on only one plan at a time.
4. Do not modify unrelated code while executing a plan.
5. After finishing a task, update:
   - the plan file
   - `INDEX.md`
   - `active.yaml`
6. Move completed or cancelled plans from `current/` to `archive/`.
7. Keep `INDEX.md` short. Detailed reasoning belongs in individual plan files.
