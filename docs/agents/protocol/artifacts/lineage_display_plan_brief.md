# plan_brief

- `task_id`: lineage-display-adaptive-layout
- `route`: `modify_plugin`
- `workflow_cost`: `standard`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `medium`
- `scope_in`: Lineage LabVIEW and Plotly layout sizing, port placement, rendering bounds, and focused regression tests.
- `scope_out`: `get_lineage()` contents, cache keys, plugin dependencies, and Mermaid output.
- `required_gates`:
  - focused_lineage_visualizer_tests
  - assess_change_impact
  - schema_compat_check
  - doc_sync
  - doc_anchors
- `executor_role`: `executor.plugin`
- `blocking_assumptions`:
  - Matplotlib and Plotly are available in the project test environment.

## modify_plugin Notes

- `change_level`: L1
- `provides_impact`: none
- `depends_on_impact`: none
- `output_contract_impact`: none; only rendered geometry changes
- `version_action`: not required; no plugin behavior changes
- `docs_sync_required`: true; document adaptive node and port sizing
- `execution_backend_decision`:
  - `backend`: python
  - `backend_reason`: startup-cost-sensitive
  - `parallel_scope`: none
  - `worker_option`: none
  - `fallback_path`: not applicable
  - `benchmark_required`: false
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest tests/test_lineage_visualizer.py -q`
  - `python scripts/assess_change_impact.py --base HEAD`
  - `python scripts/schema_compat_check.py --base HEAD --run-smoke`
  - `scripts/check_doc_sync.sh`
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
