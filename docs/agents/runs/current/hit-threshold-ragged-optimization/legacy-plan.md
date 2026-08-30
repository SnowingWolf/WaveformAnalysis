# Plan: hit_threshold Ragged Records Optimization

## Metadata

```yaml
task_id: hit-threshold-ragged-optimization
status: todo
route: modify_plugin
owner_role: executor
created_at: 2026-06-05
last_update: 2026-06-05
```

---

## Goal

Improve `hit_threshold` performance for ragged records where waveforms have different lengths.

The main target is to avoid repeated high-overhead waveform access inside the record loop.

---

## Scope In

This task may modify:

* `hit_threshold` implementation
* internal waveform access strategy
* optional benchmark scripts or notebook snippets
* tests that compare old and new hit results

---

## Scope Out

This task must not modify:

* Context output behavior
* unrelated plugin interfaces
* hit field definitions unless strictly necessary
* physical threshold definitions
* peaklet logic
* hit_merged logic

---

## Current State

Known facts:

* Current records ragged hit search can be slow for large inputs.
* A 2M-record workload was observed to take around several minutes.
* Repeated calls like `rv.signals([rid])` inside a record loop are likely expensive.
* `RecordsView.wave_pool` is available.
* `records["wave_offset"]` and `records["event_length"]` should be treated as the stable source for waveform slicing.

---

## Done

Already completed:

* Identified the likely bottleneck: repeated per-record waveform extraction.
* Identified direct slicing strategy:

  ```python
  wave = wave_pool[offset: offset + length]
  ```

---

## Doing

Currently being worked on:

* Nothing yet. This plan is waiting for `get-data-output-unification` to finish.

---

## Todo

Remaining work:

* [ ] Inspect current `hit_threshold` implementation.
* [ ] Confirm field names used for waveform offsets and lengths.
* [ ] Replace repeated `rv.signals([rid])` access where safe.
* [ ] Add record-level prefilter:

  ```python
  if positive:
      if np.max(wave) < baseline + threshold:
          continue
  else:
      if np.min(wave) > baseline - threshold:
          continue
  ```

* [ ] Keep Python fallback.
* [ ] Add optional Numba path only if it improves performance and does not complicate behavior.
* [ ] Compare new and old hit outputs.
* [ ] Benchmark at multiple scales.

---

## Required Gates

The task is not complete until:

* [ ] New and old hit counts match for representative data.
* [ ] Key hit fields match:
  * `record_id`
  * `start`
  * `end`
  * `channel`
  * `board`
* [ ] Benchmark includes at least:
  * 2k records
  * 50k records
  * 500k records
* [ ] No unrelated plugin logic is modified.
* [ ] `INDEX.md` is updated.
* [ ] `active.yaml` is updated.

---

## Test / Verification Commands

```bash
pytest tests -k "hit_threshold or threshold"
```

Benchmark commands should be added after implementation.

---

## Handoff Next Action

Wait until `get-data-output-unification` is done. Then optimize waveform access in `hit_threshold` without changing physical definitions.

---

## Execution Log

### 2026-06-05

* Changed: none yet.
* Tests: not run yet.
* Result: plan initialized.
* Remaining issues: waiting for P0.
