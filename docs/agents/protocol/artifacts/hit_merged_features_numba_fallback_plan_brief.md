# plan_brief

- `task_id`: `hit_merged_features_numba_fallback`
- `route`: `modify_plugin`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `high`
- `scope_in`:
  - Preserve exact canonical fallback semantics while moving eligible cross-record feature work to Numba.
  - Add route/timing diagnostics and reduce large-pool persistence copies.
- `scope_out`:
  - No dtype, dependency, public configuration-default, or cache-format change.
- `required_gates`:
  - targeted tests
  - plugin documentation generation
  - assess_change_impact
  - schema_compat_check
  - doc_sync
  - doc_anchors
  - performance regression check
- `executor_role`: `executor.plugin`
- `agent_profile`: `graph_engineer`
- `profile_plan`:
  - Keep `peaklet_waveforms -> peaklet_waveform_pool` lineage and memory pairing intact while separating compute and persistence timing.
  - Verify that the new fallback does not alter downstream feature consumers.
- `blocking_assumptions`:
  - `run_id=00196` remains accessible for a warm-JIT timing check.

## modify_plugin Notes

- `change_level`: `L1`
- `provides_impact`: none
- `depends_on_impact`: none
- `output_contract_impact`: none; fallback values and overlap failures remain canonical.
- `version_action`: bump `hit_merged_features` minor version for the new execution path.
- `docs_sync_required`: true
- `execution_backend_decision`:
  - `backend`: `numba_parallel`
  - `backend_reason`: CPU-bound fallback sample transformation; every row writes a disjoint preallocated range.
  - `parallel_scope`: merged-hit row
  - `worker_option`: existing untracked `feature_num_threads`
  - `fallback_path`: Python oracle for overlapping/non-safe groups.
  - `benchmark_required`: true
