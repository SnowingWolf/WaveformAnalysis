# plan_brief

- `task_id`: `lineage-reactflow-port-alignment-20260728`
- `route`: `generate_docs`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `doc_only_reviewed`
- `risk_level`: `high`
- `scope_in`: Generate the offline plugin lineage payload from the real `LineageGraphModel` node ports and edges; validate every node, port, and edge reference; render one React Flow Handle per real port; preserve overview/full plus core/all aliases and focus relations; use measured fixed-side/fixed-order ELK ports and orthogonal edge sections with a smoothstep fallback; expose exact `debug=lineage` diagnostics; add focused Python and executable TypeScript tests; rebuild the vendored React bundle.
- `scope_out`: Runtime `Context.plot_lineage`, plugin/cache contracts, the remaining static site's React migration, the legacy Cytoscape/Plotly site.js rewrite, standalone Cytoscape/ELK assets, and unrelated documentation or notebook changes.
- `required_gates`:
  - `focused_plugin_web_tests`
  - `site_react_typecheck`
  - `site_react_unit_tests`
  - `site_react_production_build`
  - `plugins_web_generation`
  - `doc_sync`
  - `doc_anchors`
- `executor_role`: `executor.docs`
- `agent_profile`: `graph_engineer`
- `profile_plan`:
  - Treat the runtime LabVIEW `LineageGraphModel` ports, node classification, and color semantics as the graph source of truth.
  - Keep topology generation and dangling-reference validation in Python, while React Flow owns interaction and ELK owns measured layered placement and orthogonal routing.
  - Preserve offline `file://` assets, existing page paths, focus links, and the `core`/`all` query aliases.
  - Require edge-count conservation and explicit smoothstep fallback when ELK omits edge sections.
- `blocking_assumptions`:
  - The checked-in `docs/site-react` dependency installation contains the Vite/TypeScript bindings needed to rebuild the vendored IIFE and CSS assets.
  - Existing dirty changes outside the declared lineage scope remain untouched and are not staged or committed by the Executor.

## generate_docs Notes

- `doc_target_scope`: Offline `plugins-web` lineage index and lineage entry embedded in the plugin index.
- `source_change_summary`: Replace plugin-level generic handles with model-derived port nodes and wires, then align the interactive layout and visual categories with notebook LabVIEW lineage without changing URL or generator entry points.
- `generation_mode`: `manual`
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest tests/test_plugin_documentation.py -q`
  - `npm run check --prefix docs/site-react`
  - `npm test --prefix docs/site-react`
  - `npm run build --prefix docs/site-react`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m waveform_analysis.utils.cli_docs generate plugins-web -o /tmp/waveform-plugin-site`
  - `PATH=/home/wxy/anaconda3/envs/pyroot-kernel/bin:$PATH scripts/check_doc_sync.sh`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/check_doc_anchors.py --check-sync --base HEAD`
- `docs_expected_to_change`:
  - `docs/site-react/src/**`
  - `waveform_analysis/utils/plugin_doc_generator.py`
  - `waveform_analysis/utils/templates/web/{base,index,lineage}.html.j2`
  - `waveform_analysis/utils/templates/web/assets/react/waveform-docs.{js,css}`
  - `tests/test_plugin_documentation.py`
