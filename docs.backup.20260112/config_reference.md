# 配置参考文档

> 自动生成于 2026-01-11 19:23:26

本文档列出了所有插件的配置选项。

---

## 目录

- [raw_files](#raw-files)
- [waveforms](#waveforms)
- [st_waveforms](#st-waveforms)
- [hits](#hits)
- [basic_features](#basic-features)
- [peaks](#peaks)
- [charges](#charges)
- [df](#df)
- [df_events](#df-events)
- [df_paired](#df-paired)

---

## raw_files

**类名**: `RawFilesPlugin`
**版本**: 0.0.0
**提供数据**: `raw_files`
**依赖**: 无
Plugin to find raw CSV files.

### 配置选项

#### `n_channels`

- **类型**: `<class 'int'>`
- **默认值**: `2`
- **说明**: Number of channels to load

**使用示例**:

```python
ctx.set_config({'n_channels': <value>}, plugin_name='raw_files')
```

---
#### `start_channel_slice`

- **类型**: `<class 'int'>`
- **默认值**: `6`
- **说明**: Starting channel index

**使用示例**:

```python
ctx.set_config({'start_channel_slice': <value>}, plugin_name='raw_files')
```

---
#### `data_root`

- **类型**: `<class 'str'>`
- **默认值**: `DAQ`
- **说明**: Root directory for data

**使用示例**:

```python
ctx.set_config({'data_root': <value>}, plugin_name='raw_files')
```

---

---

## waveforms

**类名**: `WaveformsPlugin`
**版本**: 0.0.0
**提供数据**: `waveforms`
**依赖**: raw_files
Plugin to extract waveforms from raw files.

### 配置选项

#### `start_channel_slice`

- **类型**: `<class 'int'>`
- **默认值**: `6`
- **说明**: 

**使用示例**:

```python
ctx.set_config({'start_channel_slice': <value>}, plugin_name='waveforms')
```

---
#### `n_channels`

- **类型**: `<class 'int'>`
- **默认值**: `2`
- **说明**: 

**使用示例**:

```python
ctx.set_config({'n_channels': <value>}, plugin_name='waveforms')
```

---
#### `channel_workers`

- **类型**: `None`
- **默认值**: `None`
- **说明**: Number of parallel workers for channel-level processing (None=auto, uses min(n_channels, cpu_count))

**使用示例**:

```python
ctx.set_config({'channel_workers': <value>}, plugin_name='waveforms')
```

---
#### `channel_executor`

- **类型**: `<class 'str'>`
- **默认值**: `thread`
- **说明**: Executor type for channel-level parallelism: 'thread' or 'process'

**使用示例**:

```python
ctx.set_config({'channel_executor': <value>}, plugin_name='waveforms')
```

---

---

## st_waveforms

**类名**: `StWaveformsPlugin`
**版本**: 0.0.0
**提供数据**: `st_waveforms`
**依赖**: waveforms
Plugin to structure waveforms into NumPy arrays.

### 配置选项

该插件没有配置选项。

---

## hits

**类名**: `HitFinderPlugin`
**版本**: 0.0.0
**提供数据**: `hits`
**依赖**: st_waveforms
Example implementation of the HitFinder as a plugin.

### 配置选项

该插件没有配置选项。

---

## basic_features

**类名**: `BasicFeaturesPlugin`
**版本**: 0.0.0
**提供数据**: `basic_features`
**依赖**: st_waveforms
Plugin to compute basic features (peaks and charges).

### 配置选项

#### `peaks_range`

- **类型**: `<class 'tuple'>`
- **默认值**: `None`
- **说明**: 

**使用示例**:

```python
ctx.set_config({'peaks_range': <value>}, plugin_name='basic_features')
```

---
#### `charge_range`

- **类型**: `<class 'tuple'>`
- **默认值**: `None`
- **说明**: 

**使用示例**:

```python
ctx.set_config({'charge_range': <value>}, plugin_name='basic_features')
```

---

---

## peaks

**类名**: `PeaksPlugin`
**版本**: 0.0.0
**提供数据**: `peaks`
**依赖**: basic_features
Plugin to provide peaks from basic_features.

### 配置选项

该插件没有配置选项。

---

## charges

**类名**: `ChargesPlugin`
**版本**: 0.0.0
**提供数据**: `charges`
**依赖**: basic_features
Plugin to provide charges from basic_features.

### 配置选项

该插件没有配置选项。

---

## df

**类名**: `DataFramePlugin`
**版本**: 0.0.0
**提供数据**: `df`
**依赖**: st_waveforms, peaks, charges
Plugin to build the initial single-channel events DataFrame.

### 配置选项

该插件没有配置选项。

---

## df_events

**类名**: `GroupedEventsPlugin`
**版本**: 0.0.0
**提供数据**: `df_events`
**依赖**: df
Plugin to group events by time window.

### 配置选项

#### `time_window_ns`

- **类型**: `<class 'float'>`
- **默认值**: `100.0`
- **说明**: 

**使用示例**:

```python
ctx.set_config({'time_window_ns': <value>}, plugin_name='df_events')
```

---

---

## df_paired

**类名**: `PairedEventsPlugin`
**版本**: 0.0.0
**提供数据**: `df_paired`
**依赖**: df_events
Plugin to pair events across channels.

### 配置选项

该插件没有配置选项。

---


---

**生成时间**: 2026-01-11 19:23:26
**工具**: WaveformAnalysis DocGenerator