# WaveformAnalysis Agent Plugin Reference

> 面向 agent 的插件执行与改动参考。保持与 `builtin/auto` 分离维护。

## Usage

```bash
# 生成全部 agent 插件文档
waveform-docs generate plugins-agent -o docs/plugins/reference/agent/

# 仅生成单个插件文档
waveform-docs generate plugins-agent --plugin raw_files
```

## Summary

- 插件总数：35
- 类别数：9

## Plugin Table

| Provides | Plugin | Depends On | Output Kind | Version |
|----------|--------|------------|-------------|---------|
| [`basic_features`](basic_features.md) | `BasicFeaturesPlugin` | - | `structured_array` | `4.1.0` |
| [`cache_analysis`](cache_analysis.md) | `CacheAnalysisPlugin` | - | `dict` | `0.1.0` |
| [`df`](df.md) | `DataFramePlugin` | - | `dataframe` | `1.7.0` |
| [`df_events`](df_events.md) | `GroupedEventsPlugin` | `df` | `dataframe` | `0.0.1` |
| [`df_paired`](df_paired.md) | `PairedEventsPlugin` | `df_events` | `dataframe` | `0.0.1` |
| [`events`](events.md) | `EventPlugin` | `s1_s2_pairs`, `position_reconstruction` | `structured_array` | `0.0.1` |
| [`filtered_waveforms`](filtered_waveforms.md) | `FilteredWaveformsPlugin` | `st_waveforms` | `structured_array` | `3.0.0` |
| [`hit`](hit.md) | `HitFinderPlugin` | - | `structured_array` | `3.0.0` |
| [`hit_grouped`](hit_grouped.md) | `HitGroupedPlugin` | `hit_merged`, `hit_merged_components`, `hit_threshold` | `dataframe` | `0.5.0` |
| [`hit_merge_clusters`](hit_merge_clusters.md) | `HitMergeClustersPlugin` | `hit_merged`, `hit_threshold` | `structured_array` | `1.1.0` |
| [`hit_merged`](hit_merged.md) | `HitMergePlugin` | `hit_threshold` | `structured_array` | `2.1.0` |
| [`hit_merged_components`](hit_merged_components.md) | `HitMergedComponentsPlugin` | `hit_merged`, `hit_threshold` | `structured_array` | `1.1.0` |
| [`hit_merged_features`](hit_merged_features.md) | `HitMergedFeaturesPlugin` | - | `structured_array` | `0.5.1` |
| [`hit_threshold`](hit_threshold.md) | `ThresholdHitPlugin` | - | `structured_array` | `1.2.0` |
| [`peak_classification`](peak_classification.md) | `PeakClassificationPlugin` | `peaks` | `structured_array` | `1.2.1` |
| [`peaklet_channels`](peaklet_channels.md) | `PeakletChannelsPlugin` | `peaklets`, `peaklet_components`, `hit_merged_features`, `peaklet_features` | `structured_array` | `1.0.1` |
| [`peaklet_components`](peaklet_components.md) | `PeakletComponentsPlugin` | `hit_merged` | `structured_array` | `1.4.0` |
| [`peaklet_features`](peaklet_features.md) | `PeakletFeaturesPlugin` | `peaklet_waveforms`, `peaklet_waveform_pool`, `peaklets` | `structured_array` | `4.1.0` |
| [`peaklet_waveform_pool`](peaklet_waveform_pool.md) | `PeakletWaveformPoolPlugin` | `peaklet_waveforms` | `array` | `2.0.0` |
| [`peaklet_waveforms`](peaklet_waveforms.md) | `PeakletWaveformPlugin` | - | `structured_array` | `1.4.0` |
| [`peaklets`](peaklets.md) | `PeakletPlugin` | `hit_merged`, `peaklet_components` | `structured_array` | `1.2.0` |
| [`peaks`](peaks.md) | `PeaksPlugin` | `peaklets`, `peaklet_features`, `peaklet_channels` | `structured_array` | `4.0.1` |
| [`position_reconstruction`](position_reconstruction.md) | `PositionReconstructionPlugin` | `s1_s2_pairs` | `structured_array` | `0.2.1` |
| [`raw_files`](raw_files.md) | `RawFileNamesPlugin` | - | `list` | `0.0.2` |
| [`records`](records.md) | `RecordsPlugin` | - | `structured_array` | `0.14.1` |
| [`records_asymmetry_mask`](records_asymmetry_mask.md) | `RecordsAsymmetryMaskPlugin` | `records`, `wave_pool` | `array` | `0.2.0` |
| [`records_detector_mask`](records_detector_mask.md) | `RecordsDetectorMaskPlugin` | `records`, `records_asymmetry_mask` | `array` | `0.1.0` |
| [`records_veto_mask`](records_veto_mask.md) | `RecordsVetoMaskPlugin` | `records`, `records_asymmetry_mask` | `array` | `0.1.0` |
| [`s1_s2_pair_candidates`](s1_s2_pair_candidates.md) | `S1S2PairCandidatesPlugin` | `peak_classification`, `peaks` | `structured_array` | `0.1.3` |
| [`s1_s2_pairs`](s1_s2_pairs.md) | `S1S2PairSelectionPlugin` | `s1_s2_pair_candidates` | `structured_array` | `0.2.0` |
| [`st_waveforms`](st_waveforms.md) | `WaveformsPlugin` | - | `structured_array` | `0.10.0` |
| [`wave_pool`](wave_pool.md) | `WavePoolPlugin` | - | `array` | `0.14.1` |
| [`wave_pool_filtered`](wave_pool_filtered.md) | `WavePoolFilteredPlugin` | `records`, `wave_pool` | `array` | `3.0.0` |
| [`waveform_width`](waveform_width.md) | `WaveformWidthPlugin` | - | `structured_array` | `3.0.0` |
| [`waveform_width_integral`](waveform_width_integral.md) | `WaveformWidthIntegralPlugin` | - | `structured_array` | `2.7.0` |

