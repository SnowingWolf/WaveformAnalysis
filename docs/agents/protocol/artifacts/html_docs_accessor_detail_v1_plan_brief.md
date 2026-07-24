# plan_brief

- `task_id`: `html-docs-accessor-detail-v1`
- `route`: `generate_docs`
- `workflow_cost`: `strict`
- `lifecycle_profile`: `doc_only_reviewed`
- `risk_level`: `high`
- `scope_in`: Extend the generated `site-web` Accessor pages with curated Chinese introductions, live signature-derived parameter models, parameter/return/usage notes, executable Python examples, and offline syntax highlighting.
- `scope_out`: Accessor runtime behavior, public CLI behavior, `plugins-web`, plugin contracts, cache lineage, and generated site output committed to the repository.
- `required_gates`:
  - `focused_accessor_documentation_tests`
  - `format_and_lint`
  - `site_web_generation`
  - `doc_sync`
  - `doc_anchors`
- `executor_role`: `executor.docs`
- `blocking_assumptions`:
  - `PeakChannelAccessor` and `S1S2PairAccessor` remain importable for runtime signature inspection.
  - The `docgen` extra supplies Pygments for generated Accessor example highlighting.

## generate_docs Notes

- `doc_target_scope`: `site-web` Accessor index and the two registered Accessor detail pages.
- `source_change_summary`: Replace terse Accessor member descriptions with a structured, validated documentation registry and semantic HTML presentation.
- `generation_mode`: `manual`
- `must_run_commands`:
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m pytest tests/test_plugin_documentation.py tests/test_doc_generator.py -v`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m black --check waveform_analysis/utils/site_doc_generator.py tests/test_plugin_documentation.py`
  - `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python -m ruff check waveform_analysis/utils/site_doc_generator.py tests/test_plugin_documentation.py`
  - `scripts/check_doc_sync.sh`
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
- `docs_expected_to_change`:
  - `docs/cli/WAVEFORM_DOCS.md`
  - `docs/agents/protocol/artifacts/html_docs_accessor_detail_v1_*.md`
