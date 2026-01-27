#!/usr/bin/env bash
set -euo pipefail

with_core=""

usage() {
  echo "Usage: $0 [--with-core <path>]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-core)
      with_core="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -n "$with_core" && ! -d "$with_core" ]]; then
  echo "--with-core path does not exist: $with_core"
  exit 1
fi

if [[ -d ".venv" ]]; then
  echo "Found existing .venv, reusing it."
else
  python -m venv .venv
fi

source .venv/bin/activate
python -m pip install -U pip

if ! pip install -e ".[dev]"; then
  echo "Dev extras not available, falling back to editable install without extras."
  pip install -e .
fi

if [[ -n "$with_core" ]]; then
  pip install -e "$with_core"
  echo "Installed core worktree from: $with_core"
fi

echo "Venv ready."
echo "Activate: source .venv/bin/activate"
echo "Run tests: make test"
