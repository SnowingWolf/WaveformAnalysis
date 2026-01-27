# Worktree Workflow

This repository uses three git worktrees to isolate core work and plugin work
while keeping integration clean and repeatable. The root `WaveformAnalysis/`
directory acts as a management directory (optional); avoid active development
there when possible.

## Worktree Roles and Discipline

- core worktree: only change `waveform_analysis/core/**` and core-adjacent shared
  layers such as `waveform_analysis/utils/**` or core dependencies in
  `pyproject.toml`.
- plugins worktree: only change plugin implementations (records + stw), plugin
  docs, and plugin tests (prefer `tests/plugins/**`, `docs/plugins/**`, and
  plugin-related modules).
- integration worktree: no development. Only for merging core/plugins branches,
  running full tests, updating `CHANGELOG.md`, and tagging releases.

## Branch Naming and Commit Messages

Core/plugins branches:

- `wip/core`
- `wip/plugins`

Integration branch (temporary):

- `wip/integration`

Main branch policy:

- `main` accepts chapter-level commits only (prefer squash merges, 1-3 commits per change).

Commit message suggestions:

- `feat(core): ...`
- `fix(plugins): ...`
- `refactor(plugins): ...`
- `test: ...`
- `docs: ...`

## Create Worktrees

The script below creates three worktrees next to the repo:

```bash
./scripts/worktrees/create.sh
```

Defaults:

- `--prefix ..` (worktrees are created as `../wa-core`, `../wa-plugins`, `../wa-integration`)

## Bootstrap a Venv per Worktree

Each worktree has its own `.venv`:

```bash
cd ../wa-core
./scripts/worktrees/bootstrap_venv.sh

cd ../wa-plugins
./scripts/worktrees/bootstrap_venv.sh --with-core ../wa-core
```

Why `--with-core`? Plugin worktrees should explicitly install the core worktree
path to avoid editable path confusion across worktrees.

## Keeping Plugin Branches in Sync with Core

Prefer rebase for single-developer flows:

```bash
git switch wip/plugins
git fetch origin
git rebase wip/core
```

If multiple developers are involved, use merge as a safer alternative:

```bash
git merge wip/core
```

## Integration Flow

Run the integration script from `../wa-integration`:

```bash
./scripts/worktrees/integrate.sh \
  --core wip/core \
  --plugins wip/plugins
```

The script creates (or reuses) `wip/integration`, merges branches in
order, and runs tests (default: `make test`).

## Merge to main

Recommended: use squash merges for each core/plugins branch:

```bash
git switch main
git merge --squash wip/core
git commit -m "feat(core): core changes"
```

Repeat per branch (core, plugins). Update `CHANGELOG.md` as needed.

Merge order and verification:

- Merge order: `core` → `plugins`
- After each squash merge, run `make test` on `main` (or at least `make test-core` plus the
  relevant plugin test target) to keep chapter commits reliable and bisect-friendly.

## Worktree Cleanup

Common commands:

- `git worktree list`
- `git worktree prune`

Removing a worktree:

```bash
git worktree remove ../wa-plugins
```

## Common Pitfalls

- One branch cannot be checked out in multiple worktrees. Create a new branch per worktree.
- Remove worktrees with `git worktree remove <path>` and clean stale entries with
  `git worktree prune`.
- Editable installs can point at the wrong worktree. Verify with `pip show -f waveform-analysis`
  or `python -c "import waveform_analysis; print(waveform_analysis.__file__)"`.
- Avoid running development commands in the integration worktree.
- Keep venvs separate; do not reuse `.venv` across worktrees.

## Quickstart (3 minutes)

```bash
# 1) Create worktrees
./scripts/worktrees/create.sh

# 2) Bootstrap venvs
cd ../wa-core && ./scripts/worktrees/bootstrap_venv.sh
cd ../wa-plugins && ./scripts/worktrees/bootstrap_venv.sh --with-core ../wa-core

# 3) Develop and run scoped tests
make test-core
make test-plugins

# 4) Integration validation
cd ../wa-integration
./scripts/worktrees/integrate.sh \
  --core wip/core \
  --plugins wip/plugins
```
