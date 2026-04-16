# Agent Workflows

本页定义常见任务的标准 workflow。状态机真源见 `lifecycle.md`，机器可读路由见 `index.yaml`。

## 通用协作模型
- 拓扑固定：`Planner -> Executor -> Reviewer`
- 主状态固定：`created -> planning -> ready_for_execution -> executing -> reviewing -> completed`
- 可选状态：`awaiting_user_input`、`awaiting_approval`、`rework_required`、`blocked`、`failed`、`cancelled`
- 阻断式审查：`Reviewer` 未放行前，不得进入 `completed`

## 通用交接产物
- `plan_brief`
  - 由 `Planner` 生成
  - `planning -> ready_for_execution` 前必须存在
- `compat_inventory`
  - 仅用于 `retire_compat`
  - 在 `planning` 阶段先于 `plan_brief` 完成，用于锁定删除范围
- `execution_report`
  - 由 `Executor` 生成
  - `executing -> reviewing` 前必须存在
- `review_report`
  - 由 `Reviewer` 生成
  - `reviewing -> completed` 前必须存在

## 通用 Commit Handoff
- `Executor` 在离开 `executing` 前必须检查工作树：`git status --short`、`git diff --stat`
- 若当前任务留下仓库改动，必须二选一：
  - 已完成提交，并在最终回复或交接中记录 `commit hash`
  - 明确记录 `未提交` 原因
- 默认不强制自动提交；是否提交遵循用户要求，但提交状态不能缺失
- 可执行：
  - `python scripts/check_agent_handoff.py`
  - `python scripts/check_agent_handoff.py --allow-uncommitted --reason "<原因>"`
- `Reviewer` 发现提交状态未说明时，必须打回，不能直接 `completed`

## 通用返工规则
- 默认返工路径：`reviewing -> rework_required -> executing`
- 仅当 `scope_changed=true` 时允许回到 `planning`
- 权限批准被拒绝统一进入 `blocked`

## Workflow: 修改插件

### 目标
在不破坏现有 pipeline 的前提下，完成插件改动并保证可回归、可追溯、可文档化。

### Lifecycle Profile
- route: `modify_plugin`
- profile: `reviewed_change`
- handoff: `planner -> executor.plugin -> reviewer`
- 子状态：
  - `impact_assessed`
  - `version_checked`
  - `tests_selected`
  - `docs_sync_required`

### Planner
1. 判级：`L0/L1/L2/L3`
2. 确认目标插件、上下游依赖、消费方与契约风险
3. 生成 `plan_brief`，明确：
   - 是否影响 `provides`、`depends_on`、`options`、`output_dtype`、`version`
   - 必跑 gate
   - 返工是否可能回到 `planning`

### Executor
1. 实现改动：先最小可运行，再做必要重构
2. 执行定向测试与文档更新
3. 产出 `execution_report`

### Reviewer
1. 审查 `version` 策略是否符合变更等级
2. 核对 gate 结果、契约一致性与文档同步
3. 核对 commit handoff 是否明确
4. 产出 `review_report`
5. 决策：
   - 全部通过：`completed`
   - 可修复问题：`rework_required`
   - 外部阻断：`blocked`

### 改动分级矩阵

| Level | 触发条件 | version 策略 | 最低测试要求 | 文档要求 | 审查动作 |
| --- | --- | --- | --- | --- | --- |
| `L0` | 仅注释/文档，不改行为 | 不变 | 文档检查 | 更新对应文档 | 可直接完成 |
| `L1` | 算法内部调整，输出契约不变 | 建议升级 patch | 定向测试 + 边界测试 | 更新 workflow/说明（必要时） | 检查 tests 与残余风险 |
| `L2` | 配置语义或输出字段变化 | 必须升级（至少 minor） | 定向测试 + 边界测试 + dtype/字段兼容测试 | 更新 `plugins-agent` 页面与 agent 流程文档 | 未升级 version 必打回 |
| `L3` | `provides`/依赖链/pipeline 行为变化 | 必须升级（优先 minor/major） | 增加下游兼容回归 | 同步更新路由与插件参考 | 强制检查下游兼容 |

### 固定 gate 与命令
```bash
waveform-docs generate plugins-agent --plugin <provides>
python scripts/assess_change_impact.py --base HEAD
python scripts/schema_compat_check.py --base HEAD --run-smoke
./scripts/run_tests.sh -v -k <plugin_or_feature_keyword>
python scripts/render_agent_docs.py --check
scripts/check_doc_sync.sh
python scripts/check_doc_anchors.py --check-sync --base HEAD
```

