---
name: docs-build
description: Build and validate WaveformAnalysis documentation in an external workspace, optionally staging the validated static export for packaging.
---

# Documentation build

Use the current checkout's `scripts/docs_build.py`; read `docs/agents/docs-build.md`
for options and evidence. Preserve the user's selected worktree and documentation sources.

Run with Python 3.10+ and `PYTHONPATH` pointing to that worktree. In this environment,
use `/home/wxy/anaconda3/envs/pyroot-kernel/bin/python`; do not install Python dependencies
into the shared environment.

Choose a fresh run ID. The default builds externally and leaves `site_dist` intact.
Use `--stage-output` when updating the packaged export is within the requested scope.
The script uses a private app and dependencies per run, sharing only npm's download
cache. Existing commands remain supported. It does not commit or stage Git files.

Inspect `report.json`, `build.log`, `site-model.json`, and `site/` before reporting
success. A passing unit test is not a real build. On installation or build failure,
report the exact error and retained evidence; retry with a new run ID.

Place the validated packaged export in the task diff before Reviewer review.
Acceptance integrates that reviewed version without rebuilding. Leave merge, publication,
worktree removal and cleanup to the parent workflow. Keep build artifacts for inspection.
