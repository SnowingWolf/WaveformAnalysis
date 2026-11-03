# 配置管理

本文档说明 `Context` 配置解析、DAQ adapter 推断、兼容参数映射与配置类型。Agent 侧约束见 `docs/agents/configuration.md`；本文件是用户与代码锚点使用的配置入口。

`Context` 保持无状态的数据访问接口；配置解析由内部的 `ContextConfigDomain` 承接，
不改变 `ctx.set_config()`、`ctx.get_config()` 或 `ctx.get_resolved_config()` 的用法。

Context 未显式传入 `storage_dir` 时，默认将缓存和处理产物写入当前目录下的 `./wa_data/`；
`data_root` 仍用于定位原始 DAQ 数据，默认值为 `DAQ`。如需使用其他缓存位置，请显式传入
`storage_dir`。

批量调用的 `storage_dir_strategy="readonly"` 是任务访问策略，不是插件配置项。它保留原缓存目录，
不写配置快照或 `_run_config_state.json`；若请求链依赖 run 配置，必须已有与当前配置匹配的
持久化状态和磁盘结果，否则明确报缓存不可用。普通调用仍遵循现有配置同步与失效规则。
详见[批量处理的缓存目录策略](BATCH_PROCESSOR.md)。

请求会在读取缓存或计算前检查依赖的显式版本约束，检查结果按 run 和目标复用。
`set_config()`、插件注册或覆盖、缓存清理，以及检测到 run 配置刷新时都会使该检查结果失效。
这也覆盖 `get_run_config(refresh=True)` 和 readonly 请求确认外部已更新配置及持久状态的情况；
readonly 仍只更新内存中的验证状态，不计算插件或改写磁盘缓存、配置快照和持久状态。

