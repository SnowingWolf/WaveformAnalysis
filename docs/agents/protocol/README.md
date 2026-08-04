# Agent Protocol Scaffold

本目录存放仓库中立的 agent 协议模板，不绑定具体运行时。

## 目录约定
- `task-lifecycle.md`：仓库级状态机摘要，和 `docs/agents/lifecycle.md` 保持一致。
- `artifacts/`：交接产物模板；`retire_compat` 额外使用 `compat_inventory.md`，`compact` 使用 `task_report.md`。
- `route-profiles/`：route 子状态与 gate 绑定模板。

## 设计原则
- 真源在 `docs/agents/`，本目录提供执行侧模板。
- 适配层只能映射，不应改写生命周期语义。
- 任何新增 route 都应先补生命周期和 artifact 约束，再考虑 skill/MCP 接入。

## 路径说明
- 本仓库的 `.agents/` 是只读挂载，用于现有 skill 资产。
- 因此协议模板落在 `docs/agents/protocol/`，避免和只读挂载冲突。

## 最短使用流程
1. 先选择 route profile；若没有专用 profile，先从 `route-profiles/template.md` 起草。
2. `staged` 在 `planning`、`executing`、`reviewing` 结束前依次填写三份 artifact。
3. `compact` 在执行结束前填写 `artifacts/task_report.md`；`direct` 只在最终回复记录验证结果。
4. 按 `review_report.decision` 或 `task_report.decision` 驱动状态迁移：
   - `completed`
   - `rework_required`
   - `blocked`
   - `failed`

## 当前可直接复用的实例
- `route-profiles/modify_plugin.md`
- `route-profiles/retire_compat.md`
- `route-profiles/debug_cache.md`
- `route-profiles/generate_docs.md`
- `route-profiles/run_tests.md`
- `route-profiles/schema_compat_check.md`
- `route-profiles/assess_change_impact.md`
- `route-profiles/performance_regression_check.md`
- `route-profiles/release_artifact_sync.md`

## Alias 约定
- `release_check` 复用 `route-profiles/release_artifact_sync.md`
- 对 alias route 不单独维护第二份 profile，避免语义漂移

## Agent Profile 约定
- `agent_role` 定义状态所有权；`agent_profile` 定义具体执行者的专项能力，两者不能混用。
- profile 选择统一记录在 `agent_profile`，并在三阶段复用同一个 id。
- `planning` 使用 `profile_plan` 记录专项计划输入，最终计划仍由 `planner` 负责。
- `executing` 使用 `executor_role` 记录 profile 实际承担的生命周期角色。
- `reviewing` 使用 `agent_profile_review` 记录专项审查，放行权仍归 `reviewer`。
- profile 必须在 `docs/agents/index.yaml` 注册，并至少绑定一个适用 route 的 executor role。
- profile 不拥有生命周期状态，也不能替代 `planner` 决策或 `reviewer` 放行。
- `compact` 可将 `profile_plan`、执行绑定和 `agent_profile_review` 折叠到 `task_report`；一旦命中 staged 升级条件，仍须恢复独立 `Planner`/`Reviewer` 权限边界。

## 使用约束
- 模板优先给 agent 直接复制、填空、交接，不要求额外转换格式。
- 若 route profile 已声明字段，artifact 不应发明新的同义字段。
- 需要返工时，`review_report` 必须显式给出 `scope_changed`，决定回到 `executing` 还是 `planning`。
