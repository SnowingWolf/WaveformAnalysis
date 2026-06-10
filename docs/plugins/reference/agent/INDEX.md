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

- 插件总数：29
- 类别数：8

## Plugin Table

| Provides | Plugin | Depends On | Output Kind | Version |
|----------|--------|------------|-------------|---------|
| [`basic_features`](basic_features.md) | `BasicFeaturesPlugin` | - | `structured_array` | `4.1.0` |
| [`cache_analysis`](cache_analysis.md) | `CacheAnalysisPlugin` | - | `unknown` | `0.1.0` |
| [`df`](df.md) | `DataFramePlugin` | - | `unknown` | `1.7.0` |
| [`df_events`](df_events.md) | `GroupedEventsPlugin` | `df` | `unknown` | `0.0.0` |
| [`df_paired`](df_paired.md) | `PairedEventsPlugin` | `df_events` | `unknown` | `0.0.0` |
| [`filtered_waveforms`](filtered_waveforms.md) | `FilteredWaveformsPlugin` | `st_waveforms` | `structured_array` | `3.0.0` |
| [`hit`](hit.md) | `HitFinderPlugin` | - | `structured_array` | `3.0.0` |
| [`hit_grouped`](hit_grouped.md) | `HitGroupedPlugin` | `hit_merged`, `hit_merged_components`, `hit_threshold` | `unknown` | `0.5.0` |
| [`hit_merge_clusters`](hit_merge_clusters.md) | `HitMergeClustersPlugin` | `hit_merged`, `hit_threshold` | `structured_array` | `1.1.0` |
| [`hit_merged`](hit_merged.md) | `HitMergePlugin` | `hit_threshold` | `structured_array` | `1.2.0` |
| [`hit_merged_components`](hit_merged_components.md) | `HitMergedComponentsPlugin` | `hit_merged`, `hit_threshold` | `structured_array` | `1.1.0` |
| [`hit_merged_features`](hit_merged_features.md) | `HitMergedFeaturesPlugin` | `hit_merged`, `hit_merged_components`, `hit_threshold`, `records`, `wave_pool` | `structured_array` | `0.4.0` |
| [`hit_threshold`](hit_threshold.md) | `ThresholdHitPlugin` | - | `structured_array` | `1.1.0` |
| [`peaklet_channels`](peaklet_channels.md) | `PeakletChannelsPlugin` | `peaklets`, `peaklet_components`, `hit_merged_features`, `peaklet_features` | `structured_array` | `1.0.0` |
| [`peaklet_components`](peaklet_components.md) | `PeakletComponentsPlugin` | `peaklets`, `hit_merged` | `structured_array` | `1.0.0` |
| [`peaklet_features`](peaklet_features.md) | `PeakletFeaturesPlugin` | `peaklet_waveforms`, `peaklet_waveform_pool`, `peaklets` | `structured_array` | `3.0.1` |
| [`peaklet_waveform_pool`](peaklet_waveform_pool.md) | `PeakletWaveformPoolPlugin` | `peaklets`, `peaklet_components`, `hit_merged`, `records`, `wave_pool` | `array` | `1.0.0` |
| [`peaklet_waveforms`](peaklet_waveforms.md) | `PeakletWaveformPlugin` | `peaklets`, `peaklet_components`, `hit_merged`, `records`, `wave_pool` | `structured_array` | `1.0.0` |
| [`peaklets`](peaklets.md) | `PeakletPlugin` | `hit_merged` | `structured_array` | `1.0.0` |
| [`peaks`](peaks.md) | `PeaksPlugin` | `peaklets`, `peaklet_features`, `peaklet_channels` | `structured_array` | `3.0.0` |
| [`raw_files`](raw_files.md) | `RawFileNamesPlugin` | - | `unknown` | `0.0.2` |
| [`records`](records.md) | `RecordsPlugin` | - | `structured_array` | `0.13.0` |
| [`records_asymmetry_mask`](records_asymmetry_mask.md) | `RecordsAsymmetryMaskPlugin` | `records`, `wave_pool` | `array` | `0.1.0` |
| [`s1_s2`](s1_s2.md) | `S1S2ClassifierPlugin` | `waveform_width`, `basic_features` | `structured_array` | `0.4.0` |
| [`st_waveforms`](st_waveforms.md) | `WaveformsPlugin` | - | `structured_array` | `0.10.0` |
| [`wave_pool`](wave_pool.md) | `WavePoolPlugin` | - | `array` | `0.13.0` |
| [`wave_pool_filtered`](wave_pool_filtered.md) | `WavePoolFilteredPlugin` | `records`, `wave_pool` | `array` | `3.0.0` |
| [`waveform_width`](waveform_width.md) | `WaveformWidthPlugin` | - | `structured_array` | `3.0.0` |
| [`waveform_width_integral`](waveform_width_integral.md) | `WaveformWidthIntegralPlugin` | - | `structured_array` | `2.7.0` |

