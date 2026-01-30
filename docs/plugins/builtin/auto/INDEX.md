# Built-in Plugins Index

> Auto-generated documentation for WaveformAnalysis built-in plugins.

## Summary

- **Total Plugins**: 16
- **Categories**: 7

## Quick Reference

| Plugin | Provides | Version | Category | Dependencies |
|--------|----------|---------|----------|--------------|
| [`BasicFeaturesPlugin`](basic_features.md) | `basic_features` | 0.0.0 | 特征提取 | - |
| [`CacheAnalysisPlugin`](cache_analysis.md) | `cache_analysis` | 0.1.0 | 缓存分析 | - |
| [`DataFramePlugin`](df.md) | `df` | 0.0.0 | 数据导出 | st_waveforms, basic_features |
| [`GroupedEventsPlugin`](df_events.md) | `df_events` | 0.0.0 | 事件分析 | df |
| [`PairedEventsPlugin`](df_paired.md) | `df_paired` | 0.0.0 | 事件分析 | df_events |
| [`EventsPlugin`](events.md) | `events` | 0.1.0 | 事件分析 | - |
| [`EventFramePlugin`](events_df.md) | `events_df` | 0.1.0 | 事件分析 | events |
| [`EventsGroupedPlugin`](events_grouped.md) | `events_grouped` | 0.1.0 | 事件分析 | events_df |
| [`FilteredWaveformsPlugin`](filtered_waveforms.md) | `filtered_waveforms` | 1.0.2 | 波形处理 | st_waveforms |
| [`HitFinderPlugin`](hits.md) | `hits` | 0.0.0 | 特征提取 | st_waveforms |
| [`RawFileNamesPlugin`](raw_files.md) | `raw_files` | 0.0.2 | 数据加载 | - |
| [`RecordsPlugin`](records.md) | `records` | 0.4.0 | 记录处理 | raw_files |
| [`SignalPeaksPlugin`](signal_peaks.md) | `signal_peaks` | 1.0.2 | 特征提取 | filtered_waveforms, st_waveforms |
| [`WaveformsPlugin`](st_waveforms.md) | `st_waveforms` | 0.1.0 | 波形处理 | raw_files |
| [`WaveformWidthPlugin`](waveform_width.md) | `waveform_width` | 1.0.1 | 波形处理 | - |
| [`WaveformWidthIntegralPlugin`](waveform_width_integral.md) | `waveform_width_integral` | 1.1.0 | 波形处理 | - |

## Plugins by Category

### 数据加载

#### [`raw_files`](raw_files.md)

Scan the data directory and group raw CSV files by channel number.

- **Plugin Class**: `RawFileNamesPlugin`
- **Version**: `0.0.2`
- **Accelerator**: CPU (NumPy/SciPy)

### 波形处理

#### [`filtered_waveforms`](filtered_waveforms.md)

Apply filtering to waveforms using Butterworth or Savitzky-Golay filters.

- **Plugin Class**: `FilteredWaveformsPlugin`
- **Version**: `1.0.2`
- **Accelerator**: CPU (NumPy/SciPy)
- **Dependencies**: st_waveforms
#### [`st_waveforms`](st_waveforms.md)

Extract waveforms from raw CSV files and structure them into NumPy structured arrays.

- **Plugin Class**: `WaveformsPlugin`
- **Version**: `0.1.0`
- **Accelerator**: CPU (NumPy/SciPy)
- **Dependencies**: raw_files
#### [`waveform_width`](waveform_width.md)

Calculate rise/fall time based on peak detection results.

- **Plugin Class**: `WaveformWidthPlugin`
- **Version**: `1.0.1`
- **Accelerator**: CPU (NumPy/SciPy)

#### [`waveform_width_integral`](waveform_width_integral.md)

Event-wise integral quantile width using st_waveforms baseline.

- **Plugin Class**: `WaveformWidthIntegralPlugin`
- **Version**: `1.1.0`
- **Accelerator**: CPU (NumPy/SciPy)

### 特征提取

#### [`basic_features`](basic_features.md)

Plugin to compute basic height/area features from structured waveforms.

