**导航**: [文档中心](../README.md) > [架构设计](README.md) > Records + WavePool

# Records + WavePool 设计

`records` 与 `wave_pool` 是 DAQ 原始波形进入分析插件 DAG 后的统一数据中间层。
它们将可变长度的单通道波形拆分为两类正式插件产物：结构化元数据表
`records`，以及连续的采样数组 `wave_pool`。两者必须成对使用。

本文说明设计边界、构建路由与维护约束。字段和配置的完整参考见
[records](../plugins/reference/agent/records.md) 与
[wave_pool](../plugins/reference/agent/wave_pool.md)。

## 设计目标

- 让上游 DAQ 格式差异终止在适配器和构建器边界，下游面向统一的数据模型。
- 用 `wave_offset + event_length` 表达可变长度波形，避免把波形嵌入固定宽度 dtype。
- 让 `records` 和 `wave_pool` 只构建一次，避免请求两个正式产物时重复读取原始文件。
- 支持大运行的分片、排序与 memmap 构建，同时保持下游公开接口稳定。
- 以 `run_id`、插件版本、跟踪配置和上游 lineage 决定缓存身份，避免跨运行复用。

## 数据模型

```text
records[i]
  board, channel, timestamp, baseline, polarity, ...
  wave_offset, event_length
             |
             +--> wave_pool[wave_offset : wave_offset + event_length]
```

`records` 是 `RECORDS_DTYPE` 结构化数组；其中 `timestamp` 使用 ps，`time` 使用 ns，
硬件通道的唯一键始终是 `(board, channel)`。`wave_pool` 是一维 `uint16` 采样数组，
不包含行边界或通道元数据。

最终合并后的不变量如下：

| 项目 | 约束 |
| --- | --- |
| 排序 | records 按 `(timestamp, pid, board, channel)` 全局排序。 |
| `record_id` | 排序后从 `0` 开始连续编号，是公开波形访问的稳定标识。 |
| 波形范围 | 每条记录满足 `0 <= wave_offset` 且 `wave_offset + event_length <= len(wave_pool)`。 |
| 波形归属 | `wave_pool[wave_offset:wave_offset + event_length]` 是该记录的完整原始波形。 |
| 同步更新 | 排序、分片合并或重新物化 `wave_pool` 时，必须同步重写 `wave_offset`。 |

`baseline`、`baseline_upstream`、`polarity`、`dt` 与 `flags` 属于 record 元数据；它们
不能从 `wave_pool` 本身推导出来。滤波后的波形也不应改写 `records`，而应由
`wave_pool_filtered` 作为另一个与同一 records 对齐的波形池产物。

## 组件与所有权

| 组件 | 职责 | 是否公开给下游 |
| --- | --- | --- |
| `RecordsBundle(records, wave_pool)` | 一次构建期间共享的成对结果 | 否，内部对象 |
| `RecordsBundleRef` | 临时 memmap 分片引用及显式超大数据访问 | 构建层能力，不是常规插件输出 |
| `RecordsPlugin` | 将 bundle 的元数据侧发布为 `records` | 是 |
| `WavePoolPlugin` | 将同一 bundle 的采样侧发布为 `wave_pool` | 是 |
| `records_view(ctx, run_id)` | 根据 `record_id` 组装正式 records 与波形池 | 是，推荐访问接口 |
| `WavePoolFilteredPlugin` | 基于 `records + wave_pool` 生成对齐的滤波波形池 | 是 |

内部 bundle 缓存只负责避免同一 Context 会话内重复构建，不能成为下游插件的依赖。
下游应声明并读取正式 `records`、`wave_pool`，或通过 `records_view(...)` 访问二者。
这使缓存 lineage、磁盘存储和运行间重建都有明确的公开边界。

## 构建路由

`RecordsPlugin` 与 `WavePoolPlugin` 的静态 `depends_on` 为空，但会在执行规划时按
当前配置动态解析共同上游。无论请求哪个输出，实际构建都经过同一个
`get_records_bundle(context, run_id)`。

```text
non-v1725, input_source=raw_files
  raw_files -> build_records_from_raw_files(...) -> RecordsBundle

non-v1725, input_source=st_waveforms
  st_waveforms -> build_records_from_st_waveforms_sharded(...) -> RecordsBundle

v1725
  raw_files -> build_records_from_v1725_files(...) -> RecordsBundle / RecordsBundleRef
```

默认 `input_source` 是 `raw_files`。对于非 V1725 适配器，选择
`input_source="st_waveforms"` 会让动态依赖切换到 `st_waveforms`，适合已经物化该产物
的链路。V1725 使用专用二进制读取和分片合并路径，明确不支持
`input_source="st_waveforms"`。

当 `records` 与 `wave_pool` 同时注册时，`wave_pool` 的动态依赖和构建配置以
`records` 插件为准。因此下面的配置同时作用于两个正式输出：

