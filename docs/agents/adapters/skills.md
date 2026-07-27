# Skills Adapter Notes

本页定义具体 agent profile 与生命周期角色之间的映射。profile 表达执行者的专项能力，role 仍负责状态所有权和 artifact 交接。

## 映射原则
- `planner` skill 消费 `plan_brief` 模板。
- `executor.*` skill 消费 route profile 和 `execution_report` 模板。
- `reviewer` skill 消费 gate 规则和 `review_report` 模板。
- 选择专项执行者时，在 `plan_brief.executor_profile` 与 `execution_report.executor_profile` 记录 profile id。
- profile 必须从当前 route 的 `handoff_sequence` 中选择一个允许的 `executor_role`。
- profile 不拥有生命周期状态，也不能替代阻断式 `reviewer`。

## Agent Profiles

<!-- BEGIN GENERATED: agent_profile_catalog -->
### `graph_engineer`
- DAG、lineage、图布局与图可视化专项执行者
- 可承担角色：`executor.plugin`, `executor.config`, `executor.docs`
- 适用 route：`modify_plugin`, `debug_cache`, `generate_docs`
- 能力：`plugin_dag`, `runtime_lineage`, `graph_layout`, `graph_visualization`
- 必审项：`dependency_direction`, `runtime_vs_display_semantics`, `cross_renderer_consistency`
- 约束：
  - 必须从所选 route 的 handoff 中选择一个允许的 executor_role。
  - 除非 scope 明确要求，否则运行时图语义与仅展示变换必须分离。
  - 必须保留 route 的 reviewer，此 profile 不能自行批准完成。
<!-- END GENERATED: agent_profile_catalog -->

## 当前边界
- profile 是机器契约中的选择与校验层，不代表仓库已经安装同名 skill 或外部 agent。
- 现有 `.agents/skills/create-pr/` 不纳入生命周期状态机。
