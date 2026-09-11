# plan_brief

- `task_id`: `adaptive-2d-sampling-public-api-v1`
- `route`: `modify_plugin`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `reviewed_change`
- `risk_level`: `high`
- `scope_in`:
  - Add a standalone adaptive two-dimensional stratified sampler under
    `waveform_analysis.utils`, without a runtime dependency on the source repository.
  - Expose `adaptive_sample_count` and `adaptive_stratified_sample_2d` through the
    lazy `waveform_analysis.utils` public API.
  - Cover bin parsing, seeded sampling, representative rows, diagnostics, input
    immutability, public imports, and the zero-cap boundary with focused tests.
  - Publish a source-backed user guide through the production site manifest.
- `scope_out`:
  - Do not modify `/home/wxy/Program/xihu_fast_analysis`.
  - Do not port the area-height/TMM-specific sampler, add a Context or plugin target,
    add a CLI, or write generated `docs/_site` output.
  - Do not export the sampler from the `waveform_analysis` package root.
- `required_gates`:
  - `targeted_sampling_tests`
  - `utils_public_import_contract`
  - `ruff`
  - `black_check`
  - `generate_plugins_auto`
  - `generate_plugins_agent`
  - `assess_change_impact`
  - `schema_compat_check_smoke`
  - `render_agent_docs_check`
  - `doc_sync`
  - `doc_anchors`
  - `doc_links`
  - `doc_coverage`
  - `site_web_temp_build`
  - `agent_handoff`
  - `scoped_commit`
  - `independent_reviewer`
- `executor_role`: `executor.plugin`
- `agent_profile`: `none`
- `profile_plan`:
  - Not applicable.
- `blocking_assumptions`:
  - None; NumPy and pandas are existing runtime dependencies and the initial worktree
    is clean.

## modify_plugin Notes

- `change_level`: `L2-equivalent` public Python API addition; no plugin contract changes.
- `provides_impact`: `not_applicable`
- `depends_on_impact`: `none`
- `output_contract_impact`: New DataFrame and optional per-bin diagnostics API.
- `version_action`: No plugin or package version change; include in a future minor release.
- `docs_sync_required`: `true`
- `execution_backend_decision`:
  - `backend`: `numpy`
  - `backend_reason`: `memory-bound`
  - `parallel_scope`: `none`
  - `worker_option`: `not_applicable`
  - `fallback_path`: pandas handles tabular input/output; NumPy handles masks, sorting,
    bin assignment, and random row selection.
  - `benchmark_required`: `false`
- `zero_cap_contract`:
  - When `n_take == 0`, select no representative row, report `n_sampled == 0`,
    `sampling_fraction == 0.0`, and `representative_index is None`.
- `public_imports`:
  - `from waveform_analysis.utils import adaptive_sample_count`
  - `from waveform_analysis.utils import adaptive_stratified_sample_2d`
  - Direct imports from `waveform_analysis.utils.sampling` remain supported.
