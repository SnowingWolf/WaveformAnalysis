# plan_brief

- `task_id`: `peaklet_waveforms_numba_performance`
- `route`: `modify_plugin`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `risk_level`: `high`
- `scope_in`: route cross-record/overlap peaklets through deterministic serial Numba canonical reconstruction while preserving the existing float32 rows/pool contract.
- `scope_out`: no public options, dtype fields, default signed/clipped semantics, or `n_workers` compatibility changes.
- `required_gates`: targeted waveform/downstream tests, plugin-reference generation, impact, schema smoke, performance regression, doc sync/anchors, handoff.
- `executor_role`: `executor.plugin`
- `agent_profile`: `none`
- `change_level`: `L2`
- `version_action`: `PeakletWaveformPlugin 2.0.0 -> 2.1.0`; paired-pool lineage invalidates transitively.
- `execution_backend_decision`: serial Numba classification plus fast/canonical kernels; Python/process only on unavailable or unexpected Numba failure; no nested parallelism.
- `benchmark_required`: `true`
