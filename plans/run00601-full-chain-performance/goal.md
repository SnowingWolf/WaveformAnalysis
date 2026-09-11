# Run 00601 full-chain performance goal

Optimize the Run 00601 processing chain against a fresh baseline produced from
`/mnt/data/TPC/run7_Xe/00601`, while preserving every public data-product byte
and cache-lineage contract.

## Blocking outcomes

- `records`: median wall-time improvement of at least 20%.
- `hit_merged` plus `hit_merged_components`: combined median wall-time
  improvement of at least 40%.
- `peaklet_waveforms`: median wall-time improvement of at least 20%.
- The declared output set must preserve dtype, shape, row order, and SHA-256.
- Candidate process-tree peak RSS must not exceed baseline by more than 5%.
- A candidate is measured three times; range divided by median must be at most
  10%.
- Only an independently reviewed, scoped commit may be integrated. Each failed
  branch has at most two rework rounds and the target is never relaxed.

## Execution boundaries

- Base revision: `84bd5a85378e4181544ae81111395cb8efc5c0f8`.
- Every executor and reviewer uses its own Git worktree under
  `/srv/devspace/worktrees/`.
- All task-created caches, logs, manifests, and benchmark reports live below
  `/tmp/wa-run00601-performance-g1/`; production `_cache` is read-only.
- Full Run 00601 benchmarks share the `benchmark-run00601` concurrency group
  with capacity one. Synthetic, slice, and direct-kernel checks may run in
  parallel when they do not load the NFS dataset.
- Without privileged page-cache eviction, evidence is labelled
  `cold process/current page-cache state`.
- Streaming hashes are used for large artifacts; whole-product memmaps are not
  scanned in one process.

## Required evidence

Each executor/reviewer records the exact base and candidate SHA, command,
environment, configuration, lineage/cache keys, wall time, process-tree RSS,
hash manifest, cache-hit behavior, changed paths, tests, and residual risks.
Final QA runs the integrated full-chain candidate three times, followed by a
fresh-process persisted-cache check and all strict repository gates.
