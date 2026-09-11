# Legacy Agent Artifacts

This directory is a read-only historical archive. The files here are preserved
from the former `docs/agents/protocol/artifacts/` collection and are not live
task state, approval evidence, or an input to task routing.

`MANIFEST.json` records the original repository path, archive path, byte size,
and SHA-256 digest for every migrated artifact. The digest is calculated from
the source bytes before migration; archived files must not be rewritten. The
five generic compatibility templates remain at
`docs/agents/protocol/artifacts/` and point new work to the canonical
`docs/agents/runs/current/<task-id>/task.yaml` record.

For active work, use `docs/agents/runs/current/`. Do not infer lifecycle state
from this archive or edit an archived report in place.
