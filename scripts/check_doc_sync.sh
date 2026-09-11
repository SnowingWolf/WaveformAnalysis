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

base="HEAD"
base_explicit=0
task=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      if [[ $# -lt 2 ]]; then
        echo "--base requires a Git ref" >&2
        exit 2
      fi
      base="$2"
      base_explicit=1
      shift 2
      ;;
    --base=*)
      base="${1#--base=}"
      base_explicit=1
      shift
      ;;
    --task)
      if [[ $# -lt 2 ]]; then
        echo "--task requires a task YAML path" >&2
        exit 2
      fi
      task="$2"
      shift 2
      ;;
    --task=*)
      task="${1#--task=}"
      shift
      ;;
    --)
      shift
      if [[ $# -gt 0 ]]; then
        echo "unexpected argument after --: $1" >&2
        exit 2
      fi
      ;;
    -*)
      echo "unknown option: $1" >&2
      exit 2
      ;;
    *)
      if [[ "${base_explicit}" -eq 1 || "${base}" != "HEAD" ]]; then
        echo "multiple positional/base Git refs supplied" >&2
        exit 2
      fi
      base="$1"
      base_explicit=1
      shift
      ;;
  esac
done

scope_args=()
if [[ -n "${task}" ]]; then
  scope_args+=(--task "${task}")
  if [[ "${base_explicit}" -eq 1 ]]; then
    scope_args+=(--base "${base}")
  fi
  base="$("${python_bin}" scripts/change_scope.py base "${scope_args[@]}")"
fi

echo "Doc sync check (base: ${base})"
echo

if [[ -n "${task}" ]]; then
  echo "Task-scoped changed paths:"
  "${python_bin}" scripts/change_scope.py report --task "${task}" --base "${base}"
  echo
else
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
fi

echo "Tip: compare code vs doc lists and update missing items."
echo

if [[ -n "${task}" ]]; then
  echo "Skipping repository-wide generated-doc validation in task mode."
  echo "Task-scoped gates report only the selected task's paths."
  echo
else
  echo "Running Agent Doc manifest validation..."
  echo
  "${python_bin}" scripts/render_agent_docs.py --check
  echo
fi

# 运行 Python 脚本进行详细检查
if [[ -n "${task}" ]]; then
  echo "Running task-scoped Doc Anchor validation..."
else
  echo "Running repository-wide Doc Anchor validation..."
fi
echo
if [[ -n "${task}" ]]; then
  "${python_bin}" scripts/check_doc_anchors.py --check-sync --task "${task}" --base "${base}"
else
  "${python_bin}" scripts/check_doc_anchors.py --check-sync --base "${base}"
fi