### 必须打回的情况
1. 插件契约变化但未升级 `version`
2. 字段或 dtype 变化但未执行兼容检查
3. 用户可见行为变化但 `plugins-agent` 或 `docs/agents` 未同步
4. `review_report` 未记录 gate 结果
5. 提交状态未说明，或存在未提交改动但未给出原因

### Definition of Done
1. `plan_brief`、`execution_report`、`review_report` 齐全
2. 版本策略符合改动等级
3. 固定 gate 通过
4. 需要时已更新 `plugins-agent` 文档
5. commit handoff 已明确：记录 `已提交` 或 `未提交`
6. 提交不包含无关变更

## Workflow: 删除兼容冗余

### 目标
稳定处理兼容冗余识别、风险分级、删除范围确认与删除后 gate 复核，避免内部实现长期保留双轨逻辑。

### Lifecycle Profile
- route: `retire_compat`
- profile: `compat_retirement_review`
- handoff: `planner -> executor.config -> reviewer`
- 子状态：
  - `inventory_built`
  - `risk_banded`
  - `deletion_scope_confirmed`
  - `gates_selected`

### Planner
1. 先产出 `compat_inventory`，逐项登记：
   - `canonical_form`
   - `legacy_form`
   - `runtime_surface`
   - `delete_action`
   - `risk_level`
2. 将待删项分为 `low/medium/high`
3. 若存在 `medium/high` 且触及 `public_cli`、`public_python_api`、`plugin_contract`，进入 `awaiting_user_input`
4. 生成 `plan_brief`，明确：
   - 删除范围
   - 默认 executor role（`executor.config` / `executor.plugin` / `executor.docs`）
   - 必跑 gate
   - 高风险项是否已拆分到其他 route

### Executor
1. 仅删除 `compat_inventory` 中 `delete_action=remove` 且已获确认的项
2. 将实现收敛到规范形态，不保留新的内部双轨逻辑
3. 同步更新迁移说明与相关文档
4. 执行命中的 gate，并产出 `execution_report`

### Reviewer
1. 核对 `compat_inventory` 是否完整、分类是否正确
2. 核对中高风险项是否按策略确认或拆分
3. 核对 gate 结果、文档同步与残余兼容债
4. 核对 commit handoff 是否明确
5. 产出 `review_report`
6. 决策：
   - 全部通过：`completed`
   - 可修复问题：`rework_required`
   - 缺少确认或环境阻断：`blocked`

### 风险分级矩阵

| Level | 典型对象 | 默认动作 | 最低 gate | 审查动作 |
| --- | --- | --- | --- | --- |
| `low` | 内部 fallback、重复 docs redirect、未公开 compat helper | 可直接纳入删除范围 | `doc_sync` + `doc_anchors` | 检查是否真正收敛到规范形态 |
| `medium` | 配置别名、deprecated option、import alias | 需迁移说明；必要时先确认 | `doc_sync`，必要时 `schema_compat_check` | 检查迁移说明和确认记录 |
| `high` | `provides` / `depends_on` / `output_dtype` / 正式字段 / 公开 CLI 参数 | 不直接按普通冗余删除；转 `modify_plugin` 或迁移任务 | `assess_change_impact` + `schema_compat_check` | 未拆分则打回 |

### 固定 gate 与命令
```bash
scripts/check_doc_sync.sh
python scripts/check_doc_anchors.py --check-sync --base HEAD
python scripts/assess_change_impact.py --base HEAD
python scripts/schema_compat_check.py --base HEAD --run-smoke
waveform-docs generate plugins-agent -o docs/plugins/reference/agent/
```

### Gate 触发策略
1. 总是执行：
   - `doc_sync`
   - `doc_anchors`
2. 触及 `waveform_analysis/` 且删除项影响插件契约、依赖或缓存 lineage 时：
   - `assess_change_impact`
3. 触及字段、dtype、配置语义、插件契约时：
   - `schema_compat_check`
4. 触及 agent 插件参考时：
   - `waveform-docs generate plugins-agent -o docs/plugins/reference/agent/`

### 必须打回的情况
1. 缺少 `compat_inventory`
2. 删除项未记录 `canonical_form` / `legacy_form`
3. 中高风险项被按低风险处理
4. 删除用户可见兼容入口但文档未同步
5. 需要的 `assess_change_impact` 或 `schema_compat_check` 未执行
6. 提交状态未说明，或存在未提交改动但未给出原因

### Definition of Done
1. `compat_inventory`、`plan_brief`、`execution_report`、`review_report` 齐全
2. 删除范围与风险等级一致
3. 命中的 gate 全部通过
4. 高风险项已拆分到正确 route，而不是混入普通冗余清理
5. commit handoff 已明确：记录 `已提交` 或 `未提交`
6. 内部实现只保留规范形态

## Workflow: 排查缓存问题

