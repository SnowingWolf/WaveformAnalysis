# plan_brief

- `task_id`: `merged_feature_channel_hotpath`
- `route`: `modify_plugin`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `high`
- `scope_in`:
  - Route all safe `hit_merged_features` cross-record/overlap rows through a bounded Numba canonical merge.
  - Remove repeated full-table scans and unnecessary waveform rebuilding in `peaklet_channels`.
- `scope_out`:
  - Keep output dtypes, dependencies, options, signed/clipped semantics and overlap exceptions unchanged.
- `required_gates`:
  - targeted plugin/downstream tests
  - plugin documentation generation
  - assess_change_impact
  - schema_compat_check
  - doc_sync
  - doc_anchors
  - performance regression check
- `executor_role`: `executor.plugin`
- `agent_profile`: `graph_engineer`
- `profile_plan`:
  - Use one Numba parallel layer only; all groups write to disjoint bounded scratch ranges.
  - Preserve cache lineage behavior while avoiding needless consumers of records/wave pools on direct groups.
- `blocking_assumptions`:
  - The supplied `/mnt/data/TPC/run6_Xe/00196` cache remains readable for final warm-JIT measurement.

## modify_plugin Notes

- `change_level`: `L1`
- `provides_impact`: none
- `depends_on_impact`: none
- `output_contract_impact`: none
- `version_action`: PATCH bumps for `hit_merged_features` and `peaklet_channels`.
- `docs_sync_required`: true
- `execution_backend_decision`:
  - `backend`: `numba_parallel`
  - `backend_reason`: CPU-bound canonical sample materialization with disjoint output group slices.
  - `parallel_scope`: canonical merged-hit group
  - `worker_option`: existing `feature_num_threads` only; no additional worker option.
  - `fallback_path`: Python canonical oracle for malformed, mixed-grid, span-limited or conflicting groups.
  - `benchmark_required`: true
