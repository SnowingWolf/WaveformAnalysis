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
