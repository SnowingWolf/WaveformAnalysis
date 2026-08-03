# 批量运行：多 Run 调度与执行（开发中）

**导航**: [文档中心](../README.md) > [系统架构与数据模型](README.md) > 批量运行：多 Run 调度与执行（开发中）

> **状态：开发中。** 本页区分当前代码已经实现的行为与尚未稳定的契约。`BatchProcessor` 可以组织
> 多 run 请求、自定义回调、配置网格、并发、重试和取消，但接口与存储策略仍可能继续收敛。

多 run 执行由一组独立的单 run 请求组成。每个任务继续通过 Context 解析 Plugin DAG、lineage 和
缓存；BatchProcessor 在该边界之外负责调度和汇总。

```mermaid
flowchart TD
    BATCH[BatchProcessor] --> T1[task: run_001 + target + config]
    BATCH --> T2[task: run_002 + target + config]
    BATCH --> T3[task: run_003 + target + config]
    T1 --> C1[独立 Context 请求]
    T2 --> C2[独立 Context 请求]
    T3 --> C3[独立 Context 请求]
    C1 --> D1[单 run DAG / lineage / cache]
    C2 --> D2[单 run DAG / lineage / cache]
    C3 --> D3[单 run DAG / lineage / cache]
    D1 --> SUMMARY[results / errors / meta]
    D2 --> SUMMARY
    D3 --> SUMMARY
```

## 1. 当前能力

### 1.1 三类批量入口

| 入口 | 任务定义 | 当前返回 |
| --- | --- | --- |
| `process_runs` | 对每个 run 请求同一 `data_name` | `results`、`errors`、`meta`、`ordered_run_ids` |
| `process_func` | 对每个 run 调用 `func(context, run_id)` | 同上 |
| `process_runs_with_config_grid` | 对多组 Plugin 配置分别执行 run 列表 | 配置列表与每组 batch 结果 |

`process_runs` 和 `process_func` 都支持线程/进程、错误策略、进度、Jupyter 轮询、重试和临时存储
策略；显式 `CancellationToken` 当前只由 `process_runs` 接收。配置网格按配置项外层顺序执行，每一组
配置内部再处理 run 列表。

### 1.2 返回状态

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> success: 返回结果
    pending --> attempt_error: 捕获异常
    attempt_error --> pending: 命中 retry_on 且未超限
    attempt_error --> failed: 不重试或重试耗尽
    pending --> cancelled: 任务收到取消
    pending --> skipped: stop / cancel 后未执行
    success --> [*]
    failed --> [*]
    cancelled --> [*]
    skipped --> [*]
```

每个 run 的 `meta` 当前记录 `status`、`elapsed` 和 `attempts`。`errors` 保存异常类型、消息和
traceback；`ordered_run_ids` 保留调用端输入顺序，因为并发完成顺序不稳定。

## 2. 单 Run 执行单元

### 2.1 任务身份

```mermaid
flowchart LR
    RUN[run_id] --> TASK[单 run task]
    TARGET[data_name / process_func] --> TASK
    CONFIG[resolved config snapshot] --> TASK
    CONTEXT[Plugin registry + storage] --> TASK
    TASK --> GET[Context.get_data or callback]
    GET --> IDENTITY[(run_id, product, lineage)]
```

Plugin 的一次 `compute(context, run_id, ...)` 仍只处理一个 run。同一 DAG 可以对多个 run 重复
解析，但缓存键和实体 ID 空间按 run 隔离。

### 2.2 跨 Run ID

| 使用方式 | 是否安全 | 原因 |
| --- | --- | --- |
| `(run_id, peak_id)` | 是，仍需记录 lineage/配置条件 | run 明确限定局部 ID |
| 只保存 `peak_id` | 否 | 不同 run 可产生相同局部 ID |
| 把两个 run 的实体数组直接拼接 | 仅在增加 run 字段并统一 schema 后 | 否则来源无法恢复 |
| 将一个 run 的关系表 join 到另一个 run | 否 | 父子 ID 空间不同 |

## 3. 串行、线程与进程

### 3.1 执行模式

```mermaid
flowchart TD
    REQUEST[批量请求] --> WORKERS{max_workers 为 None 或大于 1?}
    WORKERS -->|否| SERIAL[串行复用传入 Context]
    WORKERS -->|是| MODE{executor_type}
    MODE -->|thread| CLONE{ctx.clone 可用?}
    MODE -->|process| FACTORY{create_context_factory 可用?}
    CLONE -->|是| THREADS[每任务创建 Context clone]
    FACTORY -->|是| PROCESSES[每任务重建 Context]
    CLONE -->|否| FALLBACK[警告并回退串行]
    FACTORY -->|否| FALLBACK
