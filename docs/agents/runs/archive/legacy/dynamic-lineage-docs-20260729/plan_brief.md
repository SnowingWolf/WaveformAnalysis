# plan_brief

- `task_id`: `dynamic-lineage-docs-20260729`
- `route`: `generate_docs`
- `workflow_cost`: `standard`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `doc_only_reviewed`
- `risk_level`: `medium`
- `scope_in`: Add an opt-in, same-origin dynamic lineage API backed by an explicit Context factory; retain the offline graph payload by default; complete the React Flow LabVIEW-style interaction with scroll panning and a node preview popover.
- `scope_out`: Plugin computation, run-data access, arbitrary client configuration, runtime `Context.plot_lineage()` API changes, and the local SVG lineage graphs.
- `required_gates`:
  - `focused_plugin_documentation_tests`
  - `site_react_typecheck`
  - `site_react_unit_tests`
  - `site_react_production_build`
  - `plugins_web_generation`
  - `doc_sync`
  - `doc_anchors`
- `executor_role`: `executor.docs`
- `blocking_assumptions`:
  - The provided Context factory is a trusted local import and returns a Context with registered plugins.
  - Existing dirty changes remain in place and are not reverted or staged unless they are part of this feature.

## Notes

- Dynamic mode is selected only by `?lineage=live`; an unavailable API must fall back to the generated JSON graph.
- The API returns topology and documentation metadata only and never accepts a `run_id`.
