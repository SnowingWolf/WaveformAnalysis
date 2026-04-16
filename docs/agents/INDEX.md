# Agent Docs Index

本页为 Agent 文档导航页。人类入口与硬约束统一在 `AGENTS.md`，生命周期真源统一在 `lifecycle.md`，执行流程与完成标准统一在 `workflows.md`。

## 快速入口
<!-- BEGIN GENERATED: quick_links -->
- 主入口（推荐）：`../../AGENTS.md`
- 生命周期：`lifecycle.md`
- 架构总览：`architecture.md`
- 插件体系：`plugins.md`
- 配置与兼容：`configuration.md`
- 常见工作流：`workflows.md`
- 协议模板：`protocol/README.md`
- `modify_plugin` 实例：`protocol/route-profiles/modify_plugin.md`
- `retire_compat` 实例：`protocol/route-profiles/retire_compat.md`
- `debug_cache` 实例：`protocol/route-profiles/debug_cache.md`
- `generate_docs` 实例：`protocol/route-profiles/generate_docs.md`
- `run_tests` 实例：`protocol/route-profiles/run_tests.md`
- `assess_change_impact` 实例：`protocol/route-profiles/assess_change_impact.md`
- `schema_compat_check` 实例：`protocol/route-profiles/schema_compat_check.md`
- `performance_regression_check` 实例：`protocol/route-profiles/performance_regression_check.md`
- `release_artifact_sync` 实例：`protocol/route-profiles/release_artifact_sync.md`
- 适配层说明：`adapters/skills.md`、`adapters/mcp.md`
- 约定与规范：`conventions.md`
- 参考索引：`references.md`
<!-- END GENERATED: quick_links -->

## 推荐阅读顺序
<!-- BEGIN GENERATED: recommended_read_order -->
1. `AGENTS.md`
2. `lifecycle.md`
3. `workflows.md`
4. `plugins.md`
5. `configuration.md`
6. `protocol/route-profiles/modify_plugin.md`
7. `protocol/route-profiles/retire_compat.md`
8. `protocol/route-profiles/debug_cache.md`
9. `protocol/route-profiles/generate_docs.md`
10. `protocol/route-profiles/run_tests.md`
11. `protocol/route-profiles/assess_change_impact.md`
12. `protocol/route-profiles/schema_compat_check.md`
13. `protocol/route-profiles/performance_regression_check.md`
14. `protocol/route-profiles/release_artifact_sync.md`
<!-- END GENERATED: recommended_read_order -->

## 质量闸门
- PR 固定闸门：见 `workflows.md` 中“PR 前固定质量闸门（3 类，4 条命令）”
- 扩展检查 / 发布前检查：见 `workflows.md` 中 `performance_regression_check` 与 `release_artifact_sync`

## 插件参考
- Agent 插件文档：`../plugins/reference/agent/INDEX.md`
- Auto 插件文档：`../plugins/reference/builtin/auto/INDEX.md`

## 维护约定
- 本页仅维护目录与跳转，不复制 `AGENTS.md` 的规则正文。
- `docs/agents/index.yaml` 必须覆盖本页提到的机器入口与 route 协议字段。
