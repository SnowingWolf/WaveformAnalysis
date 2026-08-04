# plan_brief

- `task_id`: `hit_merged_features_fallback_repair_20260722`
- `route`: `modify_plugin`
- `workflow_cost`: `strict`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `high`
- `scope_in`: `hit_merged_features` fallback validation, runtime thread-option cache semantics, plugin version, focused tests, and generated plugin references.
- `scope_out`: `hit_merged`, `peaklet`, records merge behavior, and unrelated working-tree changes.
- `required_gates`:
  - `targeted_tests`
  - `assess_change_impact`
  - `schema_compat_check`
  - `doc_sync`
  - `doc_anchors`
- `executor_role`: `executor.plugin`
- `blocking_assumptions`:
  - Existing uncommitted changes outside the scoped paths remain untouched.

## modify_plugin Notes

- `change_level`: `L1`
- `provides_impact`: `none`
- `depends_on_impact`: `none`
- `output_contract_impact`: `none`; invalid fallback inputs now fail before entering the parallel kernel.
- `version_action`: patch bump required for changed fallback error behavior and cache configuration semantics.
- `docs_sync_required`: `true`
- `execution_backend_decision`:
  - `backend`: `numba_parallel`
  - `backend_reason`: `CPU-bound`
  - `parallel_scope`: `merged hit`
  - `worker_option`: `feature_num_threads`
  - `fallback_path`: validated component expansion before the existing Numba parallel kernel
  - `benchmark_required`: `false`; this repair must preserve the existing optimized backend.
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest tests/plugins/test_hit_merged_features_plugin.py -q`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/assess_change_impact.py --base HEAD`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/schema_compat_check.py --base HEAD --run-smoke`
  - `scripts/check_doc_sync.sh`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/check_doc_anchors.py --check-sync --base HEAD`
