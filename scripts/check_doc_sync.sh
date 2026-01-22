#!/usr/bin/env bash
set -euo pipefail

base="${1:-HEAD}"

echo "Doc sync check (base: ${base})"
echo

echo "Changed code files:"
git diff --name-status "${base}" -- \
  'waveform_analysis/**' '*.py' ':!docs/**' ':!tests/**' | \
  sed 's/^/  /' || true
echo

echo "Changed docs and guidance files:"
git diff --name-status "${base}" -- \
  'docs/**' 'CHANGELOG.md' 'CLAUDE.md' 'AGENTS.md' | \
  sed 's/^/  /' || true
echo

echo "Tip: compare code vs doc lists and update missing items."
