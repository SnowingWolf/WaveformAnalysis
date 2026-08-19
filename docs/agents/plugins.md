# Agent Plugins Guide

## 插件契约
每个插件至少声明：
- `provides`
- `depends_on`
- `options`
- `version`
- `output_dtype` 或 output kind

## Bundle 组织

- 每个正式 `provides` 对应 `waveform_analysis/core/plugins/builtin/<provides>/` 下的独立 bundle。
- `manifest.yaml` 声明插件属主、版本与依赖，bundle 根目录的 `__all__` 声明公开导出。
- `hit`、`peaks`、`builtin.cpu` 等兼容入口可以转发名称，但不取得兄弟插件的代码属主。
- Plugin Set 与 Profile 只负责组合，不拥有插件实现。
- 完整目录、共享计算和兼容规则见[插件系统与模板 API](../plugins/PLUGIN_SYSTEM_OVERVIEW.md)。

## 变更检查单
1. `provides` 是否稳定且唯一
2. `depends_on` 与 `resolve_depends_on()` 是否一致
3. `options` 默认值、类型、help 是否完整
4. 输出字段是否与消费方兼容
5. 是否需要同步更新插件文档

## Execution Backend Policy
新增或修改插件算法时，`Planner` 必须在 `plan_brief` 记录执行后端决策，`Reviewer` 必须在 `review_report` 审查执行风格。

### 后端枚举
- `python`: 少量数据、控制流复杂、性能不敏感的路径。
- `numpy`: 可向量化且不需要 JIT 的数组路径。
- `numba_serial`: CPU-bound 热点，单线程 JIT 能降低 Python 循环开销。
- `numba_parallel`: 已验证 parallel loop 有收益的 CPU-bound 路径。
- `thread_pool`: IO-bound、文件级任务，或底层释放 GIL 的任务。
- `process_pool`: CPU-bound 且不适合 Numba/向量化、序列化成本可接受的任务。

### 默认选择
1. 新 CPU 插件默认优先 `numpy` 或 `numba_serial`。
2. IO/file 解析优先在线程池或进程池中做文件级并行，不在算法内再叠加并行层。
3. `numba_parallel` 必须有 benchmark 或既有性能证据；memory-bound 任务默认不用 `parallel=True`。
4. 同一执行路径只允许一个并发层，禁止 Numba parallel 外再套线程池/进程池。
5. Numba 不可用、输入为空、非连续数组等 fallback 必须显式说明。

### 参数命名
- 新 worker 配置优先使用 `max_workers`。
- Numba 线程数使用 `numba_threads`。
- 旧 `n_jobs`、`channel_workers`、`n_workers` 只作为兼容或后续收敛对象；新增配置不得继续扩散这些命名。

## 改动等级与动作映射
| 等级 | 典型改动 | 必要动作 |
| --- | --- | --- |
| `L1` | 算法内部调整（契约不变） | 建议 bump patch；补定向 + 边界测试 |
| `L2` | 配置语义变化、字段变化 | 必须 bump 版本；补 dtype/字段兼容测试；更新 `plugins-agent` |
| `L3` | `provides` 或依赖链变化 | 必须 bump 版本；做下游回归；同步路由与流程文档 |

说明：`provides` 变化一律按高风险 `L3` 处理。

## 推荐入口
- 流程入口：`docs/agents/workflows.md`
- 机器参考：`docs/plugins/reference/agent/INDEX.md`
- 生成命令：`waveform-docs generate plugins-agent`

## Version 升级策略
插件 `version` 是缓存 lineage 的关键组成部分，必须在行为变更时正确升级。

### 升级规则概览
- **MAJOR**：契约破坏性变更（删除字段、改变字段类型/语义、删除配置项）。
- **MINOR**：算法路径变更、新增字段/配置、修改默认参数。
- **PATCH**：bug 修复、性能优化（不改变算法逻辑）。

### 关键判断
- **算法路径变更**：即使输出 dtype 和字段名不变，只要内部实现路径变化（如从 Python 循环改为 Numba JIT、从逐条处理改为批量预分配），就应升级 MINOR 版本。
- **保守原则**：不确定时，优先升级 MINOR 而非 PATCH。

### 详细规则
完整的升级场景、示例和决策流程，详见：
- [插件系统与模板 API](../plugins/PLUGIN_SYSTEM_OVERVIEW.md)

### 实际案例
- `hit_merged` v1.1.1 → v1.1.2：预分配路径优化，算法路径变更 → MINOR 升级。
- `hit_merged_features` v0.2.0 → v0.3.0：从 Python 改为 Numba 单 pass → MINOR 升级。
