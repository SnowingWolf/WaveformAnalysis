# V1725 records performance G1 goal

Optimize the V1725 RAW-to-`records`/`wave_pool` path in four bounded workstreams:
reader I/O, array-first construction, storage/merge, and resource-aware parallelism.

## Deliverables

- Consume each reader window without the fixed 1,000-event rewind amplification.
- Add an internal array-batch path while preserving `iter_waves()` compatibility.
- Reduce part-file and merge/write amplification under an explicit memory budget.
- Select one bounded file/run concurrency layer from measured evidence.
- Preserve `records` and `wave_pool` dtype, shape, order, bytes, lineage, and cache behavior.

## Constraints

- Base SHA: `d47fed4d49f115ba46d7a98823c83ec21a7119e4`.
- Every implementation workstream uses an independent worktree.
- Four Luna Max agents participate; the current task can run only three child agents at once,
  so the resource-management stream starts when one first-stage slot is released.
- Large benchmark outputs live under
  `/mnt/data/tmp/wa-v1725-records-performance-g1/`; production `_cache` is read-only.
- Real-data benchmarks that touch Run 00700--00702 share a capacity-one benchmark group.
- No implementation is integrated before independent review.
- Algorithm-path changes require a `RecordsPlugin` version update under repository policy.

## Done when

- Targeted and boundary tests cover complete windows, cross-window events, oversized events,
  truncated tails, empty files, and the legacy `iter_waves()` compatibility path.
- The single-file sample, full Run 00700, and Runs 00700--00702 comparison preserve exact
  formal outputs and report wall, CPU, RSS, I/O, part count, and scratch amplification.
- The selected parallel configuration obeys a global worker/RSS/I/O budget and does not stack
  unbounded run-level and file-level concurrency.
- Required plugin, schema, documentation, performance, and handoff gates pass.
- Task-owned large temporary data is removed after evidence is preserved.
