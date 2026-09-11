# plan_brief

- `task_id`: `site_web_atomic_publish`
- `route`: `generate_docs`
- `workflow_cost`: `standard`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `doc_only_reviewed`
- `risk_level`: `medium`
- `scope_in`: Atomic full-site publication for `waveform-docs generate site-web`, generated-site link validation, cache-disabled `waveform-docs serve` responses, focused tests, and CLI documentation.
- `scope_out`: Watch mode, automatic generation from `serve`, plugin/runtime contracts, cache lineage, and committing generated `docs/_site` files.
- `required_gates`:
  - `focused_pytest`
  - `site_web_generation`
  - `doc_sync`
  - `doc_anchors`
  - `diff_check`
- `executor_role`: `executor.docs`
- `agent_profile`: `none`
- `profile_plan`:
  - `not_applicable`
- `blocking_assumptions`:
  - `none`

## Optional Notes
- `change_level`: Public CLI behavior is strengthened without changing command names or arguments.
- `must_run_commands`:
  - `python -m pytest tests/test_cli_docs_site_publish.py tests/test_accessor_index_documentation.py tests/test_records_view_documentation.py -q --no-cov`
  - `waveform-docs generate site-web -o <temporary-directory>`
  - `scripts/check_doc_sync.sh`
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
