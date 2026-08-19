#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd -- "${script_dir}/.." && pwd)"

if [[ -n "${WAVEFORM_PYTHON:-}" ]]; then
  python_bin="${WAVEFORM_PYTHON}"
elif [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  python_bin="${VIRTUAL_ENV}/bin/python"
elif [[ -x "${project_root}/.venv/bin/python" ]]; then
  python_bin="${project_root}/.venv/bin/python"
else
  python_bin="$(command -v python3 || command -v python || true)"
fi
if [[ "${python_bin}" != */* ]]; then
  python_bin="$(command -v "${python_bin}" || true)"
fi
if [[ -z "${python_bin}" || ! -x "${python_bin}" ]]; then
  echo "Could not find a usable Python 3 interpreter; set WAVEFORM_PYTHON." >&2
  exit 1
fi

if ! "${python_bin}" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)' >/dev/null 2>&1; then
  version="$(${python_bin} -c 'import sys; print(".".join(map(str, sys.version_info[:3])))' 2>/dev/null || printf 'unknown')"
  echo "需要 Python >= 3.10（选择的解释器为 ${version}: ${python_bin}）；请设置 WAVEFORM_PYTHON。" >&2
  exit 1
fi

cd "${project_root}"
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
echo

echo "Running Agent Doc manifest validation..."
echo
"${python_bin}" scripts/render_agent_docs.py --check
echo

# 运行 Python 脚本进行详细检查
echo "Running Doc Anchor validation..."
echo
"${python_bin}" scripts/check_doc_anchors.py --check-sync --base "${base}"