```

| 模式 | Context 来源 | 主要约束 |
| --- | --- | --- |
| 串行 | 直接使用 `BatchProcessor.context` | 同一时刻只处理一个 run |
| 线程 | 默认尝试 `ctx.clone`，或显式 `context_factory` | Context 实例按任务隔离；共享 Storage 需支持并发 |
| 进程 | 默认尝试 `ctx.create_context_factory()` | 工厂、Plugin 注册和自定义回调必须可序列化/重建 |

并发请求没有可用工厂时，当前实现发出警告并回退到串行，而不是让多个 worker 共享同一个可变 Context。

### 3.2 Context 隔离

Context 包含内存结果、resolved config 缓存、run config 缓存、性能统计和 Plugin 实例。多个 worker
直接共享同一实例会让运行时状态互相覆盖。clone/factory 复制注册与配置，但为任务建立独立运行状态；
持久化 Storage 是否共享由存储策略决定。

## 4. 存储目录策略

### 4.1 当前代码行为

| `storage_dir_strategy` | 当前并行行为 | 稳定性说明 |
| --- | --- | --- |
| `shared` | 保留 Context 原存储目录 | 已实现；并发写安全取决于 Storage |
| `per_worker` | 每次任务尝试创建临时 `batch_cache_*` 目录 | 已实现，任务结束可清理 |
| `readonly` | 当前与 `per_worker` 走同一临时目录分支 | **名称未形成强制只读契约** |

串行模式下，非 `shared` 策略当前会被忽略并回退为 `shared`。因此不能根据参数名假设
`readonly` 已禁止计算或写入；需要真正只读语义的调用方目前应在执行前验证目标缓存，并避免把该
名称作为安全边界。

```mermaid
flowchart TD
    STRATEGY{storage_dir_strategy}
    STRATEGY -->|shared| EXISTING[使用原 storage_dir]
    STRATEGY -->|per_worker| TEMP[创建 batch_cache 临时目录]
    STRATEGY -->|readonly 当前行为| TEMP
    TEMP --> RUN[执行任务]
    RUN --> CLEAN{clean_temp_cache}
    CLEAN -->|true| DELETE[清理临时目录]
    CLEAN -->|false| KEEP[保留供诊断]
```

## 5. 配置网格

### 5.1 任务矩阵

两个 run 与两组配置形成四个逻辑任务：

| 配置索引 | Plugin 配置 | run |
| ---: | --- | --- |
| 0 | `{threshold: 5}` | `run_001` |
| 0 | `{threshold: 5}` | `run_002` |
| 1 | `{threshold: 8}` | `run_001` |
| 1 | `{threshold: 8}` | `run_002` |

```mermaid
flowchart LR
    C0[config 0] --> C0R1[run_001 lineage A]
    C0 --> C0R2[run_002 lineage A]
    C1[config 1] --> C1R1[run_001 lineage B]
    C1 --> C1R2[run_002 lineage B]
    C0R1 --> REPORT[按 config_index + run_id 汇总]
    C0R2 --> REPORT
    C1R1 --> REPORT
    C1R2 --> REPORT
