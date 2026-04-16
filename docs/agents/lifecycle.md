# Agent Task Lifecycle

本页定义仓库级 task lifecycle 状态机。`AGENTS.md` 继续负责硬约束，`workflows.md` 继续负责任务流程，本页负责统一说明任务在多 agent 协作中的状态、迁移、阻断与返工规则。

## 目标
- 为 `Planner -> Executor -> Reviewer` 协作提供统一状态机。
- 将用户确认、权限批准、阻断、返工做成显式状态，而不是散落在注释里。
- 让 `docs/agents/index.yaml` 可以作为机器可读的生命周期真源。

## 主状态

| 状态 | 所有者 | 含义 | 允许退出 |
| --- | --- | --- | --- |
| `created` | system | 任务已创建，尚未进入规划 | `planning` |
| `planning` | planner | 任务拆解、风险识别、route 选择、gate 选择 | `awaiting_user_input` / `awaiting_approval` / `ready_for_execution` / `blocked` / `cancelled` |
| `awaiting_user_input` | planner | 缺少用户决策或关键信息 | `planning` |
| `awaiting_approval` | planner | 需要权限提升或危险动作批准 | `ready_for_execution` / `blocked` / `cancelled` |
| `ready_for_execution` | planner | `plan_brief` 已完备，可交给执行者 | `executing` |
| `executing` | executor | 在授权范围内执行实现、检查或文档同步 | `reviewing` / `blocked` / `failed` / `cancelled` |
| `reviewing` | reviewer | 统一检查 gate、契约、一致性与残余风险 | `completed` / `rework_required` / `blocked` / `failed` / `cancelled` |
| `rework_required` | reviewer | 审查发现可修复问题，需要返工 | `executing` / `planning` |
| `blocked` | current owner | 被外部依赖、权限、环境或缺失输入阻塞 | `planning` / `executing` / `cancelled` |
| `completed` | reviewer | 所有阻断 gate 通过，产物齐全 | 终态 |
| `failed` | executor/reviewer | 出现不可继续的失败 | 终态 |
| `cancelled` | any | 任务被取消 | 终态 |

## 标准迁移
```text
created -> planning
planning -> awaiting_user_input | awaiting_approval | ready_for_execution | blocked | cancelled
awaiting_user_input -> planning
awaiting_approval -> ready_for_execution | blocked | cancelled
ready_for_execution -> executing
executing -> reviewing | blocked | failed | cancelled
reviewing -> completed | rework_required | blocked | failed | cancelled
rework_required -> executing
rework_required -> planning  # 仅当 scope_changed=true
blocked -> planning | executing | cancelled
```

## 状态语义
- `awaiting_user_input`：
  缺的是产品/范围/优先级决策，而不是执行细节。拿到用户回复后必须回到 `planning` 重新生成或修正 `plan_brief`。
  `retire_compat` 若命中 `medium/high` 风险且触及 public surface，也应进入该状态，等待删除范围确认。
- `awaiting_approval`：
  用于权限提升、网络访问、潜在破坏性操作。批准通过后进入 `ready_for_execution`；批准被拒绝时统一进入 `blocked`，并记录 `blocker_type=approval_denied`。
- `blocked`：
  表示当前 owner 无法继续推进，但任务本身未失败。恢复点由阻断来源决定：规划期阻断回 `planning`，执行期阻断回 `executing`。
- `failed`：
  用于不可继续的执行失败或审查失败，不默认进入返工闭环。
- `rework_required`：
  只能由 `reviewer` 产生，且必须附带 `rework_reason`、`required_fixes`、`owner_role`。默认 owner 为当前 route 的 executor。

## 返工规则
- 默认返工路径：`reviewing -> rework_required -> executing`
- 只有在以下情况允许 `rework_required -> planning`：
  - 审查发现范围定义错误
  - 用户目标发生变化
  - gate 结果要求重新选 route 或重做任务分解
- `Reviewer` 在打回时必须明确：
  - `scope_changed: true/false`
  - `required_gates_to_rerun`
  - `blocking_vs_non_blocking_findings`

## 人工节点
- `awaiting_user_input` 是正式状态，不应隐藏在普通消息中。
- `awaiting_approval` 是正式状态，用于权限批准与高风险操作授权。
- 普通进度同步不算状态迁移，只算事件。

## 交接产物

### `plan_brief`
- 由 `Planner` 生成。
- 离开 `planning` 进入 `ready_for_execution` 前必须存在。
- 最少包含：
  - `task_id`
  - `route`
  - `risk_level`
  - `scope_in`
  - `scope_out`
  - `required_gates`
  - `executor_role`

### `compat_inventory`
- 仅用于 `retire_compat`。
- 在 `planning` 阶段先于 `plan_brief` 完成。
- 最少包含：
  - `task_id`
  - `route`
  - `inventory_scope`
  - `canonical_policy`
  - `compat_items`

### `execution_report`
- 由 `Executor` 生成。
- 离开 `executing` 进入 `reviewing` 前必须存在。
- 最少包含：
  - `changed_paths`
  - `actions_taken`
  - `commands_run`
  - `open_risks`
  - `requested_review_focus`

### `review_report`
- 由 `Reviewer` 生成。
- 离开 `reviewing` 进入 `completed` 前必须存在。
- 最少包含：
  - `gate_results`
  - `decision`
  - `blocking_findings`
  - `residual_risks`
  - `follow_up_actions`

## 与质量闸门的绑定
- 所有 route 都必须经过 `reviewing`，即使是文档-only 任务。
- `Reviewer` 负责把 gate 结果映射到状态：
  - 全部阻断 gate 通过：`completed`
  - gate 失败但可修复：`rework_required`
  - gate 无法执行或受外部条件阻断：`blocked`
  - gate 表明任务结果不可继续：`failed`
- `modify_plugin` 默认绑定：
  - `assess_change_impact`
  - `schema_compat_check`
  - `doc_sync`
  - `doc_anchors`
- `retire_compat` 默认绑定：
  - `compat_inventory_ready`
  - `deletion_scope_confirmed`
  - `doc_sync`
  - `doc_anchors`
  - `impact_assessed_if_needed`
  - `schema_checked_if_needed`

## Route 子状态
- 子状态只能细化 route 内部流程，不能替代主状态。
- 推荐把 route 子状态绑定到“任务上下文”或 `plan_brief`，不要单独扩展主状态机。
- 当前重点子状态：
  - `modify_plugin`: `impact_assessed`, `version_checked`, `tests_selected`, `docs_sync_required`
  - `retire_compat`: `inventory_built`, `risk_banded`, `deletion_scope_confirmed`, `gates_selected`
  - `generate_docs`: `doc_targets_resolved`, `sync_checks_pending`
  - `schema_compat_check`: `schema_diff_detected`, `smoke_required`

## 审查阻断规则
- 以下情况必须进入 `rework_required`，不能直接 `completed`：
  - 插件契约变化但 `version` 未升级
  - 字段或 dtype 变化但未执行兼容检查
  - 删除兼容入口但未附 `compat_inventory`
  - 中高风险兼容删除未记录确认或迁移说明
  - 用户可见行为变化但文档未同步
  - 命中固定闸门但结果未附在 `review_report`
- 以下情况应进入 `blocked`：
  - 权限提升被拒绝
  - 缺少运行 `run_id`、基线引用等关键外部输入
  - 环境缺依赖导致 gate 无法执行

## 当前落地边界
- 本轮只定义协议，不实现调度器或 trace backend。
- `docs/agents/index.yaml` 是生命周期的机器真源。
- `docs/agents/protocol/` 提供可复用模板，供 skills、MCP 等适配层消费。
