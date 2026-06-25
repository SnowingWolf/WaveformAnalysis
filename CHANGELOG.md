# Changelog

## v1.3.0

This release builds on v1.2.0 with peak-channel access utilities, corrected
sum-waveform visualization, and new example workflows for channel inspection
and plotting.

### Highlights

- Added `PeakChannelAccessor` for structured per-channel peak inspection with
  lazy waveform loading and plotting helpers.
- Fixed `plot_peak_channels_with_sum` / `create_peak_plotter` to reuse the
  peaklet sum waveform instead of recomputing it from raw records.
- Added example scripts and docs for peak-channel access and sum-waveform
  comparison.

### Validation

- Release baseline: `v1.2.0`
- Required gates:
  - `python scripts/release_artifact_sync.py --base v1.2.0`
  - `python -m pytest tests/`

## v1.2.0

This release builds on v1.1.0 with peaklet classification improvements,
visualization utilities, DAQ/cache usability updates, and additional quality
documentation.

### Highlights

- Added and refined peaklet S1/S2 classification support, including channel role
  veto masks, save policy documentation, and corrected component configuration
  handling.
- Expanded peak and hit analysis helpers with `peak_id` alignment fixes,
  `hit_merged` timing fields, and waveform query utilities.
- Improved visualization workflows with optimized `corner_hist` execution,
  overlay/transparency support, flexible layout controls, and cut-line helpers.
- Enhanced DAQ and context observability with cache status display, time range
  filtering, row limits, plugin execution timing, and global execution config
  reporting.
- Added optimization and testing documentation for performance-sensitive
  workflows, and kept release performance gates aligned with the records-backed
  `hit_threshold` dependency chain.

### Validation

- Release baseline: `v1.1.0`
- Required gates:
  - `python scripts/release_artifact_sync.py --base v1.1.0`
  - `python -m pytest tests/`

## v1.1.0

This release focuses on records/v1725 processing performance, peaklet and peaks
plugin coverage, visualization utilities, and stricter release quality checks.

### Highlights

- Optimized v1725 records building with streaming part generation, run-scoped
  merge stages, controlled parallel merge execution, progress reporting, and
  profiler/debug metadata.
- Improved DAQ/v1725 overview scanning, records-backed data access, polarity
  application, and `records_view` signal fast paths for larger datasets.
- Expanded peaks and peaklet plugin support, including peaklet channel/features/
  waveforms plugins, waveform-backed peaklets, records asymmetry masks, and
  updated peak lineage features.
- Optimized hit merge and `hit_merged_features` execution paths with
  pre-allocation and Numba-backed hot paths where appropriate.
- Added lineage visualization fixes, statistical plotting utilities, and top
  level visualization exports.
- Strengthened agent workflow documentation, plugin version policy, generated
  plugin references, release gates, and regression test coverage.

### Validation

- Release baseline: `v1.0.0`
- Required gates:
  - `python scripts/release_artifact_sync.py --base v1.0.0`
  - `python -m pytest tests/`