## By Category

### 数据加载

- [`raw_files`](raw_files.md): Scan the data directory and group raw CSV files by channel number.
### 波形处理

- [`filtered_waveforms`](filtered_waveforms.md): Apply filtering to waveforms using Butterworth or Savitzky-Golay filters.
- [`st_waveforms`](st_waveforms.md): Extract waveforms from raw CSV files and structure them into NumPy structured arrays.
- [`wave_pool`](wave_pool.md): Build wave_pool from the shared internal records bundle.
- [`wave_pool_filtered`](wave_pool_filtered.md): Build filtered wave_pool from records-backed raw waveforms.
- [`waveform_width`](waveform_width.md): Calculate rise/fall time based on peak detection results.
- [`waveform_width_integral`](waveform_width_integral.md): Event-wise integral quantile width using st_waveforms or filtered_waveforms.
### 峰构建

- [`peaklet_channels`](peaklet_channels.md): Aggregate hit_merged_features into per-peaklet channel contribution rows.
- [`peaklet_components`](peaklet_components.md): Return per-peaklet component hit_merged indices.
- [`peaklet_features`](peaklet_features.md): Compute peaklet waveform features from ragged signal pools.
- [`peaklet_waveform_pool`](peaklet_waveform_pool.md): Return the flattened float32 signal pool paired with peaklet_waveforms. Configure waveform construction on peaklet_waveforms.
- [`peaklet_waveforms`](peaklet_waveforms.md): Build peaklet waveform index rows from records-backed hit_merged samples. Supports cross-record hits via component expansion.
- [`peaklets`](peaklets.md): Build lightweight cross-channel peaklets from hit_merged intervals.
### 特征提取

- [`basic_features`](basic_features.md): Compute basic height, amplitude, area, and max-abs-diff features from waveform data.
- [`hit`](hit.md): Detect peaks in waveforms and extract peak features.
- [`hit_grouped`](hit_grouped.md): Group merged hits across channels into event-level coincidence windows.
- [`hit_merge_clusters`](hit_merge_clusters.md): Export cluster membership rows using the authoritative hit_merged configuration.
- [`hit_merged`](hit_merged.md): Merge nearby threshold hits per channel with time-gap and max-width constraints.
- [`hit_merged_components`](hit_merged_components.md): Return per-cluster component hit indices for hit_merged rows.
- [`hit_merged_features`](hit_merged_features.md): Compute per-hit_merged local waveform features from records-backed samples.
- [`hit_threshold`](hit_threshold.md): Threshold-only hit detector with THRESHOLD_HIT_DTYPE output.
- [`peak_classification`](peak_classification.md): Classify peaks into S1/S2 using multi-dimensional features.
- [`peaks`](peaks.md): Build final peaks table from peaklets and waveform-derived features.
### 事件分析

- [`df_events`](df_events.md): Group events across channels within a configurable time window.
- [`df_paired`](df_paired.md): Pair grouped events across channels for coincidence analysis.
- [`events`](events.md): Complete event reconstruction from S1-S2 pairs and position
- [`s1_s2_pair_candidates`](s1_s2_pair_candidates.md): Generate all physically allowed S1-S2 pairing candidates
- [`s1_s2_pairs`](s1_s2_pairs.md): Select best S1-S2 pairs from candidates
### 数据导出

- [`df`](df.md): Build the initial single-channel events DataFrame.
### 缓存分析

- [`cache_analysis`](cache_analysis.md): Analyze cache usage and return summary, entries, and diagnostics.
### 记录处理

- [`records`](records.md): Build records (event index table) from the shared internal records bundle.
- [`records_asymmetry_mask`](records_asymmetry_mask.md): Bool mask for waveform asymmetry selection.
- [`records_detector_mask`](records_detector_mask.md): Bool mask for detector-channel records after channel-role splitting.
- [`records_veto_mask`](records_veto_mask.md): Bool mask for veto-channel records after channel-role splitting.
### 其他

- [`position_reconstruction`](position_reconstruction.md): Reconstruct 3D position from S1-S2 pairs using vectorized CoG method
