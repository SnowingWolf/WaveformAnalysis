# plan_brief

- `task_id`: `peaklet_channel_sort_canonical`
- `route`: `modify_plugin`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `medium`
- `scope_in`:
  - Remove avoidable feature/component and channel-key sorting from `peaklet_channels`.
  - Extract the dense canonical Numba primitives for reuse by `peaklet_channels` complex groups.
  - Preserve current dtype, dependencies, options, conflict exception and Python canonical fallback.
- `scope_out`:
  - No public option, output field, dependency, worker-model or cache-format change.
  - No broad site-documentation repair.
- `required_gates`:
  - targeted feature/channel/accessor tests and new fast/fallback path tests
  - Black, Ruff, compileall
  - generated auto/agent plugin references
  - `assess_change_impact`, `schema_compat_check`, doc sync and anchors
  - warm-JIT synthetic benchmark; real `00196` measurement when memory permits
- `executor_role`: `executor.plugin`
- `agent_profile`: `graph_engineer`
- `profile_plan`:
  - Use a validated dense-identity direct join and retain the existing sorted join for arbitrary inputs.
  - Skip `lexsort` only when `(peaklet_id, board, channel)` is already nondecreasing.
  - Share nopython dense canonical classify/materialize/reduce primitives; conflicting or unsafe groups re-enter the existing Python oracle.
- `blocking_assumptions`:
  - Normal `hit_merged_features` rows are dense by merged index, but runtime validation is required for legacy/external arrays.

## modify_plugin Notes

- `change_level`: `L1`
- `provides_impact`: none
- `depends_on_impact`: none
- `output_contract_impact`: none
- `version_action`: PATCH bump `peaklet_channels 2.0.1 -> 2.0.2`; PATCH bump `hit_merged_features 1.1.1 -> 1.1.2` for shared implementation lineage.
- `docs_sync_required`: true
- `execution_backend_decision`:
  - `backend`: `numpy + numba_serial + numba_parallel`
  - `backend_reason`: CPU-bound grouping and canonical sample materialisation; serial write owns each dense buffer.
  - `parallel_scope`: independent group classification only
  - `worker_option`: existing `feature_num_threads` continues to govern only hit feature execution; no new option
  - `fallback_path`: existing Python `merge_waveform_segments` for conflicts and unsafe groups
  - `benchmark_required`: true
