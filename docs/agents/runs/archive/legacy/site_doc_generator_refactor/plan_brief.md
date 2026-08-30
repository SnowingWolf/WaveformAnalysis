# plan_brief

- `task_id`: `site_doc_generator_refactor`
- `route`: `generate_docs`
- `workflow_cost`: `standard`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `doc_generator_refactor`
- `risk_level`: `medium`
- `scope_in`:
  - Split the private models/safety validation and curated content registry out of `waveform_analysis/utils/site_doc_generator.py`.
  - Preserve `DocumentationSiteGenerator`, the CLI import path, generated routes, and existing module-level import compatibility.
  - Fix content-asset discovery for every generated page, avoid duplicate signature inspection, and normalize NumPy aliases in wrapped signatures.
- `scope_out`:
  - Do not move the package from `waveform_analysis.utils` to `waveform_analysis.documentation` in this change.
  - Do not change Markdown guide discovery, templates, generated `docs/_site`, navigation routes, or public document wording.
  - Do not perform the unrelated DRY decomposition of every `generate()` write call.
- `required_gates`:
  - focused_site_generator_tests
  - site_web_atomic_publish_test
  - source_import_compatibility
  - diff_check
- `executor_role`: `executor.docs`
- `agent_profile`: `none`
- `profile_plan`:
  - Not applicable.
- `blocking_assumptions`:
  - The existing public import path remains available through re-exports from `site_doc_generator.py`.

## Optional Notes

- `change_level`: internal refactor with output-correctness fixes
- `must_run_commands`:
  - `pytest tests/test_plugin_documentation.py tests/test_site_guides.py tests/test_cli_docs_site_publish.py`
  - `python -m waveform_analysis.utils.cli_docs generate site-web -o <temporary-output>`
