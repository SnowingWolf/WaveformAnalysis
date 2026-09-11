# plan_brief

- `task_id`: `lineage-virtual-plugins`
- `route`: `modify_plugin`
- `workflow_cost`: `strict`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `high`
- `scope_in`: Add opt-in `lineage_virtual` display metadata and the `show_virtual_plugins` control to `Context.plot_lineage()`, including shared graph filtering, tests, and user documentation.
- `scope_out`: Plugin execution, dependency resolution, cache lineage, output dtypes, and automatic marking of existing plugins.
- `required_gates`:
  - focused_lineage_virtual_tests
  - assess_change_impact
  - schema_compat_check
  - doc_sync
  - doc_anchors
- `executor_role`: `executor.plugin`
- `blocking_assumptions`:
  - Matplotlib and Plotly are available in the project test environment.

## modify_plugin Notes

- `change_level`: `L2`
- `provides_impact`: none
- `depends_on_impact`: none
- `output_contract_impact`: public visualization API gains an optional parameter; runtime plugin output contracts are unchanged.
- `version_action`: not required; no registered plugin behavior or plugin output changes.
- `docs_sync_required`: true
- `execution_backend_decision`:
  - `backend`: `python`
  - `backend_reason`: `startup-cost-sensitive`
  - `parallel_scope`: `none`
  - `worker_option`: none
  - `fallback_path`: not applicable
  - `benchmark_required`: false
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest tests/test_context_core_preview.py tests/test_lineage_visualizer.py -q`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/assess_change_impact.py --base HEAD`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/schema_compat_check.py --base HEAD --run-smoke`
  - `scripts/check_doc_sync.sh`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/check_doc_anchors.py --check-sync --base HEAD`
