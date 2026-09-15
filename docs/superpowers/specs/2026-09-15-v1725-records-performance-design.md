# V1725 records performance design

## Objective

Improve V1725 RAW-to-records throughput without changing formal data products. The design
separates four concerns so each can be measured and reviewed independently before integration.

## Architecture

The reader first consumes complete read windows and emits an internal array batch containing
primitive metadata and waveform offsets. The records builder fills the structured records array
from those primitives and copies waveform blocks into a bounded wave pool. Storage chooses parts
from a byte budget rather than an unconditional wave-count cap. Parallelism is applied at one
measured file/run layer under global worker, RSS, scratch, and merge budgets.

`V1725Reader.iter_waves()` remains a compatibility adapter. Formal `records` and `wave_pool`
contracts, ordering, dtype, cache semantics, and truncation behavior remain unchanged.

## Integration boundaries

- Reader, array, and storage prototypes are developed in independent worktrees.
- Their commits are reviewed together before the resource-management stream starts.
- A dedicated integration worktree applies compatible commits in dependency order.
- A separate read-only reviewer owns exact-output and performance acceptance.

## Safety and validation

Production run caches are read-only. Benchmarks write only to a task-specific NAS root and serialize
real-data load. Every candidate records exact environment, command, wall, CPU, RSS, I/O, output hash,
part count, scratch bytes, lineage, and cache behavior. Task-created large data is deleted only after
small evidence is preserved and exact paths are rechecked.

Algorithm-path changes require the repository-mandated plugin version and generated documentation
updates. A performance improvement cannot compensate for any output, boundary, lineage, or cleanup
regression.
