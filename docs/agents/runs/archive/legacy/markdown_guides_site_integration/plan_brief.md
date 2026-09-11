# plan_brief

- `task_id`: `markdown_guides_site_integration`
- `route`: `generate_docs`
- `workflow_cost`: `standard`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `doc_only_reviewed`
- `risk_level`: `medium`
- `scope_in`: Manifest-selected Markdown rendering in `site-web`, categorized navigation, guide search entries, local-link rewriting/degradation, local asset publication, focused tests, and CLI documentation.
- `scope_out`: Recursive publication of the full Markdown corpus, changing Markdown source bodies, replacing generated API/plugin reference pages, and changing existing CLI command names.
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

## generate_docs Notes

- `doc_target_scope`: Eight curated user-guide and architecture Markdown pages listed in `docs/site-guides.yaml`.
- `source_change_summary`: Markdown remains the narrative source of truth; HTML becomes a generated publication surface with shared navigation and search.
- `generation_mode`: `mixed`
- `must_run_commands`:
  - `python -m pytest <focused documentation tests> -q --no-cov`
  - `waveform-docs generate site-web -o <temporary-directory>`
  - `scripts/check_doc_sync.sh`
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
- `docs_expected_to_change`:
  - `docs/site-guides.yaml`
  - `docs/cli/WAVEFORM_DOCS.md`
  - HTML templates and generated-site tests
