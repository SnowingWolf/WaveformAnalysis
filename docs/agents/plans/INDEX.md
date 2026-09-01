# Agent Plan Registry (compatibility view)

Active task state is owned by the v6 records under
`docs/agents/runs/current/<task-id>/task.yaml`. This file is generated for old
links and readers; edit the task record and rerun
`python scripts/render_agent_docs.py --write` instead of editing this view.

<!-- BEGIN GENERATED: current_task_registry -->
| task_id | state | route | cost | shape | condition | record |
| --- | --- | --- | --- | --- | --- | --- |
| `get-data-output-unification` | `planning` | `modify_code` | `standard` | `staged` | `NeedsRevalidation` | `docs/agents/runs/current/get-data-output-unification/task.yaml` |
| `hit-merged-peaklet-responsibility` | `planning` | `modify_code` | `standard` | `staged` | `NeedsRevalidation` | `docs/agents/runs/current/hit-merged-peaklet-responsibility/task.yaml` |
| `hit-threshold-ragged-optimization` | `planning` | `modify_plugin` | `standard` | `staged` | `NeedsRevalidation` | `docs/agents/runs/current/hit-threshold-ragged-optimization/task.yaml` |
| `import-topology-optimization` | `executing` | `modify_code` | `strict` | `staged` | `ReworkExecutionStarted` | `docs/agents/runs/current/import-topology-optimization/task.yaml` |
| `waveform-doc-content-recovery-20260901` | `reviewing` | `modify_code` | `standard` | `staged` | `—` | `docs/agents/runs/current/waveform-doc-content-recovery-20260901/task.yaml` |
| `waveform-doc-lineage-density-20260901` | `completed` | `modify_code` | `standard` | `staged` | `AllBlockingGatesPass` | `docs/agents/runs/current/waveform-doc-lineage-density-20260901/task.yaml` |
| `waveform-doc-system-opt-20260831` | `completed` | `retire_compat` | `strict` | `staged` | `PlanBriefReadyWithUserConfirmation` | `docs/agents/runs/current/waveform-doc-system-opt-20260831/task.yaml` |
<!-- END GENERATED: current_task_registry -->

Legacy plan text is retained as `legacy-plan.md` beside each current task. It is
historical input and is not a second source of truth.
