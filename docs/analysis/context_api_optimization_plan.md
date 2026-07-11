# Context API 优化计划

> 状态：规划，尚未执行 API 删除或弃用。
> 范围：`waveform_analysis/core/context.py` 及其公开的 `PluginMixin` 方法。

## 目标与边界

本计划的目标是降低 Context 的维护复杂度，同时保持常用工作流、插件契约、缓存 lineage 和公开 Python API 稳定。

- `show_config()` 是核心交互入口，完整保留，包括无参全局展示和指定插件展示。
- 不因仓库内调用次数低而删除公开方法；公开导出的 `Context` 可能被外部用户调用。
- Domain facade 的一行转发是稳定 API 边界，不按“重复代码”处理。
- 没有语义等价替代方案的 API 不进入弃用或删除范围。

## 当前基线与前置修复

提交 `bdbad63` 错误地把 `show_config(run_name=...)` 标记弃用，并在示例中使用当前签名不支持的 `show_config(run_id=...)`。在开始任何优化前，必须先单独修复：

1. 恢复 `show_config(run_name=...)` 为非弃用、可用的公开参数。
2. 恢复所有示例使用 `run_name`，或在未来先实现真实的 `run_id` 参数后再迁移。
3. 删除这次错误弃用带来的 warning、Sphinx 弃用标记和不成立的迁移说明。
4. 添加覆盖 `show_config()`、`show_config(plugin_name)` 和 `show_config(run_name=...)` 的回归测试。

此修复不属于 API 优化，而是恢复既有契约。

## API 分层

### 必须保留

| 分类 | 方法 | 原因 |
| --- | --- | --- |
| 核心数据 | `get_data`, `register`, `set_config`, `clear_cache_for` | 数据处理和缓存生命周期主入口。 |
| 配置读取 | `get_config`, `get_config_value`, `get_resolved_config`, `has_explicit_config` | 分别提供裸值、单项来源信息、完整解析结果和显式配置判断。 |
| 配置展示 | `show_config`, `list_plugin_configs`, `show_resolved_config` | 展示全局配置、插件选项和解析来源，职责不同。 |
| 依赖与执行 | `get_lineage`, `resolve_dependencies`, `preview_execution`, `analyze_dependencies` | 分别服务缓存身份、拓扑顺序、run/cache 感知预览和性能/关键路径分析。 |
| 时间 | `time_range`、epoch 和时间索引方法 | 时间查询、绝对时间换算和索引生命周期接口。 |

### 仅在证明安全后处理

| 候选 | 计划动作 | 前提 |
| --- | --- | --- |
| `get_lineage(data_name, _visited=...)` | 将 `_visited` 移入私有递归 helper，公共签名只保留 `data_name`。 | 增加 lineage 与缓存键回归测试。 |
| `register_plugin_` | 先盘点直接调用方和公开文档；仅在提供稳定迁移期后私有化。 | 不得影响插件加载、spec 校验或外部扩展。 |
| `clear_performance_caches` | 保留行为，先更正其“规划/lineage/key 缓存失效”语义和文档。 | 证明没有脚本依赖旧名称。 |
| `help`, `quickstart` | 评估是否改为稳定文档链接；默认保留。 | 用户确认弃用周期和外部 API 迁移策略。 |
| `analyze_cache`, `cache_stats`, `diagnose_cache` | 暂不弃用。 | `waveform-cache` 必须与 Context 在存储目录、插件注册和版本诊断上语义一致。 |

## 分阶段执行

### Phase 0：恢复正确基线

- 修复 `bdbad63` 对 `show_config` 的错误弃用。
- 为常用的配置展示行为建立回归测试。
- 仅完成本阶段并通过审查后，才进入优化工作。

### Phase 1：建立公开 API 契约测试

- 为配置、缓存、时间、依赖和展示方法建立最小的 Context facade 测试。
- 将“仓库内部调用”和“公开 Python API”分开记录。
- 明确每项 API 的输入、返回值、副作用、缓存/lineage 影响和推荐使用场景。

### Phase 2：无行为变化的内部收敛

- 抽取 `get_lineage` 的递归状态到私有 helper。
- 修正文档中内部入口与公开入口的混淆，例如只推荐 `register()`。
- 不删除、不重命名、不发出公开 API warning。

### Phase 3：诊断与展示体验优化

- 保持 `show_config()` 为主配置展示入口。
- 明确三个展示入口：`show_config()` 看当前配置汇总，`list_plugin_configs()` 看单插件选项，`show_resolved_config()` 看配置来源。
- 评估将 `preview_execution()` 和缓存诊断的“结构化数据”与“打印展示”分开，保持现有调用兼容。

### Phase 4：逐项弃用决策

- 只处理已经具备语义等价替代方案、测试和迁移文档的公开 API。
- 每个候选必须独立提供 `compat_inventory`，并记录 `deprecated_in`、`removed_in`、替代代码和用户确认。
- 跨至少一个完整 MINOR 发布周期后，才允许在 MAJOR 版本移除。

## 不纳入当前优化范围

- 删除 `show_config()` 或其指定插件展示能力。
- 删除 `get_config_value()`、`get_config()` 或 `get_resolved_config()`。
- 用 `preview_execution()` 替代 `analyze_dependencies()`。
- 用 `time_range()` 直接替代 `get_data_time_range_absolute()`。
- 在未修复 CLI 语义差异前，将缓存诊断 API 迁移到 `waveform-cache`。

## 验收标准

每个执行阶段必须满足：

```bash
python -m pytest tests/test_context_core.py tests/test_context_core_clone.py \
  tests/test_context_core_time.py tests/test_context_core_preview.py -v
python -m pytest tests/contracts/test_compat_deprecation.py \
  tests/contracts/test_cache_consistency.py tests/contracts/test_plugin_contracts.py -v
python scripts/assess_change_impact.py --base HEAD
python scripts/schema_compat_check.py --base HEAD --run-smoke
scripts/check_doc_sync.sh
python scripts/check_doc_anchors.py --check-sync --base HEAD
```

若变更公开 API，额外要求：用户确认删除范围、完整 `compat_inventory`、迁移文档和独立 Reviewer 放行。
