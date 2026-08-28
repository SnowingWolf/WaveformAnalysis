# plan_brief

- `task_id`: `python_ci_failures_20260828`
- `route`: `run_tests`
- `workflow_cost`: `standard`
- `workflow_shape`: `staged`
- `lifecycle_profile`: `qa_review`
- `risk_level`: `medium`
- `scope_in`: repair the Python CI failures at commit `99d757d` by modernizing lint-only type annotations, aligning the CI Black version with pre-commit, and correcting the slow-test synthetic timestamp model
- `scope_out`: production plugin behavior, waveform overlap policy, plugin contracts, generated documentation, and unrelated tests
- `required_gates`:
  - `ruff_check`
  - `black_check`
  - `plugin_dependency_check`
  - `pytest_fast_complete`
  - `pytest_slow_complete`
- `executor_role`: `executor.qa`
- `blocking_assumptions`:
  - the canonical waveform contract must continue to reject conflicting samples at identical `(board, channel, abs_time_ps)` keys

## run_tests Notes

- `test_target`: GitHub Actions Python CI fast matrix and slow job
- `keyword_or_path`: repository-wide lint plus `tests/plugins/test_stress_tests.py`
- `env_assumption`: local pyroot-kernel Python 3.12 matches the failing slow job interpreter
- `must_run_commands`:
  - `ruff check .`
  - `black --check .`
  - `python scripts/check_plugin_deps.py`
  - `pytest`
  - `pytest -m slow -o addopts=""`
