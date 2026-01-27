#!/usr/bin/env bash
set -euo pipefail

core_branch=""
plugins_branch=""
tests_cmd="make test"

usage() {
  echo "Usage: $0 --core <branch> --plugins <branch> [--tests <cmd>]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --core)
      core_branch="${2:-}"
      shift 2
      ;;
    --plugins)
      plugins_branch="${2:-}"
      shift 2
      ;;
    --tests)
      tests_cmd="${2:-}"
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

if [[ -z "$core_branch" || -z "$plugins_branch" ]]; then
  echo "Missing required arguments."
  usage
  exit 1
fi

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$current_branch" != "main" ]]; then
  echo "Run this from the main worktree on main."
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Commit or stash changes before integrating."
  exit 1
fi

merge_branch() {
  local branch="$1"
  echo "Merging ${branch}..."
  if ! git merge --no-ff "${branch}"; then
    echo "Merge failed for ${branch}."
    echo "Next steps: git merge --abort"
    exit 1
  fi
}

merge_branch "${core_branch}"
merge_branch "${plugins_branch}"

echo "Running tests: ${tests_cmd}"
if ! eval "${tests_cmd}"; then
  echo "Tests failed."
  echo "Next steps: fix the failures or undo the merge manually."
  exit 1
fi
