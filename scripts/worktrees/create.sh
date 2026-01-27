#!/usr/bin/env bash
set -euo pipefail

prefix=".."

usage() {
  echo "Usage: $0 [--prefix <path>]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      prefix="${2:-}"
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

if [[ -z "$prefix" ]]; then
  echo "--prefix must be non-empty."
  usage
  exit 1
fi

git rev-parse --show-toplevel >/dev/null 2>&1 || {
  echo "Run this from inside a git repository."
  exit 1
}

prefix="${prefix%/}"

paths=(
  "${prefix}/wa-core"
  "${prefix}/wa-records"
  "${prefix}/wa-stw"
  "${prefix}/wa-integration"
)

for path in "${paths[@]}"; do
  if [[ -e "$path" ]]; then
    echo "Target path already exists: $path"
    echo "Remove it or choose a different --prefix."
    exit 1
  fi
done

git worktree add "${prefix}/wa-core" -b "wip/core"
git worktree add "${prefix}/wa-records" -b "wip/records"
git worktree add "${prefix}/wa-stw" -b "wip/stw"
git worktree add "${prefix}/wa-integration" main

echo "Worktrees created under ${prefix}:"
echo "  wa-core, wa-records, wa-stw, wa-integration"
