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

- 插件总数：17
- 类别数：8

## Plugin Table

| Provides | Plugin | Depends On | Output Kind | Version |
|----------|--------|------------|-------------|---------|
| [`basic_features`](basic_features.md) | `BasicFeaturesPlugin` | - | `structured_array` | `3.7.0` |
| [`cache_analysis`](cache_analysis.md) | `CacheAnalysisPlugin` | - | `unknown` | `0.1.0` |
| [`df`](df.md) | `DataFramePlugin` | - | `unknown` | `1.7.0` |
| [`df_events`](df_events.md) | `GroupedEventsPlugin` | `df` | `unknown` | `0.0.0` |
| [`df_paired`](df_paired.md) | `PairedEventsPlugin` | `df_events` | `unknown` | `0.0.0` |
| [`filtered_waveforms`](filtered_waveforms.md) | `FilteredWaveformsPlugin` | `st_waveforms` | `structured_array` | `2.5.0` |
| [`hit`](hit.md) | `HitFinderPlugin` | - | `structured_array` | `2.5.0` |
| [`hit_grouped`](hit_grouped.md) | `HitGroupedPlugin` | `hit_merged` | `unknown` | `0.3.0` |
| [`hit_merged`](hit_merged.md) | `HitMergePlugin` | `hit_threshold` | `structured_array` | `0.6.0` |
| [`hit_merged_components`](hit_merged_components.md) | `HitMergedComponentsPlugin` | `hit_merge_clusters`, `hit_merged` | `structured_array` | `0.1.0` |
| [`hit_threshold`](hit_threshold.md) | `ThresholdHitPlugin` | - | `structured_array` | `0.10.0` |
| [`raw_files`](raw_files.md) | `RawFileNamesPlugin` | - | `unknown` | `0.0.2` |
| [`records`](records.md) | `RecordsPlugin` | `raw_files` | `structured_array` | `0.8.0` |
| [`s1_s2`](s1_s2.md) | `S1S2ClassifierPlugin` | `waveform_width`, `basic_features` | `structured_array` | `0.3.0` |
| [`st_waveforms`](st_waveforms.md) | `WaveformsPlugin` | - | `structured_array` | `0.9.0` |
| [`waveform_width`](waveform_width.md) | `WaveformWidthPlugin` | - | `structured_array` | `2.2.0` |
| [`waveform_width_integral`](waveform_width_integral.md) | `WaveformWidthIntegralPlugin` | - | `structured_array` | `2.5.0` |

## By Category

### 数据加载

- [`raw_files`](raw_files.md): Scan the data directory and group raw CSV files by channel number.

### 波形处理

- [`filtered_waveforms`](filtered_waveforms.md): Apply filtering to waveforms using Butterworth or Savitzky-Golay filters.
- [`st_waveforms`](st_waveforms.md): Extract waveforms from raw CSV files and structure them into NumPy structured arrays.
- [`waveform_width`](waveform_width.md): Calculate rise/fall time based on peak detection results.
- [`waveform_width_integral`](waveform_width_integral.md): Event-wise integral quantile width using st_waveforms or filtered_waveforms.

### 特征提取

- [`basic_features`](basic_features.md): Compute basic height, amplitude, and area features from waveform data.
- [`hit`](hit.md): Detect peaks in waveforms and extract peak features.
- [`hit_grouped`](hit_grouped.md): Group merged hits across channels into event-level coincidence windows.
- [`hit_merged`](hit_merged.md): Merge nearby threshold hits per channel with time-gap and max-width constraints.
- [`hit_merged_components`](hit_merged_components.md): Return the component hit indices for each merged hit cluster.
- [`hit_threshold`](hit_threshold.md): Threshold-only hit detector with THRESHOLD_HIT_DTYPE output.

### 事件分析

- [`df_events`](df_events.md): Group events across channels within a configurable time window.
- [`df_paired`](df_paired.md): Pair grouped events across channels for coincidence analysis.

### 数据导出

- [`df`](df.md): Build the initial single-channel events DataFrame.

### 缓存分析

- [`cache_analysis`](cache_analysis.md): Analyze cache usage and return summary, entries, and diagnostics.

### 记录处理

- [`records`](records.md): Build records (event index table) from raw_files.

### 其他

- [`s1_s2`](s1_s2.md): Classify peaks into S1/S2 using width/area/height ranges.
