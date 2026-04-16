# Agent Protocol Scaffold

本目录存放仓库中立的 agent 协议模板，不绑定具体运行时。

## 目录约定
- `task-lifecycle.md`：仓库级状态机摘要，和 `docs/agents/lifecycle.md` 保持一致。
- `artifacts/`：交接产物模板；`retire_compat` 额外使用 `compat_inventory.md`。
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
2. 在 `planning` 结束前填写 `artifacts/plan_brief.md`。
3. 在 `executing` 结束前填写 `artifacts/execution_report.md`。
4. 在 `reviewing` 结束前填写 `artifacts/review_report.md`。
5. 按 `review_report.decision` 驱动状态迁移：
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

## 使用约束
- 模板优先给 agent 直接复制、填空、交接，不要求额外转换格式。
- 若 route profile 已声明字段，artifact 不应发明新的同义字段。
- 需要返工时，`review_report` 必须显式给出 `scope_changed`，决定回到 `executing` 还是 `planning`。
