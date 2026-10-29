# Context API 优化计划

> 状态：本轮已确认直接精简公开缓存维护入口、摘要属性与冗余参数；实现、文档系统与契约测试同步收敛。
> 范围：`waveform_analysis/core/context.py`、相关 domain、调用方与文档目录。
> 用户迁移说明：[配置管理](../features/context/CONFIGURATION.md#context-api-迁移)。

## 目标与边界

降低 Context 的维护复杂度，保持常用工作流、插件输出与缓存 lineage 语义。

- `show_config()` 是核心交互入口，保留无参全局展示、指定插件展示和 `run_name` 参数。
- Domain facade 是公开 API 边界；不因转发简短或仓库调用少而删除。
- 本轮删除范围已经用户确认，直接迁移，不保留旧入口别名或额外弃用周期。
- 其他公开 API 保留；旧分析记录的候选建议不构成新增删除授权。

## 本轮接口决策与迁移

| 原形式 | 当前契约 | 调用方迁移 |
| --- | --- | --- |
| `clear_config_cache()` | 配置缓存维护成为私有 `_clear_config_cache()`。 | 用户通过 `set_config(...)` 修改配置，删除手动清理调用。 |
| `clear_performance_caches()` | 私有 `_invalidate_planning_caches()` 调用缓存域 `invalidate_planning_caches()`。 | 用户删除手动维护调用；注册和配置更新负责自动失效。 |
| `profiling_summary` | 删除便捷属性。 | 使用 `ctx.profiler.summary()`。 |
| `get_lineage(data_name, _visited=...)` | 公共签名只接收 `data_name`；递归状态放在私有 `_get_base_lineage()`。 | 删除 `_visited` 参数。 |
| `analyze_dependencies(..., run_id=...)` | Context 与底层 `DependencyAnalyzer.analyze()` 均移除未使用的 `run_id`。 | 删除该参数；特定 run 的缓存预览使用 `preview_execution(run_id, data_name)`。 |
| `show_config(run_name=...)` 的错误弃用 | `run_name` 是受支持的展示参数，不发出弃用警告。 | 保持 `run_name` 写法；该入口不接受 `run_id`。 |

内部缓存维护方法不属于迁移后的用户 API。`set_config()` 自动清理解析配置、运行配置与规划缓存；
`clear_cache_for(run_id, data_name)` 继续负责指定 run 的产物清理。以上精简不改变插件配置优先级、
缓存键身份或 lineage 内容。

## 保留的 API 分层

| 分类 | 方法 | 用途 |
| --- | --- | --- |
| 核心数据 | `get_data`, `register`, `set_config`, `clear_cache_for` | 数据处理与缓存生命周期。 |
| 配置读取 | `get_config`, `get_config_value`, `get_resolved_config` | 裸值、单项来源和完整解析结果。 |
| 配置展示 | `show_config`, `list_plugin_configs`, `show_resolved_config` | 全局汇总、插件选项和解析来源。 |
| 依赖与执行 | `get_lineage`, `resolve_dependencies`, `preview_execution`, `analyze_dependencies` | 缓存身份、拓扑顺序、run/cache 预览与关键路径分析。 |
| 缓存诊断 | `analyze_cache`, `cache_stats`, `diagnose_cache` | 现有 Context 存储与插件注册范围内的诊断。 |
| 时间 | `time_range`、epoch 和时间索引方法 | 时间查询、换算与索引生命周期。 |
| 帮助 | `help` | 返回终端/Jupyter 可显示的结构化 `HelpDocument`，查询当前已注册插件。 |

`show_config(data_name)` 仍会委托 `list_plugin_configs()` 显示插件配置清单，不能把全局视图说明理解为删除指定插件能力。

## 已完成的前序精简

| API | 替代写法 | 决策 |
| --- | --- | --- |
| `register_plugin_()` | `register()` | 已删除，不保留兼容 facade。 |
| `has_explicit_config(plugin, name, adapter_name=None)` | `get_config_value(plugin, name, adapter_name=...).source == ConfigSource.EXPLICIT` | 已确认直接删除，domain helper 一并收敛。 |
| `quickstart(template="basic")` | `help("examples")` 或[快速上手](../user-guide/QUICKSTART_GUIDE.md) | 已删除，静态帮助主题与 reserved name 同步删除。 |

## 实施与验收

1. 核心实现与内部调用迁移，保留正常配置自动失效、BatchProcessor 和数据缓存行为。
2. 定向契约测试验证公开签名、旧入口缺席、lineage/缓存键与配置展示行为。
3. 同步 API catalog、参数说明、用户指南和活动架构文档；历史归档保持原样。
4. 有意更新本轮删除涉及的内容覆盖基线，并生成当前 site model fixture。
5. 通过文档同步、锚点检查、影响分析、schema 冒烟及真实隔离站点构建，暂存验证后的打包导出。
6. 独立 Reviewer 审查通过后，由主流程提交本轮改动。

执行证据与最终状态以当前任务记录 `docs/agents/runs/current/context-api-retirement-20261029/task.yaml` 为准。
