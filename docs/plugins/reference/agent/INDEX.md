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

- 插件总数：16
- 类别数：8

## Plugin Table

| Provides | Plugin | Depends On | Output Kind | Version |
|----------|--------|------------|-------------|---------|
| [`basic_features`](basic_features.md) | `BasicFeaturesPlugin` | - | `structured_array` | `3.3.0` |
| [`cache_analysis`](cache_analysis.md) | `CacheAnalysisPlugin` | - | `unknown` | `0.1.0` |
| [`df`](df.md) | `DataFramePlugin` | `st_waveforms`, `basic_features` | `unknown` | `1.1.0` |
| [`df_events`](df_events.md) | `GroupedEventsPlugin` | `df` | `unknown` | `0.0.0` |
| [`df_paired`](df_paired.md) | `PairedEventsPlugin` | `df_events` | `unknown` | `0.0.0` |
| [`events`](events.md) | `EventsPlugin` | - | `structured_array` | `2.0.0` |
| [`events_df`](events_df.md) | `EventFramePlugin` | `events` | `unknown` | `0.3.0` |
| [`events_grouped`](events_grouped.md) | `EventsGroupedPlugin` | `events_df` | `unknown` | `0.1.0` |
| [`filtered_waveforms`](filtered_waveforms.md) | `FilteredWaveformsPlugin` | `st_waveforms` | `structured_array` | `2.4.0` |
| [`hit`](hit.md) | `HitFinderPlugin` | - | `structured_array` | `2.2.0` |
| [`raw_files`](raw_files.md) | `RawFileNamesPlugin` | - | `unknown` | `0.0.2` |
| [`records`](records.md) | `RecordsPlugin` | `raw_files` | `structured_array` | `0.4.0` |
| [`s1_s2`](s1_s2.md) | `S1S2ClassifierPlugin` | `waveform_width`, `basic_features` | `structured_array` | `0.2.0` |
| [`st_waveforms`](st_waveforms.md) | `WaveformsPlugin` | - | `structured_array` | `0.5.0` |
| [`waveform_width`](waveform_width.md) | `WaveformWidthPlugin` | - | `structured_array` | `2.1.0` |
| [`waveform_width_integral`](waveform_width_integral.md) | `WaveformWidthIntegralPlugin` | - | `structured_array` | `2.1.0` |

## By Category

### 数据加载

- [`raw_files`](raw_files.md): Scan the data directory and group raw CSV files by channel number.

### 波形处理

- [`filtered_waveforms`](filtered_waveforms.md): Apply filtering to waveforms using Butterworth or Savitzky-Golay filters.
- [`st_waveforms`](st_waveforms.md): Extract waveforms from raw CSV files and structure them into NumPy structured arrays.
- [`waveform_width`](waveform_width.md): Calculate rise/fall time based on peak detection results.
- [`waveform_width_integral`](waveform_width_integral.md): Event-wise integral quantile width using st_waveforms or filtered_waveforms.

### 特征提取

- [`basic_features`](basic_features.md): Plugin to compute basic height/area features from structured waveforms.
- [`hit`](hit.md): Detect peaks in waveforms and extract peak features.

### 事件分析

- [`df_events`](df_events.md): Plugin to group events by time window.
- [`df_paired`](df_paired.md): Plugin to pair events across channels.
- [`events`](events.md): Provide event index data backed by the records bundle.
- [`events_df`](events_df.md): Build an events DataFrame from the events bundle.
- [`events_grouped`](events_grouped.md): Group events_df into multi-channel events by time window.

### 数据导出

- [`df`](df.md): Plugin to build the initial single-channel events DataFrame.

### 缓存分析

- [`cache_analysis`](cache_analysis.md): Analyze cache usage and return summary, entries, and diagnostics.

### 记录处理

- [`records`](records.md): Build records (event index table) from raw_files.

### 其他

- [`s1_s2`](s1_s2.md): Classify peaks into S1/S2 using width/area/height ranges.
