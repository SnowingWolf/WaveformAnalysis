# Agent Docs Index

本页为 Agent 文档导航页。主入口与硬约束统一在 `AGENTS.md`。

## 快速入口
- 主入口（推荐）：`../../AGENTS.md`
- 架构总览：`architecture.md`
- 插件体系：`plugins.md`
- 配置与兼容：`configuration.md`
- 常见工作流：`workflows.md`
- 约定与规范：`conventions.md`
- 参考索引：`references.md`

## 推荐阅读顺序
1. `../../AGENTS.md`
2. `plugins.md`
3. `configuration.md`
4. `workflows.md`

## 质量闸门入口（PR 前固定，按改动类型触发）
- `waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/`
- `waveform-docs generate plugins-agent -o docs/plugins/reference/agent/`
- `python scripts/assess_change_impact.py --base HEAD`
- `python scripts/schema_compat_check.py --base HEAD --run-smoke`

## 插件参考
- Agent 插件文档：`../plugins/reference/agent/INDEX.md`
- Auto 插件文档：`../plugins/reference/builtin/auto/INDEX.md`

## 维护约定
- 本页仅维护目录与跳转，不复制 `AGENTS.md` 的规则正文。
