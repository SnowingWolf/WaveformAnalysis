# plan_brief

- `task_id`: plugin-web-clickable-lineage
- `route`: `generate_docs`
- `workflow_cost`: `standard`
- `lifecycle_profile`: `doc_only_reviewed`
- `risk_level`: `medium`
- `scope_in`: Offline `plugins-web` lineage views, documentation completeness and DAG impact scores, static navigation, source tests, and CLI documentation. The global graph must resolve each builtin plugin's dynamic dependencies against Option defaults, render the resulting whole-plugin graph with locally bundled Plotly, and accept a plugin-focused URL from a local-lineage page.
- `scope_out`: Runtime `Context` lineage, cache keys, plugin contracts, online deployment, and generated `docs/_site` artifacts.
- `required_gates`:
  - focused_plugin_web_tests
  - plugins_web_generation
  - doc_sync
  - doc_anchors
- `executor_role`: `executor.docs`
- `blocking_assumptions`:
  - The static site continues to be generated from builtin plugin documentation views only.

## generate_docs Notes

- `doc_target_scope`: `plugins-web` static site
- `source_change_summary`: Add a generated clickable plugin DAG and two documentation-only scores. Resolve dynamic dependencies using a no-data default-config facade so raw_files and other default-path nodes appear in the global Plotly graph; retain a compact static SVG for each plugin-local graph.
- `generation_mode`: manual
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest tests/test_plugin_documentation.py -q`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m waveform_analysis.utils.cli_docs generate plugins-web -o /tmp/waveform-plugin-site`
  - `PATH=/home/wxy/anaconda3/envs/pyroot-kernel/bin:$PATH scripts/check_doc_sync.sh`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python scripts/check_doc_anchors.py --check-sync --base HEAD`
- `docs_expected_to_change`:
  - `docs/cli/WAVEFORM_DOCS.md`