`Plugin.timeout` 是插件执行属性，不是 `ctx.set_config()` 配置项。当前 Context 只支持
`timeout=None`：需要进入该插件的 `compute()` 时，非 `None` 值会触发 `NotImplementedError`。
该属性值不进入 lineage，也不改变缓存身份；命中有效缓存时仍可读取已有结果。
检查发生在该插件的计算入口，上游依赖可能已经执行。详见
[超时支持边界](../../architecture/ARCHITECTURE.md#超时支持边界)。

## 查看配置

`ctx.list_plugin_configs(plugin_name, verbose=False)` 返回选项元数据和当前值的字典；
默认开启展示时，还会输出插件概览与选项表。`show_current_values=False` 仅列出选项定义，
`show_full_help=True` 保留完整帮助文本。

`ctx.show_config(data_name)` 复用插件选项表；不传 `data_name` 时则按全局、插件特定、
Context 自身和未使用配置分组展示。两种视图共用选项格式、排序和高亮规则，
但全局视图展示显式配置，选项清单中的当前值经过配置解析。
需要追踪生效值来源时，使用 `ctx.show_resolved_config(plugin)`。

## 配置优先级

配置生效顺序为：

1. 显式配置
2. DAQ adapter 推断
3. 插件默认值

显式配置可以来自 `Context.config`、`ctx.set_config()`、插件命名空间配置或 run 级配置。插件行为参数应优先放在插件自己的命名空间下，例如 `plugins.<plugin>` 或 `<plugin>` 配置块；通道差异化行为应放在插件的 `channel_config` 中。

通道配置采用三层覆盖：

```text
defaults < groups < channels
```

硬件通道唯一键统一为 `(board, channel)`，配置文件中推荐写成 `"board:channel"`。不要继续使用裸 channel 或 boardless key。

示例：

```python
ctx.set_config(
    {
        "daq_adapter": "vx2730",
        "hit": {
            "threshold": 20.0,
            "channel_config": {
                "defaults": {"polarity": "negative"},
                "groups": [
                    {
                        "name": "positive_board1",
                        "channels": ["1:0", "1:1"],
                        "config": {"polarity": "positive", "threshold": 35.0},
                    }
                ],
                "channels": {
                    "1:0": {"threshold": 40.0},
                },
            },
        },
    }
)
```

在这个例子里，`hit(1:0)` 先继承默认负极性，再被 group 改为正极性和阈值 35，最后被单通道阈值 40 覆盖。

## 适配器推断

配置解析器会从 DAQ adapter 的格式信息推断部分插件配置。推荐显式设置全局 `daq_adapter`，避免同一处理链路内不同插件推断来源不一致。
Adapter registry 的规范入口是 `waveform_analysis.acquisition.formats`；旧的
`waveform_analysis.utils.formats` 与其共享同一 registry 和对象身份。

自定义 adapter 必须在创建 `Context` 前注册。`AdapterInfo.from_adapter(name)` 与
`get_adapter_info(name)` 每次从当前注册对象提取元数据，不使用进程级元数据缓存；按名称入口复用
`AdapterInfo.from_adapter_object(adapter)`。未知名称返回 `None`，已注册对象的元数据错误直接传播。
`use_cache` 参数和 `clear_adapter_info_cache` 函数及其导出已删除，调用方应移除这些参数和清理调用。

注册表替换不会通知已有 Context，也不会自动失效其配置或 lineage。若以同名 adapter 替换了格式规范，
应在注册完成后创建新的 Context，再请求数据；不支持既有 Context 的注册表热替换。

当前可推断的典型值包括：

- `sampling_rate_hz`
- `sampling_rate`
- `fs`
- `sampling_interval_ns`
- `dt`
- `dt_ns`
- `dt_ps`
- `records_dt_ns`
- `events_dt_ns`
- `timestamp_unit`
- `raw_timestamp_mode`

推断值只在没有显式配置时生效。可以使用 `ctx.get_resolved_config()` 或 `ctx.show_resolved_config()` 检查每个配置值的来源。

## 兼容层

兼容层集中处理旧参数名到规范参数名的映射，以及弃用提示。参数重命名必须先进入兼容层，不能在插件实现内部散落处理。

兼容层职责：

- 将旧参数名解析为规范参数名。
- 对已弃用参数发出弃用警告。
- 保留配置解析入口的兼容行为。
- 让插件内部只读取规范参数名。

新增或删除兼容参数时，应同步检查：

- 兼容映射是否只保留在入口层。
- 插件实现是否已经收敛到规范名称。
- 文档是否说明新名称和迁移方式。
- 行为或配置语义变化是否需要升级插件 `version`。

## 配置类型

配置解析结果使用结构化类型表达配置值、来源和调试信息。

核心类型：

- `ConfigSource`：配置来源枚举，包括 `explicit`、`plugin_default`、`adapter_inferred`、`global_default`。
- `ConfigValue`：单个配置值及其来源、原始键名、规范键名和推断来源。
- `ResolvedConfig`：某个插件的完整解析配置集合。

`ResolvedConfig` 可用于读取生效值、列出显式值、列出 adapter 推断值，并生成参与 lineage 的配置字典。默认 lineage 只包含显式配置和 adapter 推断值；插件默认值通常不作为显式 lineage 输入。
DAQ adapter 的解释信息由 Context 仅附加在顶层 lineage。递归上游使用不含该字段的基础 lineage，
从而保证首次查询、缓存后查询及不同依赖遍历顺序产生相同缓存身份。

## 配置展示

`ctx.list_plugin_configs()` 会展示插件概览和配置选项明细。对于没有 `options`
的插件，配置选项明细会明确显示“该插件没有配置选项”，不会再尝试对空配置表排序或
设置索引。

`ctx.help("config")` 返回 `HelpDocument`：终端中打印纯文本一次，Jupyter 中由 displayhook
显示 HTML。帮助查询不会解析 run 配置、执行插件或修改 Context；需要检查实际配置来源时仍应使用
`get_resolved_config()` / `show_resolved_config()`。

## 推荐实践

- 全局设置 `daq_adapter`。
- 使用 `run_config.json` 放 run 级覆盖和标定结果。
- 使用 `plugins.<plugin>.channel_config` 表达通道级行为差异。
- 使用顶层 `channel_metadata` 表达硬件事实或兼容信息，不参与插件行为决策。
- 标定值如 `gain_adc_per_pe` 推荐放在 `calibration`。
- 描述性信息如 `operator`、`sample`、`comment` 放在 `meta`。
- **术语统一**：DAQ/CLI 数据集名称使用 `run_name`，Context/API 数据访问使用显式 `run_id`。

## 术语说明

### `run_id` vs `run_name`

在 WaveformAnalysis 系统中，两个术语分别属于不同边界：

- **`run_name`**：DAQ/CLI 使用的数据集名称，通常对应 DAQ 根目录下的运行目录名。
  `waveform-process --run-name <run_name>` 使用该名称选择数据集。

- **`run_id`**：Context/API 访问数据时显式传入的运行标识符，用于所有数据读取和缓存范围
  - `ctx.get_data(run_id, 'peaks')`
  - 缓存目录结构：`{storage_dir}/{run_id}/_cache/`

`run_name` 和 `run_id` 在常见目录布局中可以是同一个字符串，但不要把它们当作同一个 API
参数。Context 不保存隐式当前 run，每次数据访问都必须显式传入 `run_id`。

`ctx.show_config(run_name=...)` 中的 `run_name` 是受支持的公开参数，仅用于全局配置视图中标注缓存目录，
不会发出弃用警告；它不替代数据 API 的 `run_id`。

**使用示例**：

```python
# DAQ/CLI 数据集名称
run_name = 'my_run'
waveform_process_args = ['--run-name', run_name]

# Context 数据访问标识
run_id = run_name
ctx.get_data(run_id, 'peaks')
# 配置展示参数：标注该运行的缓存目录
ctx.show_config(run_name=run_name)
```

这样既能保持 DAQ/CLI 的数据集命名，又能让每次 Context 数据访问的作用域清晰可见。

## Context API 迁移

以下公开入口与冗余参数已移除，旧调用需要直接更新：

| 原调用 | 当前写法与语义 |
| --- | --- |
| `ctx.clear_config_cache()` | 删除手动清理调用；通过 `ctx.set_config(...)` 更新配置，自动失效解析配置与规划缓存。 |
| `ctx.clear_performance_caches()` | 删除手动维护调用；规划、lineage 与缓存键的失效由 Context 内部维护。 |
| `ctx.profiling_summary` | 使用 `ctx.profiler.summary()` 获取 profiler 摘要。 |
| `ctx.get_lineage(data_name, _visited=...)` | 使用 `ctx.get_lineage(data_name)`；循环检测状态只在内部递归中维护。 |
| `ctx.analyze_dependencies(..., run_id=...)` | 删除未使用的 `run_id`，保留目标名称和 `include_performance`。 |
| `DependencyAnalyzer.analyze(..., run_id=...)` | 同样删除未使用的 `run_id`。 |

```python
# 更新配置时自动失效相关内部缓存，不要直接修改 ctx.config 后手动清理
ctx.set_config({'threshold': 15}, plugin_name='hit_threshold')

# lineage 与依赖分析不需要运行标识
lineage = ctx.get_lineage('peaks')
analysis = ctx.analyze_dependencies('peaks', include_performance=True)
print(ctx.profiler.summary())

# 检查特定 run 的缓存状态和执行计划
plan = ctx.preview_execution('run_001', 'peaks')
```

`clear_cache_for(run_id, data_name)` 仍是清理指定运行产物的公开入口，与内部规划缓存失效职责不同。
`_clear_config_cache()` 和 `_invalidate_planning_caches()` 仅供内部维护，不作为迁移后的用户调用。
`show_config()`、`show_config(data_name)` 和 `show_config(run_name=...)` 均保留。

## 相关文档

- [Plugin DAG、lineage 与缓存](../../architecture/PLUGIN_DAG_LINEAGE_CACHE.md)
- [Agent 配置约束](https://github.com/SnowingWolf/WaveformAnalysis/blob/0bc56668c0d2ebf81fc391287fb0097cd94b49f7/docs/agents/configuration.md)
