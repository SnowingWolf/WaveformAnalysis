# plan_brief

- `task_id`: `html-docs-mdn-redesign-v1`
- `route`: `generate_docs`
- `workflow_cost`: `strict`
- `lifecycle_profile`: `doc_site_reviewed`
- `risk_level`: `high`
- `scope_in`: Redesign the generated `site-web` documentation portal with an MDN-inspired offline document shell, global search, responsive navigation, shared templates, focused tests, and CLI documentation.
- `scope_out`: React/Vue migration, online services, external runtime assets, dark theme, changes to plugin contracts, cache lineage, Accessor APIs, and unrelated dirty worktree files.
- `required_gates`:
  - `targeted_tests`
  - `plugins_auto_generation`
  - `plugins_agent_generation`
  - `assess_change_impact`
  - `schema_compat_check`
  - `doc_sync`
  - `doc_anchors`
  - `browser_review`
  - `handoff_check`
- `executor_role`: `executor.docs`
- `blocking_assumptions`:
  - The generated site must keep working through direct `file://` access with no external resource requests.
  - Existing `plugins-web` paths and generated plugin/Accessor URLs remain compatible.

## generate_docs Notes

- `doc_target_scope`: `site-web` home, plugin index/detail pages, Accessor index/detail pages, shared local assets, and `docs/cli/WAVEFORM_DOCS.md`.
- `source_change_summary`: Keep the Jinja/Python generator; add a shared MDN-style document shell and generated local search index rather than a JavaScript framework.
- `generation_mode`: `mixed`
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest tests/test_plugin_documentation.py tests/test_doc_generator.py -v`
  - `waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/`
  - `waveform-docs generate plugins-agent -o docs/plugins/reference/agent/`
  - `python scripts/assess_change_impact.py --base HEAD`
  - `python scripts/schema_compat_check.py --base HEAD --run-smoke`
  - `scripts/check_doc_sync.sh`
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
