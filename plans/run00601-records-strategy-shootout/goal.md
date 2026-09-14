# Run 00601 records strategy shootout

Compare three independent records-build implementations against one frozen
Run 00601 baseline without changing the formal `records` or `wave_pool`
contract.

## Frozen inputs

- Base: `0840ed9de67f7c59eeaf4285db399d475cdfd4e4`
- Data: `/mnt/data/TPC/run7_Xe/00601`
- Baseline evidence: `/tmp/wa-run00601-performance-g1/baseline/`
- Records SHA-256: `9e29a985a5ec2d8fa2a265c4859b8152cf08751161e724e0c1907af5153306e7`
- Wave-pool SHA-256: `424d1015398e519ff129099425eded180746dac080b0791fa96b04b86ff7cce9`
- Primary same-sampler records-only wall: `245.502700 s`
- Primary same-sampler incremental process-tree RSS: `12241170432 B`
- Context-only full-chain records wall: `234.6442048990284 s`
- Context-only full-chain incremental process-tree RSS: `46655692800 B`

All candidate speedup and RSS decisions use the primary records-only baseline;
the full-chain values are retained only as provenance and must not be mixed into
the ranking.

## Strategies

1. Stable original order: preserve a monotonic source-sequence key through
   part creation and exploit it as the final stable tie-break, eliminating
   redundant global ordering/copy work without changing canonical bytes.
2. Keep the 10k layout: retain the historical effective 10,000-wave V1725
   partition and wave offsets, while optimizing only the stable records merge.
3. Canonical chunked aggregation/copy: compute the existing canonical
   permutation exactly, then materialize records in bounded chunks so peak
   memory and duplicate whole-array copies are reduced.

Each executor must keep a Python/NumPy oracle or direct comparison path, cover
empty and tie-heavy inputs, and stop a candidate immediately if either formal
hash differs. Real-data benchmarks use task-local caches and the shared
`benchmark-run00601` lock. No candidate may be integrated by an executor or
reviewer.

## Recommendation rule

The reviewer ranks only byte-exact candidates. A recommendation requires a
three-run median and range, RSS within baseline +5%, scoped tests, and a written
complexity/compatibility assessment. If no candidate is clearly better, the
reviewer recommends no integration.

## Generation 2: Strategy 1 controlled rework

The first blocking review selected Strategy 1 as the only rework candidate.
Round 1 keeps its merge algorithm unchanged, synchronizes the site-model
records-version fixture with the intentional `0.15.0` lineage bump, and runs
three new clean-commit full measurements under the existing shared lock. Each
run uses a fresh task-local cache and records fallback status. Historical and
new evidence remain separate; no outlier may be discarded or replaced. The
independent reviewer must reject integration unless exact hashes, the 20% wall
gate, RSS +5% guardrail, and range/median <=10% all pass.

## Generation 3: final merge-I/O rework

Round 1 fixed the site-model lineage fixture but failed wall and stability.
The final allowed round may change only the measured records-final or wave-pool
concatenation I/O path. It must first demonstrate lower copied/flushed bytes or
representative-stage time while preserving the stable source-order contract and
formal hashes. If that screening does not show a gain, stop without three more
full runs. If it does, commit first and run exactly three new clean-commit
measurements; no sample replacement, baseline change, or threshold relaxation
is allowed.
