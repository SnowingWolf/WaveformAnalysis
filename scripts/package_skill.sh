#!/usr/bin/env bash
set -euo pipefail

skill_dir="${1:-}"
out_dir="${2:-dist}"

if [[ -z "${skill_dir}" ]]; then
  echo "Usage: package_skill.sh <skill-dir> [out-dir]" >&2
  exit 1
fi

if [[ ! -d "${skill_dir}" ]]; then
  echo "Skill directory not found: ${skill_dir}" >&2
  exit 1
fi

if [[ ! -f "${skill_dir}/SKILL.md" ]]; then
  echo "Missing SKILL.md in ${skill_dir}" >&2
  exit 1
fi

skill_name="$(basename "${skill_dir}")"
mkdir -p "${out_dir}"
out_path="${out_dir}/${skill_name}.skill"

python -m zipfile -c "${out_path}" "${skill_dir}"
echo "Wrote ${out_path}"
