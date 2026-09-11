# v2.0.0 generation 4 validation

Plan SHA256: `3514493e01ff58ba51ff3cf4d948a695c80003d4852a18ae97e38856192158e4`

## Local gates

- Python 3.12 fast testpaths: `1779 passed, 2 skipped, 15 deselected`.
- Python 3.12 slow layer: `15 passed, 1781 deselected`.
- Full-repository Black and Ruff: PASS.
- Plugin dependency check: 37 bundles, 153 from-import checks, 0 missing shims.
- Generated plugin references: 37 builtin pages and 37 agent pages, no drift.
- Agent documentation rendering and document synchronization: PASS with
  `WAVEFORM_PYTHON=/home/wxy/anaconda3/envs/pyroot-kernel/bin/python`.
- Document anchors: 0 errors and 0 warnings against the v1.5.0 baseline.
- Schema compatibility smoke: PASS; `raw_files=2`, `st_waveforms=24`, `hit=0`,
  `df=24`, `events=12`.
- `release_artifact_sync`: PASS for version/changelog, generated docs, document
  synchronization/anchors, key tests, and performance; no skip flags were used.

## Performance baseline

Baseline: annotated tag `v1.5.0`, resolved commit
`715c8ce35a93d04f7641b4b149e56b7be6ea01e4`.

The benchmark uses the same fresh subprocess path for baseline and candidate,
separates timing from peak-memory measurement, validates output contracts, and uses
`2 x 1200 x 512 = 1,228,800` synthetic samples. Five repeats and the fixed limits
of 10% for time and 15% for peak memory were retained. The independent root run
reported:

- `df`: time -0.84%, memory +0.06%, 2400 rows.
- `df_events`: time +0.10%, memory +0.02%, 1200 rows.
- `hit`: time -2.17%, memory -4.27%, 2400 rows.
- `hit_threshold`: time -2.54%, memory -4.25%, 2400 rows.
- `st_waveforms`: time -2.73%, memory +0.08%, 2400 rows.

The complete release synchronization rerun also passed all five targets.

## Documentation build

External run:
`/tmp/wa-release-v200-docs-g4/runs/release-v200-g4-root-20260911`.

- `npm ci --ignore-scripts`: PASS.
- TypeScript/Vitest check: PASS.
- Next.js static build: PASS.
- Input fingerprint:
  `ba60d222c49e872de1fb5b2610bbd55b387806c605eaec2cbb122418fc3bd5c1`.
- Site model SHA256:
  `a10f5a31d59500020f2def686e88df18459779256bd29626dcd77f1c56ba81b0`.
- Site manifest SHA256:
  `46702075f8e471c3033dcd47284d521cd3f881b14910bfeb38868b9dffd3a0c4`.
- External and packaged site model/manifest hashes match.

## Reviewed compatibility risk

The impact scanner reports 74 high-risk raw class changes across 166 plugin files.
Manual review groups these into plugin-bundle relocations represented as paired class
removals/additions, plus the documented energy reconstruction placeholder. The schema
smoke has no contract issue. User-visible removals and changed time/fall-time semantics
are listed in `CHANGELOG.md` and `docs/releases/v2.0.0.md`.

## Remaining release gates

- GitHub Python 3.10/3.11/3.12 and slow-test jobs for the exact candidate commit.
- GitHub documentation and pull-request workflow checks for the exact candidate.
- Wheel and sdist rebuilt from the exact candidate commit, independent install smoke,
  checksums, annotated tag, GitHub Release publication, and remote asset verification.