## By Category

### 数据加载

- [`raw_files`](raw_files.md): Scan the data directory and group raw CSV files by channel number.
### 波形处理

- [`filtered_waveforms`](filtered_waveforms.md): Apply filtering to waveforms using Butterworth or Savitzky-Golay filters.
- [`peaklet_waveform_pool`](peaklet_waveform_pool.md): Return flattened float32 peaklet waveform signal pool.
- [`peaklet_waveforms`](peaklet_waveforms.md): Build peaklet waveform index rows from records-backed hit_merged samples.
- [`st_waveforms`](st_waveforms.md): Extract waveforms from raw CSV files and structure them into NumPy structured arrays.
- [`wave_pool`](wave_pool.md): Build wave_pool from the shared internal records bundle.
- [`wave_pool_filtered`](wave_pool_filtered.md): Build filtered wave_pool from records-backed raw waveforms.
- [`waveform_width`](waveform_width.md): Calculate rise/fall time based on peak detection results.
- [`waveform_width_integral`](waveform_width_integral.md): Event-wise integral quantile width using st_waveforms or filtered_waveforms.
### 特征提取

- [`basic_features`](basic_features.md): Compute basic height, amplitude, area, and max-abs-diff features from waveform data.
- [`hit`](hit.md): Detect peaks in waveforms and extract peak features.
- [`hit_grouped`](hit_grouped.md): Group merged hits across channels into event-level coincidence windows.
- [`hit_merge_clusters`](hit_merge_clusters.md): Export cluster membership rows using the authoritative hit_merged configuration.
- [`hit_merged`](hit_merged.md): Merge nearby threshold hits per channel with time-gap and max-width constraints.
- [`hit_merged_components`](hit_merged_components.md): Return per-cluster component hit indices for hit_merged rows.
- [`hit_merged_features`](hit_merged_features.md): Compute per-hit_merged local waveform features from records-backed samples.
- [`hit_threshold`](hit_threshold.md): Threshold-only hit detector with THRESHOLD_HIT_DTYPE output.
- [`peaklet_channels`](peaklet_channels.md): Aggregate hit_merged_features into per-peaklet channel contribution rows.
- [`peaklet_components`](peaklet_components.md): Return per-peaklet component hit_merged indices.
- [`peaklet_features`](peaklet_features.md): Compute peaklet waveform features from ragged signal pools.
- [`peaklets`](peaklets.md): Build lightweight cross-channel peaklets from hit_merged intervals.
- [`peaks`](peaks.md): Build final peaks table from peaklets and waveform-derived features.
### 事件分析

- [`df_events`](df_events.md): Group events across channels within a configurable time window.
- [`df_paired`](df_paired.md): Pair grouped events across channels for coincidence analysis.
### 数据导出

- [`df`](df.md): Build the initial single-channel events DataFrame.
### 缓存分析

- [`cache_analysis`](cache_analysis.md): Analyze cache usage and return summary, entries, and diagnostics.
### 记录处理

- [`records`](records.md): Build records (event index table) from the shared internal records bundle.
- [`records_asymmetry_mask`](records_asymmetry_mask.md): Bool mask for waveform asymmetry selection.
### 其他

- [`s1_s2`](s1_s2.md): Classify peaks into S1/S2 using width/area/height ranges.
