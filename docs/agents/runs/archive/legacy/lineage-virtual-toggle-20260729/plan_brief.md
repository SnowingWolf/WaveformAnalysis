# plan_brief

- `task_id`: `lineage-virtual-toggle-20260729`
- `route`: `generate_docs`
- `workflow_cost`: `standard`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `doc_only_reviewed`
- `risk_level`: `medium`
- `scope_in`: Add a static-site DAG control that hides calculation-only virtual nodes while preserving real upstream-to-downstream port connections.
- `scope_out`: Plugin execution, run-data access, the default Python lineage API, and virtual-node classification.
- `required_gates`: `site_react_typecheck`, `site_react_unit_tests`, `focused_plugin_documentation_tests`, `plugins_web_generation`, `doc_sync`, `doc_anchors`.
- `executor_role`: `executor.docs`

## Design

- The control defaults to showing all nodes.
- Disabling it removes only nodes marked `isLineageVirtual` in the browser-derived graph.
- Each virtual node's input/output port pairs are bypassed into direct edges. The original source edge supplies every visual property, so source plugin-set colors and solid/dashed status remain authoritative.
