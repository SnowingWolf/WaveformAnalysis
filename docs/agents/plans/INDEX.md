# Agent Plan Registry (compatibility view)

Active task state is owned by the v6 records under
`docs/agents/runs/current/<task-id>/task.yaml`. This file is generated for old
links and readers; edit the task record and rerun
`python scripts/render_agent_docs.py --write` instead of editing this view.

<!-- BEGIN GENERATED: current_task_registry -->
| task_id | state | route | cost | shape | condition | record |
| --- | --- | --- | --- | --- | --- | --- |
| `adapter-contracts-20261030` | `completed` | `retire_compat` | `strict` | `staged` | `—` | `docs/agents/runs/current/adapter-contracts-20261030/task.yaml` |
| `context-api-retirement-20261029` | `completed` | `retire_compat` | `strict` | `staged` | `—` | `docs/agents/runs/current/context-api-retirement-20261029/task.yaml` |
| `context-dedup-20261029` | `completed` | `modify_code` | `strict` | `staged` | `—` | `docs/agents/runs/current/context-dedup-20261029/task.yaml` |
| `context-simplification-20261104` | `reviewing` | `modify_code` | `strict` | `staged` | `—` | `docs/agents/runs/current/context-simplification-20261104/task.yaml` |
| `corner-hist-bincount-optimization` | `completed` | `modify_code` | `strict` | `staged` | `—` | `docs/agents/runs/current/corner-hist-bincount-optimization/task.yaml` |
| `docs-build-skill` | `reviewing` | `modify_code` | `strict` | `staged` | `—` | `docs/agents/runs/current/docs-build-skill/task.yaml` |
| `event-contract-hardening-20261103` | `completed` | `modify_plugin` | `strict` | `staged` | `—` | `docs/agents/runs/current/event-contract-hardening-20261103/task.yaml` |
| `execution-correctness-20261030` | `completed` | `modify_code` | `strict` | `staged` | `—` | `docs/agents/runs/current/execution-correctness-20261030/task.yaml` |
| `get-data-output-unification` | `planning` | `modify_code` | `standard` | `staged` | `NeedsRevalidation` | `docs/agents/runs/current/get-data-output-unification/task.yaml` |
| `hit-merged-peaklet-responsibility` | `planning` | `modify_code` | `standard` | `staged` | `NeedsRevalidation` | `docs/agents/runs/current/hit-merged-peaklet-responsibility/task.yaml` |
| `hit-merged-profiler-run00600` | `completed` | `modify_plugin` | `standard` | `staged` | `—` | `docs/agents/runs/current/hit-merged-profiler-run00600/task.yaml` |
| `hit-threshold-ragged-optimization` | `planning` | `modify_plugin` | `standard` | `staged` | `NeedsRevalidation` | `docs/agents/runs/current/hit-threshold-ragged-optimization/task.yaml` |
| `import-topology-optimization` | `executing` | `modify_code` | `strict` | `staged` | `ReworkExecutionStarted` | `docs/agents/runs/current/import-topology-optimization/task.yaml` |
| `managed-workflow-mvp` | `completed` | `modify_code` | `strict` | `staged` | `—` | `docs/agents/runs/current/managed-workflow-mvp/task.yaml` |
| `peak-classification-test-plugin-20260917` | `—` | `modify_plugin` | `standard` | `staged` | `—` | `docs/agents/runs/current/peak-classification-test-plugin-20260917/task.yaml` |
| `peaks-run00600-optimization` | `completed` | `modify_plugin` | `strict` | `staged` | `AllBlockingGatesPassed` | `docs/agents/runs/current/peaks-run00600-optimization/task.yaml` |
| `run00601-full-chain-performance` | `failed` | `modify_plugin` | `strict` | `staged` | `—` | `docs/agents/runs/current/run00601-full-chain-performance/task.yaml` |
| `run00601-records-buffer-8m` | `completed` | `modify_plugin` | `strict` | `staged` | `—` | `docs/agents/runs/current/run00601-records-buffer-8m/task.yaml` |
| `run00601-records-strategy-shootout` | `failed` | `modify_plugin` | `strict` | `staged` | `—` | `docs/agents/runs/current/run00601-records-strategy-shootout/task.yaml` |
| `system-hardening-20261029` | `completed` | `modify_code` | `strict` | `staged` | `—` | `docs/agents/runs/current/system-hardening-20261029/task.yaml` |
| `v1725-merged-parts-cleanup` | `completed` | `modify_code` | `strict` | `staged` | `—` | `docs/agents/runs/current/v1725-merged-parts-cleanup/task.yaml` |
| `v1725-records-performance-g1` | `reviewing` | `modify_plugin` | `strict` | `staged` | `—` | `docs/agents/runs/current/v1725-records-performance-g1/task.yaml` |
| `vx2730-bin-adapter-20260917` | `completed` | `modify_code` | `strict` | `staged` | `—` | `docs/agents/runs/current/vx2730-bin-adapter-20260917/task.yaml` |
| `wa-data-default-20260918` | `completed` | `modify_code` | `strict` | `staged` | `all_scoped_gates_pass` | `docs/agents/runs/current/wa-data-default-20260918/task.yaml` |
| `waveform-doc-content-recovery-20260901` | `completed` | `modify_code` | `standard` | `staged` | `—` | `docs/agents/runs/current/waveform-doc-content-recovery-20260901/task.yaml` |
| `waveform-doc-lineage-density-20260901` | `completed` | `modify_code` | `standard` | `staged` | `AllBlockingGatesPass` | `docs/agents/runs/current/waveform-doc-lineage-density-20260901/task.yaml` |
| `waveform-doc-nested-nav-20260902` | `completed` | `modify_code` | `strict` | `staged` | `—` | `docs/agents/runs/current/waveform-doc-nested-nav-20260902/task.yaml` |
| `waveform-doc-review-fixes-20260907` | `completed` | `modify_code` | `strict` | `staged` | `—` | `docs/agents/runs/current/waveform-doc-review-fixes-20260907/task.yaml` |
| `waveform-doc-sidebar-expand-20260902` | `completed` | `modify_code` | `standard` | `staged` | `—` | `docs/agents/runs/current/waveform-doc-sidebar-expand-20260902/task.yaml` |
| `waveform-doc-strict-optimization-20260902` | `completed` | `modify_code` | `strict` | `staged` | `—` | `docs/agents/runs/current/waveform-doc-strict-optimization-20260902/task.yaml` |
| `waveform-doc-system-opt-20260831` | `completed` | `retire_compat` | `strict` | `staged` | `PlanBriefReadyWithUserConfirmation` | `docs/agents/runs/current/waveform-doc-system-opt-20260831/task.yaml` |
| `waveform-version-sync-20260902` | `blocked` | `release_artifact_sync` | `strict` | `staged` | `FirefoxHeadlessEnvironmentBlocked` | `docs/agents/runs/current/waveform-version-sync-20260902/task.yaml` |
| `workspace-cleanup-20261030` | `completed` | `generate_docs` | `light` | `staged` | `—` | `docs/agents/runs/current/workspace-cleanup-20261030/task.yaml` |
<!-- END GENERATED: current_task_registry -->

Legacy plan text is retained as `legacy-plan.md` beside each current task. It is
historical input and is not a second source of truth.
