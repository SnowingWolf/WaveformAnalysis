# 配置管理

本文档说明 `Context` 配置解析、DAQ adapter 推断、兼容参数映射与配置类型。Agent 侧约束见 `docs/agents/configuration.md`；本文件是用户与代码锚点使用的配置入口。

`Context` 保持无状态的数据访问接口；配置解析由内部的 `ContextConfigDomain` 承接，
不改变 `ctx.set_config()`、`ctx.get_config()` 或 `ctx.get_resolved_config()` 的用法。

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
- **术语统一**：使用 `run_id` 作为运行标识符，避免使用已弃用的 `run_name`。

## 术语说明

### `run_id` vs `run_name`

在 WaveformAnalysis 系统中，我们统一使用 `run_id` 作为运行的唯一标识符：

- **`run_id`**：推荐的运行标识符，用于所有 API 调用
  - `ctx.get_data(run_id, 'peaks')`
  - 缓存目录结构：`{storage_dir}/{run_id}/_cache/`

- **`run_name`**：已弃用，请使用 `run_id` 代替
  - 在 `ctx.show_config()` 中的 `run_name` 参数已弃用
  - 将在未来版本中移除

**迁移示例**：

```python
# ❌ 旧方式（已弃用）
ctx.show_config(run_name='my_run')

# ✅ 新方式（推荐）
run_id = 'my_run'
ctx.get_data(run_id, 'peaks')
ctx.show_config(run_id=run_id)  # 会显示 deprecation warning
```

统一使用 `run_id` 有助于：
- 避免术语混淆
- 与缓存目录结构保持一致
- 提供更清晰的 API 语义

## 相关文档

- [Plugin DAG、lineage 与缓存](../../architecture/PLUGIN_DAG_LINEAGE_CACHE.md)
- [执行预览](PREVIEW_EXECUTION.md)
- [插件管理](PLUGIN_MANAGEMENT.md)
- [Agent 配置约束](../../agents/configuration.md)