- **Plugin Class**: `BasicFeaturesPlugin`
- **Version**: `0.0.0`
- **Accelerator**: CPU (NumPy/SciPy)

#### [`hits`](hits.md)

Example implementation of the HitFinder as a plugin.

- **Plugin Class**: `HitFinderPlugin`
- **Version**: `0.0.0`
- **Accelerator**: CPU (NumPy/SciPy)
- **Dependencies**: st_waveforms
#### [`signal_peaks`](signal_peaks.md)

Detect peaks in filtered waveforms and extract peak features.

- **Plugin Class**: `SignalPeaksPlugin`
- **Version**: `1.0.2`
- **Accelerator**: CPU (NumPy/SciPy)
- **Dependencies**: filtered_waveforms, st_waveforms
### 事件分析

#### [`df_events`](df_events.md)

Plugin to group events by time window.

- **Plugin Class**: `GroupedEventsPlugin`
- **Version**: `0.0.0`
- **Accelerator**: CPU (NumPy/SciPy)
- **Dependencies**: df
#### [`df_paired`](df_paired.md)

Plugin to pair events across channels.

- **Plugin Class**: `PairedEventsPlugin`
- **Version**: `0.0.0`
- **Accelerator**: CPU (NumPy/SciPy)
- **Dependencies**: df_events
#### [`events`](events.md)

Provide event index data backed by the records bundle.

- **Plugin Class**: `EventsPlugin`
- **Version**: `0.1.0`
- **Accelerator**: CPU (NumPy/SciPy)

#### [`events_df`](events_df.md)

Build an events DataFrame from the events bundle.

- **Plugin Class**: `EventFramePlugin`
- **Version**: `0.1.0`
- **Accelerator**: CPU (NumPy/SciPy)
- **Dependencies**: events
#### [`events_grouped`](events_grouped.md)

Group events_df into multi-channel events by time window.

- **Plugin Class**: `EventsGroupedPlugin`
- **Version**: `0.1.0`
- **Accelerator**: CPU (NumPy/SciPy)
- **Dependencies**: events_df
### 数据导出

#### [`df`](df.md)

Plugin to build the initial single-channel events DataFrame.

- **Plugin Class**: `DataFramePlugin`
- **Version**: `0.0.0`
- **Accelerator**: CPU (NumPy/SciPy)
- **Dependencies**: st_waveforms, basic_features
### 缓存分析

#### [`cache_analysis`](cache_analysis.md)

Analyze cache usage and return summary, entries, and diagnostics.

- **Plugin Class**: `CacheAnalysisPlugin`
- **Version**: `0.1.0`
- **Accelerator**: CPU (NumPy/SciPy)

### 记录处理

#### [`records`](records.md)

Build records (event index table) from raw_files.

- **Plugin Class**: `RecordsPlugin`
- **Version**: `0.4.0`
- **Accelerator**: CPU (NumPy/SciPy)
- **Dependencies**: raw_files

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Loading                              │
│  raw_files → waveforms                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Waveform Processing                           │
│  st_waveforms → filtered_waveforms                              │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Feature Extract │ │ Signal Process  │ │  Hit Finding    │
│ basic_features  │ │ signal_peaks    │ │ hits            │
└─────────────────┘ └─────────────────┘ └─────────────────┘
              │               │               │
              └───────────────┼───────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Data Export                                │
│  dataframe → grouped_events → paired_events                     │
└─────────────────────────────────────────────────────────────────┘
```

## Configuration Guide

### Global Configuration

```python
from waveform_analysis.core.context import Context

ctx = Context(config={
    "data_root": "DAQ",
    "n_channels": 2,
    "daq_adapter": "vx2730",
})
```

### Plugin-Specific Configuration

```python
# Set configuration for a specific plugin
ctx.set_config({
    "height": 30.0,
    "prominence": 0.7,
}, plugin_name="signal_peaks")

# Or use dot notation
ctx.set_config({
    "signal_peaks.height": 30.0,
    "signal_peaks.prominence": 0.7,
})
```

---

*This index was auto-generated from plugin metadata.*
*Last updated: now*