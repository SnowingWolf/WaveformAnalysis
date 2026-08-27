# plan_brief

- `task_id`: `cache-lineage-key-stability`
- `route`: `modify_plugin`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `reviewed_change`
- `workflow_cost`: `strict`
- `risk_level`: `high`
- `scope_in`: Stabilize Context lineage/key identity across cold/warm cache state and traversal order; normalize built-in custom lineage providers; safely reuse logically equivalent historical disk-cache keys without modifying production cache files.
- `scope_out`: Plugin algorithms, output dtypes, classification rules, automatic cache deletion/renaming/copying, and compatibility retirement.
- `required_gates`:
  - `focused_lineage_cache_tests`
  - `production_cache_read_only_preview`
  - `generate_docs`
  - `assess_change_impact`
  - `schema_compat_check`
  - `doc_sync`
  - `doc_anchors`
- `executor_role`: `executor.plugin`
- `agent_profile`: `graph_engineer`
- `profile_plan`:
  - Preserve one canonical base-lineage recursion path and add `adapter_info` exactly once at the public top level.
  - Make custom lineage dependency expansion use an explicit resolver while preserving legacy third-party hook signatures.
  - Accept historical cache keys only after metadata-backed, allowlisted normalization proves semantic equivalence.
- `blocking_assumptions`:
  - Existing caches may differ only in placement/presence of `adapter_info`; any version, config, dtype, schema, dependency, plugin class, or run difference remains invalid.
  - Production cache validation is read-only and must not materialize the full run `00196` peaks array.

## modify_plugin Notes

- `change_level`: `L2`
- `provides_impact`: none
- `depends_on_impact`: dependency declarations unchanged; lineage construction becomes order-independent.
- `output_contract_impact`: none
- `version_action`: no plugin version bump; no plugin algorithm, dtype, config, or numeric-output semantics change.
- `docs_sync_required`: true
- `execution_backend_decision`:
  - `backend`: `python`
  - `backend_reason`: cache metadata and lineage control flow
  - `parallel_scope`: none
  - `worker_option`: none
  - `fallback_path`: metadata-validated read-only lookup of historical keys
  - `benchmark_required`: false
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest -q tests/test_cache_optimization.py tests/contracts/test_cache_consistency.py waveform_analysis/core/config/tests/test_config.py tests/plugins/test_plugin_auto_config_waveforms.py`
  - `./scripts/run_tests.sh -v -k 'lineage or cache'`
  - `waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/`
  - `waveform-docs generate plugins-agent -o docs/plugins/reference/agent/`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/assess_change_impact.py --base HEAD`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/schema_compat_check.py --base HEAD --run-smoke`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/render_agent_docs.py --check`
  - `scripts/check_doc_sync.sh`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/check_doc_anchors.py --check-sync --base HEAD`

## Acceptance Criteria

- Repeated public lineage calls and different dependency traversal orders produce identical lineage and canonical keys.
- `adapter_info` appears exactly once at the public lineage root and does not leak into recursive base lineage.
- Built-in custom lineage providers use the resolver; legacy third-party `get_lineage(context)` hooks remain callable.
- Canonical cache entries win. Historical entries are reused only when complete metadata becomes exactly equal after recursively removing `adapter_info`, with no adapter conflict.
- Cache validity checks, execution previews, and real loads choose the same resolved disk key.
- Existing logically equivalent run `00196` caches remain cache hits without plugin execution or disk mutation.
- The scoped commit contains only task code, tests, docs, and the three staged artifacts.
