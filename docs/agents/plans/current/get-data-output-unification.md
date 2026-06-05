# Plan: get_data Output Unification

## Metadata

```yaml
task_id: get-data-output-unification
status: doing
route: modify_context
owner_role: executor
created_at: 2026-06-05
last_update: 2026-06-05
```

---

## Goal

Unify `ctx.get_data(..., output=...)` behavior across direct execution, memory cache, disk cache, and stream / chunk paths.

The output conversion should live at the Context API boundary as much as possible. Individual plugins should not be forced to implement output conversion themselves.

---

## Scope In

This task may modify:

* Context API output handling
* Small helper functions for output conversion
* Tests covering output modes
* Documentation related to get_data output behavior

---

## Scope Out

This task must not modify:

* `hit_threshold` physics logic
* `basic_features` physics logic
* `hit_merged` logic
* `peaklet` logic
* waveform threshold definitions
* detector-specific feature definitions
* broad plugin architecture

---

## Current State

Known facts:

* `get_data` has multiple return paths:
  * memory cache
  * disk cache
  * direct plugin execution
  * stream / chunk execution
* `OneTimeGenerator` mainly appears in stream execution.
* Current behavior may differ depending on which path produced the result.
* The desired output modes include:
  * `output="native"`
  * `output="array"`
  * `output="chunk_stream"`

---

## Done

Already completed:

* Initial return-path analysis.
* Decision: keep plugin `compute` contract unchanged.
* Decision: avoid large plugin-system refactor in this task.

---

## Doing

Currently being worked on:

* Implementing consistent `ctx.get_data(..., output=...)` behavior.

---

## Todo

Remaining work:

* [ ] Inspect current `get_data` implementation.
* [ ] Inspect memory cache return path.
* [ ] Inspect disk cache return path.
* [ ] Inspect direct execution return path.
* [ ] Inspect stream / chunk return path.
* [ ] Add or update output conversion helper.
* [ ] Add tests for `output="native"`.
* [ ] Add tests for `output="array"`.
* [ ] Add tests for `output="chunk_stream"`.
* [ ] Ensure unsafe conversion fails explicitly instead of silently returning the wrong type.
* [ ] Update this plan after execution.

---

## Required Gates

The task is not complete until:

* [ ] Relevant tests pass.
* [ ] Existing plugin compute behavior is not changed.
* [ ] Existing physical analysis logic is not changed.
* [ ] No unrelated files are modified.
* [ ] `INDEX.md` is updated.
* [ ] `active.yaml` is updated.

---

## Test / Verification Commands

```bash
pytest tests -k "get_data or context or output"
```

If this command is too broad or fails because of unrelated tests, run the most relevant narrower tests and record the exact commands.

---

## Handoff Next Action

The next Agent should first inspect Context output handling and implement P0 only. Do not start hit_threshold performance optimization until this plan is done.

---

## Execution Log

### 2026-06-05

* Changed: none yet.
* Tests: not run yet.
* Result: plan initialized.
* Remaining issues: implementation still pending.
