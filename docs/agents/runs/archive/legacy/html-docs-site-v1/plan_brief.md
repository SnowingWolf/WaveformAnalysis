# plan_brief

- `task_id`: `html-docs-site-v1`
- `route`: `generate_docs`
- `workflow_cost`: `strict`
- `lifecycle_profile`: `doc_only_reviewed`
- `risk_level`: `high`
- `scope_in`: Add the public `site-web` CLI mode, compose the existing plugin HTML site under `/plugins`, generate a curated Accessor section, share an offline Chinese site shell, preserve `plugins-web`, define a documentation-only dependency profile, add Core/All terminal-output views and shareable URL state, update CLI documentation, and add focused tests.
- `scope_out`: Rendering the Markdown user guide, architecture, API, or CLI corpus into the site; changing plugin contracts, versions, cache lineage, Accessor behavior, or the public Python API.
- `required_gates`:
  - `targeted_tests`
  - `plugins_auto_generation`
  - `plugins_agent_generation`
  - `assess_change_impact`
  - `schema_compat_check`
  - `doc_sync`
  - `doc_anchors`
  - `local_link_check`
  - `browser_review`
- `executor_role`: `executor.docs`
- `blocking_assumptions`:
  - The live `PeakChannelAccessor` and `S1S2PairAccessor` classes remain importable while the site is generated.
  - Plotly remains available for the existing plugin lineage generation path.

## generate_docs Notes

- `doc_target_scope`: Chinese offline HTML documentation home, plugin section, Accessor section, and `waveform-docs` CLI reference.
- `source_change_summary`: Add an internal site generator and structured Accessor documentation registry; parameterize plugin web routes and shared assets without changing the legacy `plugins-web` output contract.
- `dependency_profile`: Shared `wave_source=records`, `use_filtered=false`, and `daq_adapter=vx2730`; plugin-specific `hit_threshold.asymmetry_cut_enabled=true`; precedence is plugin-specific, shared, then `Option.default`.
- `lineage_views`: Resolve dependencies once, lay out the complete graph once, derive coordinate-stable Core/All views, hide non-`events` leaves in Core, and list `cache_analysis` under Standalone Tools.
- `generation_mode`: `mixed`
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest tests/test_plugin_documentation.py tests/test_doc_generator.py -v`
  - `waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/`
  - `waveform-docs generate plugins-agent -o docs/plugins/reference/agent/`
  - `python scripts/assess_change_impact.py --base HEAD`
  - `python scripts/schema_compat_check.py --base HEAD --run-smoke`
  - `scripts/check_doc_sync.sh`
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
- `docs_expected_to_change`:
  - `docs/cli/WAVEFORM_DOCS.md`
  - `docs/agents/protocol/artifacts/html_docs_site_v1_plan_brief.md`
  - `docs/agents/protocol/artifacts/html_docs_site_v1_execution_report.md`

## Acceptance Notes

- `plugins-web` retains its CLI arguments, default output, root `index.html`, `plugins/*.html`, and `assets/*` layout.
- `site-web` rejects `--plugin`, generates only the two registered Accessor pages, fails on a missing registered member, escapes dynamic HTML, and references no external resource.
- Both generated sites support direct `file://` opening and `waveform-docs serve`.
- `?view=core|all&focus=<provides>` restores browser history state, and terminal focus selects `all` automatically.
