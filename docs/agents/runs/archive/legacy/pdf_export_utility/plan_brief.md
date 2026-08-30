# plan_brief

- `task_id`: `pdf_export_utility`
- `route`: `public_utility_change`
- `workflow_cost`: `strict`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `public_api_review`
- `risk_level`: `medium`
- `scope_in`:
  - Add a public utility for exporting one or more Matplotlib figures as a PDF.
  - Export the utility from both visualization and top-level utils namespaces.
  - Add focused tests, user documentation, and staged handoff records.
- `scope_out`:
  - Existing PNG examples, automatic figure closing, PDF metadata, and report generation.
  - Existing unrelated worktree changes.
- `required_gates`:
  - focused PDF export tests
  - plugin documentation generation
  - change impact assessment
  - schema compatibility smoke test
  - documentation sync and anchor checks
- `executor_role`: `executor.python`
- `agent_profile`: `none`
- `blocking_assumptions`:
  - Matplotlib is an installed runtime dependency.
  - Existing unrelated worktree changes remain unstaged.

## Public API Contract

`save_figures_pdf(figures: Figure | Iterable[Figure], output_path: str | Path) -> Path`

- A single figure creates one page; an iterable creates pages in iteration order.
- The output suffix is normalized to `.pdf`, parent directories are created, and input figures remain open.
