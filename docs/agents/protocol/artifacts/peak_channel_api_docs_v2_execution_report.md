# execution_report

- task_id: peak-channel-api-docs-v2
- workflow_cost: strict
- executor_role: executor.config
- changed_paths: PeakChannelAccessor, position reconstruction caller, tests, demo, notebook, API documentation, site documentation source, and retire_compat artifacts
- actions_taken: removed the six legacy public methods and the partial-field fallback; added get_channels, a three-view plot dispatcher, PeakChannelDataUnavailableError, call-site migration, and explicit calculation documentation
- commands_run: targeted pytest, ruff, black, assess_change_impact, schema_compat_check smoke, site-web generation, doc sync, and doc anchor checks
- open_risks: callers outside this repository must migrate immediately; no compatibility alias remains by user decision
- requested_review_focus: verify public method removal, peaklet_channels validation, plot axes normalization, and generated page wording

## retire_compat Notes

- compat_items_removed: get_peak_channels, get_channel_waveform, get_peak_channel_data, batch_plot, plot_channel_comparison, plot_sum_vs_channels, and the hit_merged_features fallback
- compat_items_kept: get_sum_waveform and clear_waveform_cache
- migration_updates: position reconstruction, example, notebook, Markdown guide, site registry, and generated site
- gates_executed: targeted tests pass; ruff pass; black pass; impact pass; schema smoke pass; doc sync pass with two unrelated existing warnings; doc anchors pass with the same warnings
- not_executed_and_why: no full test suite; focused tests cover the changed Accessor, documentation generator, and position reconstruction caller
