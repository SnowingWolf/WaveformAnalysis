# compat_inventory

- task_id: peak-channel-api-docs-v2
- route: retire_compat
- inventory_scope: PeakChannelAccessor public Python API and per-channel feature fallback
- canonical_policy: public callers use get_channels, get_sum_waveform, and plot(view=...); internal code uses the canonical peaklet_channels product only

## compat_items

- compat_id: peak_channel_data_getters
  - kind: other
  - canonical_form: get_channels(peak_id, include_waveforms=False, pad=30)
  - legacy_form: get_peak_channels, get_peak_channel_data, get_channel_waveform
  - location: waveform_analysis/utils/peak_channel_accessor.py
  - runtime_surface: public_python_api
  - delete_action: remove
  - risk_level: medium
  - required_gates: targeted tests, doc_sync, doc_anchors, impact_assessed_if_needed, schema_checked_if_needed
  - migration_note: user explicitly approved immediate removal; component waveform access is now internal
  - review_decision: approved

- compat_id: peak_channel_plot_methods
  - kind: other
  - canonical_form: plot(peak_id, view=stacked|overlay|sum-comparison)
  - legacy_form: batch_plot, plot_channel_comparison, plot_sum_vs_channels
  - location: waveform_analysis/utils/peak_channel_accessor.py
  - runtime_surface: public_python_api
  - delete_action: remove
  - risk_level: medium
  - required_gates: targeted tests, doc_sync, doc_anchors, impact_assessed_if_needed
  - migration_note: user explicitly approved immediate removal; batch output moves to explicit caller loops
  - review_decision: approved

- compat_id: peaklet_channels_fallback
  - kind: fallback_path
  - canonical_form: complete peaklet_channels structured array
  - legacy_form: hit_merged plus hit_merged_features partial-field fallback
  - location: waveform_analysis/utils/peak_channel_accessor.py
  - runtime_surface: public_python_api
  - delete_action: remove
  - risk_level: medium
  - required_gates: targeted tests, schema_checked_if_needed, doc_sync
  - migration_note: user explicitly requires peaklet_channels; missing or invalid input now raises PeakChannelDataUnavailableError
  - review_decision: approved
