**导航**: [文档中心](../README.md) > [架构设计](README.md) > Records + WavePool 设计

---

# Records + WavePool 数据中间层设计


本文档提出一种面向大跨度波形长度、百万级事件、流式/并行/异构计算场景的
数据中间层设计。核心思路是用一个按时间有序的索引表 `records` 搭配一维
波形池 `wave_pool`（内部 bundle），在保证可扩展与高性能的同时保持统一的
用户访问体验。

---

## 📋 目录

- [Records + WavePool 数据中间层设计](#records--wavepool-数据中间层设计)
  - [📋 目录](#-目录)
  - [概述](#概述)
  - [设计目标](#设计目标)
  - [数据模型](#数据模型)
    - [1. `records`（事件索引表）](#1-records事件索引表)
    - [2. `wave_pool`（波形池）](#2-wave_pool波形池)
  - [时间语义与排序](#时间语义与排序)
  - [构建流程与外部归并](#构建流程与外部归并)
    - [1. Worker 并行阶段](#1-worker-并行阶段)
    - [2. Merge 阶段（k-way merge）](#2-merge-阶段k-way-merge)
  - [并行与 GPU 职责划分](#并行与-gpu-职责划分)
  - [RecordsView 与用户 API](#recordsview-与用户-api)
  - [插件使用指南](#插件使用指南)
  - [缓存与存储布局](#缓存与存储布局)
  - [向后兼容性](#向后兼容性)
  - [阶段规划](#阶段规划)

---

## 概述

当前 `st_waveforms` 以“每条记录包含完整波形数组”的方式存储，面对以下场景
容易产生瓶颈：

- 波形长度跨度极大（几十点到上百万点）
- 超大事件规模（百万级）
- 需要 streaming/并行/GPU 协同

本方案将波形数据拆为：

- `records`: 小而规整的事件索引表（元数据 + 指针）
- `wave_pool`: 一维连续波形池（所有变长波形顺序拼接）

这样既保持“事件流/时间流”的访问模式，又避免将大波形嵌入结构化数组造成
排序/搬运成本过高。

---

## 设计目标

1. **统一数据模型**: 面向事件流，支持 streaming 与批量查询。
2. **高性能存储**: records 小而有序，wave_pool 连续可顺序读写。
3. **变长波形友好**: 事件长度不再受固定 dtype 约束。
4. **并行构建**: worker 并行输出分片，merge 线性归并一次完成。
5. **GPU 友好**: 通过批量 gather + pad/mask 将波形送入 GPU 特征插件。
6. **向后兼容**: 保留 `st_waveforms` 管线，提供可选适配层。

---

## 数据模型

### 1. `records`（事件索引表）

结构化数组，仅包含元数据和指针字段。

推荐字段如下（可在后续实现中微调）：

| 字段           | 类型    | 单位         | 说明                               |
| -------------- | ------- | ------------ | ---------------------------------- |
| `timestamp`    | int64   | ps           | ADC 时间戳（主排序与查询）         |
| `pid`          | int32   | -            | 采集/分片 ID，用于稳定排序与追溯   |
| `channel`      | int16   | -            | 物理通道号                         |
| `baseline`     | float64 | ADC counts   | 基线值（与现有 st_waveforms 对齐） |
| `event_id`     | int64   | -            | 排序后的全局顺序编号               |
| `dt`           | int32   | ns           | 采样间隔（与 time 同单位）         |
| `trigger_type` | int16   | -            | 触发类型编码                       |
| `flags`        | uint32  | -            | 位图标记（质量/异常等）            |
| `wave_offset`  | int64   | sample index | 在 wave_pool 中的起始索引          |
| `event_length` | int32   | samples      | 波形长度                           |
| `time`         | int64   | ns           | 系统时间，仅用于对齐/展示          |

说明：
- 字段命名遵循统一术语：使用 `event_length`，避免 `wave_length`/`pair_len`。
- `baseline` 使用 `float64` 以保持与现有 `st_waveforms` 一致的数值表现。
- `event_id` 在排序完成后生成，保证全局稳定顺序。
- `dt` 以 ns 记录，便于与 `time` 一起计算 endtime。
- `event_length` 使用 `int32`，支持最大约 21 亿采样点。
- `time` 字段**始终存在**但不参与默认查询与排序，仅作跨系统对齐或显示用途。

### 2. `wave_pool`（波形池）

一维连续数组，dtype 统一为 `uint16`：

- 14-bit ADC 可无损存储为 `uint16`
- 比 `float32` 节省约 50% 空间
- 读取时可按需转换为 `float32` 并进行 baseline 校正

波形索引方式：

```
wave = wave_pool[wave_offset : wave_offset + event_length]
```

---

## 时间语义与排序

- **默认时间轴**: `timestamp`（ADC 时间戳）
- **可选时间轴**: `time`（系统时间，ns）

排序规则：

```
(records)  按 (timestamp, pid, channel) 全局有序
```

优势：
- 事件流天然可按时间扫描
- streaming / event building / time range 查询更高效
- 排序稳定、可复现

---

## 构建流程与外部归并

### 1. Worker 并行阶段

每个 worker 处理一部分原始数据，产出：

- 已排序的 `records_part`
- 对应的 `wave_pool_part`（offset 以 part 内部起点计）

输出满足：`records_part` 按 `(timestamp, pid, channel)` 已排序。

### 2. Merge 阶段（k-way merge）

使用小顶堆做 k 路归并，同时构建全局 wave_pool：

- 每弹出一条 record：
  - 从所属 `wave_pool_part` 切片取波形
  - append 到最终 `wave_pool`
  - 将 record 的 `wave_offset` 改为全局位置

伪代码：

```python
heap = init_heap(parts)
wave_cursor = 0
while heap:
    rec, part_id, row_id = heappop(heap)
    wave = wave_pool_part[part_id][rec.wave_offset : rec.wave_offset + rec.event_length]
    wave_pool[wave_cursor : wave_cursor + rec.event_length] = wave
    rec.wave_offset = wave_cursor
    records_out.write(rec)
    wave_cursor += rec.event_length
    push_next_record(heap, part_id, row_id + 1)
```

特点：
- 线性复杂度、低内存
- 无需 prefix-sum + 二次修 offset
- 一次归并同时得到全局有序 records 与对齐 wave_pool

---

## 并行与 GPU 职责划分

- **CPU 多进程**: worker 阶段负责 IO/解码/裁剪/排序
- **归并阶段**: 线性合并，顺序 IO 为主（瓶颈可控）
- **GPU 使用点**: 特征计算阶段
  - `RecordsView.waves()` 批量 gather + pad/mask
  - GPU 端处理特征，输出 event-level 表格

说明：构建 `records`/`wave_pool` 本身是 IO 主导流程，GPU 不参与。

---

## RecordsView 与用户 API

提供只读访问视图，避免用户手动处理 offset/length：

```python
from waveform_analysis.core.data import records_view

rv = records_view(ctx, run_id)
wave = rv.wave(i, baseline_correct=True)
waves, mask = rv.waves([0, 10, 20], pad_to=2048, mask=True)
subset = rv.query_time_window(t_min, t_max)  # 使用 timestamp
```

API 约定：
- `query_time_window()` **只使用 `timestamp`**
- `time` 仅用于显示/对齐，不进入默认查询逻辑
- `events`（推荐）或 `records`（兼容）为公开插件产物
- `wave_pool` 作为内部 bundle，由 `RecordsView` 访问

---

## 插件使用指南

### 1. Events 管线（基于 records/wave_pool）

推荐用于变长波形/大规模数据流。插件链：

```
RawFilesPlugin → WaveformsPlugin → StWaveformsPlugin → EventsPlugin
```

输出：
- `events`: 结构化事件索引表
- `df`: 事件 DataFrame（timestamp/area/height/amp/channel）

**English**: `df` is the event DataFrame with `timestamp/area/height/amp/channel`.

插件说明（records 管线）：
- `RecordsPlugin` → `records`（依赖 `raw_files`）
  - 关键配置：`records_part_size`, `records_dt_ns`, `daq_adapter`
  - 继承波形加载参数：`channel_workers`, `channel_executor`, `n_jobs`, `use_process_pool`, `chunksize`
- `EventsPlugin` → `events`（依赖 `raw_files`；内部 bundle + wave_pool）
  - 关键配置：`events_part_size`, `events_dt_ns`
- `DataFramePlugin` → `df`（依赖 `st_waveforms`, `basic_features`）
  - 关键配置：`gain_adc_per_pe`
- `GroupedEventsPlugin` → `df_events`（依赖 `df`）
  - 关键配置：`time_window_ns`

### 2. st_waveforms 管线（现有）

沿用当前稳定链路：

```
RawFilesPlugin → WaveformsPlugin → StWaveformsPlugin → BasicFeaturesPlugin
             → DataFramePlugin → GroupedEventsPlugin → PairedEventsPlugin
```

输出：
- `df` / `df_events` / `df_paired`

---

## 缓存与存储布局

- `records`: `numpy.memmap` 结构化数组
- `wave_pool`: 内部 bundle 数据（当前不作为公开 data_name）

缓存策略：
- `EventsPlugin` lineage 统一驱动 `records`/`wave_pool` 一致性
- merge 结束后原子写入 (`.tmp` → rename)
- 两者保持一致性（版本/配置/依赖一致）

Lineage 细节（适配器分支）：
- `RecordsPlugin.get_lineage()` 会把实际生效的 `daq_adapter` 写入 lineage，避免不同适配器复用同一缓存键。
- 依赖固定为 `raw_files`，即便内部可能构建 `st_waveforms`，对外 lineage 仍保持稳定的上游边。
- `EventsPlugin.get_lineage()` 会根据 `daq_adapter` 分支依赖：
  - `v1725` → `depends_on = {"raw_files": ...}`
  - 其他适配器 → `depends_on = {"st_waveforms": ...}`

可选实现方式：
- 引入 `RecordsBundle`（包含 `records` + `wave_pool`）
- `Context` 使用内部 bundle 缓存 `wave_pool`，不暴露为公开数据名

---

## 向后兼容性

- 现有 `st_waveforms` 管线保留并继续支持
- `events`/`records` 管线当前默认从 `st_waveforms` 构建（`v1725` 直接走 `raw_files`）
- 新增 `events` 不替代旧数据类型，`wave_pool` 保持为内部数据
- 可选适配层：
  - `records → st_waveforms` 只读视图（供旧特征插件复用）
  - 逐步迁移新特征插件基于 RecordsView

---

## 阶段规划

1. **Phase 1**: 数据模型与存储实现
   - 新增 `EventsPlugin`（内部 wave_pool bundle）
   - 基础 memmap 存储与 lineage 记录

2. **Phase 2**: RecordsView 与查询
   - 批量 gather / pad / mask
   - timestamp-based 时间窗口查询

3. **Phase 3**: Streaming 与 GPU 插件整合
   - StreamingEventsPlugin
   - GPU 侧特征插件对接

---

**快速链接**:
[架构设计](README.md) |
[系统架构](ARCHITECTURE.md) |
[Context 工作流](CONTEXT_PROCESSOR_WORKFLOW.md)