### Lifecycle Profile
- route: `debug_cache`
- profile: `diagnostic_review`
- handoff: `planner -> executor.config -> reviewer`
- 子状态：
  - `preview_ready`
  - `lineage_checked`

### 标准步骤
1. `Planner` 确认 `run_id`、target 与重现路径
2. `Executor` 运行：
   - `ctx.preview_execution(run_id, target)`
   - `waveform-cache diagnose --run <run_id> --dry-run`
3. `Reviewer` 审查根因是否明确、是否存在后续修复建议

### 完成标准
1. 已明确 cache blocker 与可能根因
2. 已记录下一步修复动作或需要补充的信息

## Workflow: 文档同步检查
```bash
python scripts/render_agent_docs.py --check
scripts/check_doc_sync.sh
python scripts/check_doc_anchors.py --check-sync --base HEAD
```

## Workflow: PR 前固定质量闸门（3 类，4 条命令）

### 目标
将 `generate_docs`、`assess_change_impact`、`schema_compat_check` 固定为可重复、可审计的 PR 前闸门。

### 触发策略（按改动类型）
1. 若改动触及插件实现或契约相关代码（如 `waveform_analysis/`），执行全部三类闸门
2. 若仅文档改动（`docs/**`、`AGENTS.md`、`CLAUDE.md`），按文档同步流程执行

### 固定闸门与命令
```bash
# generate_docs
waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/
waveform-docs generate plugins-agent -o docs/plugins/reference/agent/
python scripts/render_agent_docs.py --check

# assess_change_impact
python scripts/assess_change_impact.py --base HEAD

# schema_compat_check
python scripts/schema_compat_check.py --base HEAD --run-smoke
```

### Lifecycle 绑定
- `Planner` 决定哪些 gate 必须进入 `plan_brief`
- `Executor` 负责运行命令并产出 `execution_report`
- `Reviewer` 决定 gate 结果映射为 `completed` / `rework_required` / `blocked` / `failed`

### Definition of Done
1. 命中触发条件时，三类闸门对应的四条命令全部执行并通过
2. PR 描述包含执行命令与 PASS/FAIL 摘要
3. `docs/agents/index.yaml` 对应 route 命令与本节一致

## Workflow: assess_change_impact

### 目标
在改代码前做影响面扫描：定位 `provides/depends_on/output_dtype/version` 变化、下游受影响插件、缓存 lineage 风险。

### 命令
```bash
python scripts/assess_change_impact.py --base HEAD
```

### 审查重点
1. 已识别变更插件类和关键契约字段变化
2. 已列出下游受影响插件列表
3. 若存在 `output_dtype/depends_on` 变化且 `version` 未变，必须打回

## Workflow: schema_compat_check

### 目标
专门处理字段/dtype 变更，输出迁移清单，并固定执行关键链路冒烟：
`raw_files -> st_waveforms -> hit -> df -> events`

### 命令
```bash
python scripts/schema_compat_check.py --base HEAD --run-smoke
```

### 审查重点
1. dtype 字段增删改、类型变化已输出
2. 已生成迁移清单
3. 冒烟链路可跑通，且关键字段契约完整

## Workflow: performance_regression_check

### 目标
对热点插件做“改前/改后”耗时与内存对比，避免性能静默退化。

### 命令
```bash
python scripts/performance_regression_check.py --base HEAD
```

### 口径
1. 固定小样本数据，保证可重复
2. 默认目标插件：`st_waveforms, hit, df, events`
3. 默认阈值：平均耗时 `+10%`、平均峰值内存 `+15%` 以上判定回归

## Workflow: release_artifact_sync

### 目标
发布前统一校验：版本号、`CHANGELOG`、agent/auto 文档、doc anchors、关键测试结果是否齐全。

### 命令
```bash
python scripts/release_artifact_sync.py --base HEAD
```

### 审查重点
1. 版本与 `CHANGELOG` 状态一致
2. `plugins-auto` 与 `plugins-agent` 生成结果与仓库文档一致
3. `doc_sync` 与 `doc_anchors` 检查通过
4. 关键链路测试与性能检查状态明确

## Workflow: release_check

`release_check` 是 `release_artifact_sync` 的兼容别名。

### 使用约定
1. 优先使用 `release_artifact_sync` 作为主 route 名称
2. 若外部系统仍调用 `release_check`，其生命周期、命令、gate 与完成标准均按 `release_artifact_sync` 解释
3. 不单独维护 `release_check` 专用 protocol 模板

## 当前落地决策
1. 生命周期真源在 `docs/agents/lifecycle.md`
2. 机器协议真源在 `docs/agents/index.yaml`
3. 协议模板放在 `docs/agents/protocol/`
4. `Planner -> Executor -> Reviewer` 是默认唯一协作拓扑