```

每组配置通过 `ctx.set_config(config, plugin_name=plugin_name)` 应用。tracked 配置变化产生新的
lineage；汇总结果必须保留 `config_index`、原始配置和 run_id，不能只按数组位置解释来源。

### 5.2 当前限制

配置网格目前不是一个全局二维调度器：外层配置串行推进，每一组内部才使用 `process_runs` 的并发
策略。使用同一 Context 的串行路径会逐组修改 Plugin 配置；调用方不应在网格执行期间并发复用该
Context 做其他请求。

## 6. 重试、取消与错误策略

### 6.1 重试

`retries` 是额外尝试次数，只有异常属于 `retry_on` 指定类型时才重试。每次并行尝试重新调用
`context_factory()`；临时存储可在尝试之间清理。重试不会把失败结果写成成功缓存，但底层 Plugin 在
异常前是否留下不完整外部副作用，仍由其存储原子性保证。

### 6.2 错误策略

| `on_error` | 行为 |
| --- | --- |
| `continue` | 记录失败，继续其他 run |
| `stop` | 记录当前失败，取消/跳过尚未开始的任务 |
| `raise` | 重新抛出异常并终止调用 |

已开始的并发任务可能无法瞬时停止，因此 `stop` 或取消后仍需根据 `meta` 判断哪些任务 success、failed、
cancelled 或 skipped，不能只看结果字典长度。

## 7. 跨 Run 汇总

跨 run 统计发生在单 run 正式产物完成之后。汇总表至少保留：

| 字段 | 用途 |
| --- | --- |
| `run_id` | 限定实体 ID 和输入采集 |
| `data_name` / operation | 记录目标语义 |
| config 或 `config_index` | 区分扫描条件 |
| lineage 摘要 | 证明结果身份兼容 |
| status / attempts / elapsed | 描述执行结果 |
| error type / message | 支持失败分析与选择性重试 |

若跨 run 汇总本身需要被下游重复使用，应建立独立且可追溯的产物边界；当前 BatchProcessor 返回值是
调度结果，不自动成为 Plugin DAG 中的正式跨 run 产物。

## 8. 故障原因

| 现象 | 可能原因 | 检查 |
| --- | --- | --- |
| 请求并行却串行执行 | clone/factory 不可用，触发串行回退 | warning、`max_workers`、Context factory |
| 进程模式启动失败 | 工厂、Plugin 或回调不可序列化 | `create_context_factory` 与自定义函数定义位置 |
| run 之间状态串扰 | worker 共享了可变 Context 或共享外部全局对象 | 每任务 Context 和 Plugin 实例 |
| 缓存写入冲突 | `shared` Storage 不支持当前并发写模式 | 存储目录、原子写和锁行为 |
| `readonly` 仍发生计算 | 当前实现未强制只读，只切换临时目录 | 实际 `_apply_storage_dir_strategy` 行为 |
| 重试后结果重复 | 自定义回调存在非幂等外部副作用 | callback 的写入与去重策略 |
| 汇总缺少部分 run | `stop`、取消或失败只记录在 `meta/errors` | `ordered_run_ids` 与每个状态 |

## 9. 开发中事项

以下内容尚不应写成稳定保证：

1. `readonly` 的强制只读语义和预检行为；
2. 配置网格的跨配置全局调度与资源配额；
3. 分布式执行器、远程队列和跨主机缓存协调；
4. 正式的跨 run 数据产物与 lineage 模型；
5. 失败恢复点、断点续跑和幂等外部副作用协议。

## 10. 维护检查

1. 每个任务显式保存 run_id、目标、配置和状态。
2. 并发任务使用独立 Context；共享 Storage 的并发语义经过测试。
3. retry 仅处理明确异常类型，自定义回调说明幂等性。
4. 汇总保留失败和 skipped 项，不把缺失当作空结果。
5. 文档将当前实现与未来设计分开，尤其不把 `readonly` 名称写成已实现保证。

参见[系统总览：组件、边界与数据流](ARCHITECTURE.md)了解 Context 边界，参见
[插件执行链：DAG、动态依赖、Lineage 与缓存](PLUGIN_DAG_LINEAGE_CACHE.md)了解每个单 run 任务的结果身份。
