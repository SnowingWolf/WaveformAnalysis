# plan_brief

- `task_id`: `architecture_docs_refresh_20260730`
- `route`: `retire_compat`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `compat_retirement_review`
- `risk_level`: `medium`
- `scope_in`: Refresh the published architecture documentation model; delete `DATA_ACCESS.md` and `architecture/data-access.html`; publish the agreed system, DAG/lineage/cache, data-product, wave-pool access, accessor, and multi-run pages; migrate active links and tests; remove the generated HTML `用户指南` section and its six routes while preserving Markdown sources.
- `scope_out`: Runtime implementation/API changes, Plugin contract/dtype changes, user-guide Markdown deletion or rewrite, HTTP redirects, and historical protocol artifact rewrites.
- `required_gates`:
  - `compat_inventory_ready`
  - `deletion_scope_confirmed`
  - `focused_documentation_tests`
  - `site_web_generation`
  - `doc_sync`
  - `doc_anchors`
  - `diff_check`
- `executor_role`: `executor.docs`
- `agent_profile`: `none`
- `profile_plan`:
  - `not_applicable`
- `blocking_assumptions`:
  - `The user explicitly approved removal of the old Markdown source and generated route without an HTML redirect.`

## retire_compat Notes

- `compat_inventory_required`: `true`
- `executor_role_override`: `executor.docs`
- `deletion_policy`: `balanced`
- `public_surface_confirmation_required`: `true; confirmed by the user`
- `high_risk_items_redirected`: `true; no Plugin/API/cache-contract deletion is in scope`
- `must_run_commands`:
  - `python -m pytest <focused architecture/site-guide tests> -q --no-cov`
  - `waveform-docs generate site-web -o docs/_site`
  - `scripts/check_doc_sync.sh`
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
  - `git diff --check`
