# Agent Protocol Scaffold

本目录存放仓库中立的 agent 协议说明与兼容入口，不绑定具体运行时。

## Canonical Task Record

活动任务唯一写入
`docs/agents/runs/current/<task-id>/task.yaml`，格式由
`docs/agents/schema/agent-task.schema.json` 定义。记录分为：

- `spec`：目标、canonical route、workflow cost/shape、风险、基线、允许路径、验收条件、gates 与角色分配。
- `status`：当前生命周期状态、transition history、spec digest、execution/review/approval/handoff 证据。

CLI 只负责创建、校验、记录迁移与归档，不代表 agent 执行命令，也不代表用户批准。scope 或验收条件改变时必须递增 `metadata.generation`，重新规划并使旧执行、审查和批准证据失效。

## 兼容与历史

- `artifacts/` 下的 `plan_brief.md`、`execution_report.md`、`review_report.md`、`task_report.md`、`compat_inventory.md` 只保留为 deprecated 兼容入口，不是活动状态。
- 旧报告原样保存在 `runs/archive/legacy/`，由 `MANIFEST.json` 记录来源、归档路径、字节数和 SHA-256；归档内容只读，不参与路由或放行。
- `plans/INDEX.md` 与 `plans/active.yaml` 是从当前 `task.yaml` 生成的兼容视图；不要编辑它们作为第二真源。

## 生命周期与路由

- `task-lifecycle.md`：生命周期摘要；完整状态机见 `docs/agents/lifecycle.md`。
- `route-profiles/`：按 `index.yaml` 动态渲染的 route 摘要与人工操作说明。
- 任何新增 route 都应先补机器契约和对应 profile，再考虑 skill/MCP 接入。

## 最短使用流程

1. 从 `docs/agents/index.yaml` 选择 canonical route，并读取其 `read_order`。
2. 用 `scripts/agent_workflow.py init` 创建 current `task.yaml`；不要复制 deprecated artifact 模板。
3. 按 route 的合法迁移记录 `planning -> ready_for_execution -> executing -> reviewing`。
4. 用 `scripts/agent_workflow.py validate` 检查 schema、scope、digest、gates 和证据；终态任务再用 `archive` 迁入 archive。
5. 运行 `python scripts/render_agent_docs.py --write` 刷新兼容导航视图。

## Agent Profile 约定

- `agent_role` 定义状态所有权；`agent_profile` 定义具体执行者的专项能力，两者不能混用。
- profile 选择记录在 `spec.assignment` 与对应 status evidence 中，并贯穿 planning、executing、reviewing。
- profile 不拥有生命周期状态，也不能替代 `planner` 决策或 `reviewer` 放行。