```python
ctx.set_config(
    {"input_source": "st_waveforms"},
    plugin_name="records",
)
```

这是共享 bundle 的配置所有权规则，不应通过给两个插件写出彼此冲突的输入配置来绕过。

## 共享构建与缓存

内部缓存键形如 `_records_bundle-{lineage_key}`，存放在 Context 的内存结果表中。若
`records` 已注册，键来自 `context.key_for(run_id, "records")`；否则来自 `wave_pool`。
这样一次请求 `records` 后再请求 `wave_pool`，或反过来，都会复用同一 bundle。

```text
Context request records or wave_pool
        |
        v
get_records_bundle(run_id)
        |
        +-- internal bundle cache hit --> reuse pair
        |
        +-- miss --> select route, build pair, cache pair
                                      |
                                      +--> RecordsPlugin publishes records
                                      +--> WavePoolPlugin publishes wave_pool
```

内部 bundle 与正式插件缓存层次不同：

- 内部 bundle 仅在当前 Context 中复用，并会在同一 run 产生新的 bundle 键时清理旧引用。
- `records` 与 `wave_pool` 作为 `save_when="always"` 的正式产物，可由存储后端持久化。
- 两个插件共享 PATCH 版本；构建语义、读取器行为或任何影响输出内容的配置变化都必须
  升级版本，从而使旧的 records/wave_pool lineage 失效。
- 只有标记为 tracked 的配置进入 lineage。并发度、执行器选择等运行时调优项通常不应
  改变输出身份，但仍可能改变资源消耗。

## 大数据与分片

构建器可以先生成 `_RecordsPartRef` 指向的临时 memmap 分片，再进行全局排序和合并。
这将“读取原始波形”和“最终物化正式产物”分离：构建阶段不必长期持有所有波形对象。

`records_part_size` 控制通用路径的 records 分片规模；V1725 使用
`v1725_part_size` 控制单文件内的 wave 分片规模。`keep_on_disk` 与
`memory_budget_gb` 决定是否保留磁盘引用或合并为内存数组。V1725 默认倾向磁盘
引用，且 `n_jobs` 只控制文件级并行；单个 `.bin` 文件始终按事件边界串行读取。

`RecordsBundleRef.iter_chunks(...)` 可用于显式的超大数据处理，但其分块中的
`wave_offset` 会被重映射为当前 chunk 的相对偏移。它不是 `RecordsPlugin` 和
`WavePoolPlugin` 的常规公开返回契约；常规分析代码应读取正式产物或使用
`records_view(...)`。

## 公开访问与下游

需要按 record 获取波形时，使用 `records_view`，不要索引内部 bundle：

```python
from waveform_analysis.core.data import records_view

rv = records_view(ctx, "run_001")
record_id = int(rv.records[0]["record_id"])
raw_wave = rv.waves(record_id)
signal = rv.signals(record_id, sample_start=40, sample_end=120)
```

`rv.waves(...)` 依据 `record_id` 与 `wave_offset/event_length` 回切原始波形；
`rv.signals(...)` 再按 records 的 `polarity` 统一信号方向。选择
`wave_pool_name="wave_pool_filtered"` 时，只替换波形池，不改变 record 元数据与索引
关系。

典型下游分为两类：

- 元数据/选择链路：records mask、hit finding 和依赖 records 的特征插件。
- 波形链路：`wave_pool_filtered`、records-backed 波形插件，以及按 `records_view` 查询的
  分析与可视化代码。

新增或修改下游时，必须明确它只需要 records 元数据、只需要已对齐的波形池，还是需要
两者；不能假设 `wave_pool` 的数组下标等于 `record_id`。

## 维护约束

1. 变更 records 字段、波形 dtype、排序规则、`wave_offset` 语义或输入路由时，视为
   插件契约变更，升级版本并执行 schema/lineage 检查。
2. 任何新的输入路由都必须同时验证 `RecordsPlugin`、`WavePoolPlugin` 的动态依赖与
   共享 bundle 配置所有权。
3. 不要把 `RecordsBundle` 或 `_records_bundle-*` 暴露为新的下游公共依赖。
4. 波形池的变换必须保持与 records 的一对一布局；若不能保持，必须定义新的 records
   表和新的公开产物，而不是复用旧的 `wave_offset`。
5. 修改配置或输出契约后，刷新自动/Agent 插件参考；设计解释保留在本文，避免手改生成页。

## 相关文档

- [数据访问](../features/context/DATA_ACCESS.md)：运行时读取、RecordsView 与缓存行为。
- [配置管理](../features/context/CONFIGURATION.md)：配置来源与解析优先级。
- [records 插件参考](../plugins/reference/agent/records.md)：字段和配置表。
- [wave_pool 插件参考](../plugins/reference/agent/wave_pool.md)：采样数组和配置表。
- [系统架构](ARCHITECTURE.md)：适配器、存储与插件 DAG 的总体设计。
