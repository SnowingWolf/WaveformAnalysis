# 配置参考文档

> 自动生成于 2026-01-26 13:44:28

本文档列出了所有插件的配置选项。

---

## 目录

- [raw_files](#raw-files)
- [waveforms](#waveforms)
- [st_waveforms](#st-waveforms)
- [hits](#hits)
- [peaks](#peaks)
- [charges](#charges)
- [df](#df)
- [df_events](#df-events)
- [df_paired](#df-paired)
- [events_grouped](#events-grouped)

---

## raw_files

**类名**: `RawFilesPlugin`
**版本**: 0.0.2
**提供数据**: `raw_files`
**依赖**: 无
Plugin to find raw CSV files.

### 配置选项

#### `data_root`

- **类型**: `<class 'str'>`
- **默认值**: `DAQ`
- **说明**: Root directory for data

**使用示例**:

```python
ctx.set_config({'data_root': <value>}, plugin_name='raw_files')
```

---
#### `daq_adapter`

- **类型**: `<class 'str'>`
- **默认值**: `vx2730`
- **说明**: DAQ adapter name (e.g., 'vx2730')

**使用示例**:

```python
ctx.set_config({'daq_adapter': <value>}, plugin_name='raw_files')
```

---

---

## waveforms

**类名**: `WaveformsPlugin`
**版本**: 0.0.2
**提供数据**: `waveforms`
**依赖**: raw_files
Plugin to extract waveforms from raw files.

### 配置选项

#### `channel_workers`

- **类型**: `None`
- **默认值**: `None`
- **说明**: Number of parallel workers for channel-level processing (None=auto, uses min(len(raw_files), cpu_count))

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
#### `daq_adapter`

- **类型**: `<class 'str'>`
- **默认值**: `vx2730`
- **说明**: DAQ adapter name (e.g., 'vx2730')

**使用示例**:

```python
ctx.set_config({'daq_adapter': <value>}, plugin_name='waveforms')
```

---
#### `n_jobs`

- **类型**: `<class 'int'>`
- **默认值**: `None`
- **说明**: Number of parallel workers for file-level processing within each channel (None=auto, uses min(max_file_count, 50))

**使用示例**:

```python
ctx.set_config({'n_jobs': <value>}, plugin_name='waveforms')
```

---
#### `use_process_pool`

- **类型**: `<class 'bool'>`
- **默认值**: `False`
- **说明**: Whether to use process pool for file-level parallelism (False=thread pool for I/O, True=process pool for CPU-intensive)

**使用示例**:

```python
ctx.set_config({'use_process_pool': <value>}, plugin_name='waveforms')
```

---
#### `chunksize`

- **类型**: `<class 'int'>`
- **默认值**: `None`
- **说明**: Chunk size for CSV reading (None=read entire file, enables PyArrow; set value to enable chunked reading but disables PyArrow)

**使用示例**:

```python
ctx.set_config({'chunksize': <value>}, plugin_name='waveforms')
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

#### `daq_adapter`

- **类型**: `<class 'str'>`
- **默认值**: `vx2730`
- **说明**: DAQ adapter name (default: 'vx2730').

**使用示例**:

```python
ctx.set_config({'daq_adapter': <value>}, plugin_name='st_waveforms')
```

---

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

## peaks

**类名**: `PeaksPlugin`
**版本**: 0.0.0
**提供数据**: `peaks`
**依赖**: st_waveforms
Plugin to compute peak features from structured waveforms.

### 配置选项

#### `peaks_range`

- **类型**: `<class 'tuple'>`
- **默认值**: `None`
- **说明**: 峰值计算范围 (start, end)

**使用示例**:

```python
ctx.set_config({'peaks_range': <value>}, plugin_name='peaks')
```

---

---

## charges

**类名**: `ChargesPlugin`
**版本**: 0.0.0
**提供数据**: `charges`
**依赖**: st_waveforms
Plugin to compute charge features from structured waveforms.

### 配置选项

#### `charge_range`

- **类型**: `<class 'tuple'>`
- **默认值**: `(0, None)`
- **说明**: 电荷计算范围 (start, end)，end=None 表示积分到波形末端

**使用示例**:

```python
ctx.set_config({'charge_range': <value>}, plugin_name='charges')
```

---

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

## events_grouped

**类名**: `EventsGroupedPlugin`
**版本**: 0.1.0
**提供数据**: `events_grouped`
**依赖**: events_df
Group events_df into multi-channel events by time window.

### 配置选项

#### `time_window_ns`

- **类型**: `<class 'float'>`
- **默认值**: `100.0`
- **说明**: Grouping time window in ns (converted to ps internally).

**使用示例**:

```python
ctx.set_config({'time_window_ns': <value>}, plugin_name='events_grouped')
```

---
#### `use_numba`

- **类型**: `<class 'bool'>`
- **默认值**: `True`
- **说明**: Enable numba acceleration when available.

**使用示例**:

```python
ctx.set_config({'use_numba': <value>}, plugin_name='events_grouped')
```

---
#### `n_processes`

- **类型**: `<class 'int'>`
- **默认值**: `None`
- **说明**: Process count for multiprocessing; None or <=1 disables it.

**使用示例**:

```python
ctx.set_config({'n_processes': <value>}, plugin_name='events_grouped')
```

---


---

**生成时间**: 2026-01-26 13:44:28
**工具**: WaveformAnalysis DocGenerator
