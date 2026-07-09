# Plan: hit_merged / features / peaklet Responsibility Boundary

## Metadata

```yaml
task_id: hit-merged-peaklet-responsibility
status: todo
route: refactor
owner_role: planner
created_at: 2026-06-05
last_update: 2026-07-09
```

---

## Goal

Clarify the responsibility boundary between `hit_threshold`, `hit_merged`, feature extraction, and `peaklet`.

The goal is to avoid duplicated computation and prevent low-level plugins from accumulating high-level physics features.

---

## Scope In

This task may modify:

* planning documents
* plugin responsibility documentation
* future implementation plan
* tests only after the design is agreed

---

## Scope Out

This task must not immediately modify:

* hit finding logic
* merge logic
* peaklet implementation
* output dtype definitions
* existing analysis notebooks

Implementation should be done in a later executor task.

---

## Proposed Responsibility Boundary

| Layer | Input | Output | Responsibility |
| --- | --- | --- | --- |
| records | raw waveform data | waveform records | Store waveform and metadata |
| hit_threshold | records | hits | Find threshold crossings only |
| hit_merged | hits | merged hit clusters | Merge hits close in time |
| hit_merged_features | merged hits + records | feature table | Compute area, height, rise_time, fall_time, quantiles |
| peaklet | merged hits / features | peak-like objects | Higher-level aggregation and classification |

---

## Current State

Known facts:

* `hit_threshold` should remain low-level.
* `hit_merged` should primarily merge nearby hits.
* `rise_time`, `fall_time`, `quantile`, and `area per channel` are better placed in a feature layer.
* `peaklet` may depend on features, but features should not depend on peaklet.

---

## Done

Already completed:

* Initial boundary proposal.

---

## Doing

Currently being worked on:

* Nothing yet.

---

## Todo

Remaining work:

* [ ] Inspect current `hit_threshold` output fields.
* [ ] Inspect current `hit_merged` output fields.
* [ ] Inspect current `basic_features` and peaklet dependencies.
* [ ] Decide exact plugin names.
* [ ] Decide output dtype ownership.
* [ ] Decide whether `hit_merged_features` is a new plugin or an extension of existing feature logic.
* [ ] Write a concrete implementation plan before modifying code.

Optimization follow-ups:

* [ ] Treat `hit_merge_clusters` as the shared membership source for `hit_merged` and `hit_merged_components`, so canonical cluster rows are not recomputed independently.
* [ ] Evaluate replacing per-channel `hit_merged` grouping plus per-group sort with a single sorted scan over `(board, channel, abs_start)` while preserving the no-cross-channel merge contract.
* [ ] Keep `hit_merged_components.validate_components` disabled by default; use it only for diagnostics or strict validation gates.
* [ ] Convert `PeakletComponentsPlugin` from Numba result -> Python `list[list[int]]` -> structured rows to a flat/CSR-style output path.
* [ ] Vectorize or Numba-accelerate `PeakletPlugin._compute_peaklets()` summary construction, including `time_start`, `time_end`, `n_hits`, and unique `(board, channel)` counting.
* [ ] Convert the single-record `peaklet_waveforms` path to a two-pass preallocated pool fill, matching the cross-record path's allocation pattern.
* [ ] Make Numba fallback visibility explicit for performance runs by documenting or enforcing `peaklet_waveforms.debug_numba=True` / `log_waveform_diagnostics=True` in benchmarks.
* [ ] Review `PeakletWaveformPoolPlugin` and `PeakletWaveformPlugin` shared construction so both products cannot accidentally diverge in cache/config behavior.
* [ ] Treat multiprocessing cross-record fallback as low priority until profiling shows array-copy overhead is outweighed by batch size.

---

## Required Gates

The design is not ready for implementation until:

* [ ] Plugin responsibility table is accepted.
* [ ] Input / output dtypes are specified.
* [ ] Backward compatibility strategy is specified.
* [ ] Tests to protect existing behavior are identified.
* [ ] `INDEX.md` is updated.
* [ ] `active.yaml` is updated.

---

## Handoff Next Action

Do not implement this plan yet. First finish P0 and P1. Then return to this plan as a design/refactor task.

---

## Execution Log

### 2026-06-05

* Changed: none yet.
* Tests: not run yet.
* Result: plan initialized.
* Remaining issues: waiting for earlier priorities.

### 2026-07-09

* Changed: added optimization follow-ups based on current `hit_merge.py` and `peaklets.py` implementation review.
* Tests: not run; planning-only documentation update.
* Result: backlog now distinguishes current implemented optimizations from remaining follow-up work.
* Remaining issues: implementation still deferred until the responsibility boundary and dtype ownership are accepted.
