#!/usr/bin/env bash
set -euo pipefail

# Run test suite with proper conda activation.
# Usage: ./scripts/run_tests.sh [pytest args]

CONDA_ENV=${CONDA_ENV:-pyroot-kernel}
PYTEST_ARGS=${@:-}

# Find conda base and source conda.sh
if command -v conda >/dev/null 2>&1; then
  CONDA_BASE=$(conda info --base)
  # shellcheck source=/dev/null
  source "$CONDA_BASE/etc/profile.d/conda.sh"
else
  echo "conda command not found in PATH. Please ensure Conda is installed." >&2
  exit 1
fi

# Prefer using `conda run -n` to avoid shell activation side-effects
# Check if pytest is available in the target env; if not, install it via pip inside env
echo "Using conda env: $CONDA_ENV (running tests with conda run -n $CONDA_ENV)"

# Check pytest availability
set +e
conda run -n "$CONDA_ENV" python -c "import pytest" >/dev/null 2>&1
PYTEST_OK=$?
set -e
if [ "$PYTEST_OK" -ne 0 ]; then
  echo "pytest is not available in environment $CONDA_ENV. Installing pytest via pip inside the env..."
  conda run -n "$CONDA_ENV" pip install pytest pytest-cov
fi

# Run pytest with given args
echo "Running pytest $PYTEST_ARGS inside env $CONDA_ENV"
conda run -n "$CONDA_ENV" pytest $PYTEST_ARGS
