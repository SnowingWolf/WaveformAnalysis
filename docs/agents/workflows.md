# Agent Workflows

本页定义常见任务的标准 workflow。状态机真源见 `lifecycle.md`，机器可读路由见 `index.yaml`。

## 通用协作模型
- 拓扑固定：`Planner -> Executor -> Reviewer`
- 主状态固定：`created -> planning -> ready_for_execution -> executing -> reviewing -> completed`
- 可选状态：`awaiting_user_input`、`awaiting_approval`、`rework_required`、`blocked`、`failed`、`cancelled`
- 阻断式审查：`Reviewer` 未放行前，不得进入 `completed`

### Role 与 Profile
- role（如 `executor.plugin`）定义状态所有权与交接责任。
- profile（如 `graph_engineer`）定义贯穿任务的专项参与，不新增主状态或绕过 route。
- `planning`：profile 作为 contributor 产出 `profile_plan`，由 `Planner` 合并并负责最终计划。
- `executing`：同一个 `agent_profile` 映射到当前 route 允许的 `executor_role`。
- `reviewing`：profile 是 review subject，由阻断式 `Reviewer` 在 `agent_profile_review` 中覆盖专项必审项。

## Workflow Cost 分级

`workflow_cost` 用来控制一次任务的流程重量。它不替代主状态机，只决定 artifact 填写粒度和 gate 数量。

| workflow_cost | 适用范围 | Artifact 口径 | Gate 口径 |
| --- | --- | --- | --- |
| `light` | 只读解释、定向测试、文档小修、缓存诊断 | 三段式仍保留，但允许压缩填写 | 只跑当前目标必需的最小 gate |
| `standard` | 普通代码、插件内部算法、QA 扫描 | 完整填写通用 artifact | 跑 route 默认 gate 与定向测试 |
| `strict` | 插件契约、dtype/字段、compat 删除、发布前检查 | 完整 artifact，不得压缩 | 固定 gate 必须全部记录 PASS/FAIL |

### 升级规则
1. route 默认成本见 `docs/agents/index.yaml` 的 `workflow_cost`。
2. `Planner` 必须在 `plan_brief.workflow_cost` 写明实际成本；实际成本可以高于 route 默认值。
3. 触及 public surface、缓存 lineage、插件契约、dtype/字段、compat 删除或发布检查时，必须使用 `strict`。
4. 仅文档改动默认使用 `light`；若文档同步的是代码契约变化，继承源 route 成本。

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
- `light` 模式最低字段：
  - `plan_brief`: `task_id`、`route`、`workflow_cost`、`scope_in`、`required_gates`、`executor_role`
  - `execution_report`: `task_id`、`workflow_cost`、`actions_taken`、`commands_run`、`open_risks`
  - `review_report`: `task_id`、`workflow_cost`、`gate_results`、`decision`、`blocking_findings`
- 使用专项 profile 时，三段式 artifact 还必须分别记录 `agent_profile + profile_plan`、`agent_profile`、`agent_profile_review`。

## 通用 Commit Handoff
- `Executor` 在离开 `executing` 前必须检查工作树：`git status --short`、`git diff --stat`
- 若当前任务留下仓库改动，必须二选一：
  - 已完成提交，并在最终回复或交接中记录 `commit hash`
  - 明确记录 `未提交` 原因
- 修改任务默认在验证通过后提交本轮相关改动；提交必须 scoped，不得混入无关 dirty 文件
- 若不能提交（例如验证失败、范围不清、需要用户确认），必须明确记录 `未提交` 原因
- 可执行：
  - `python scripts/check_agent_handoff.py`
  - `python scripts/check_agent_handoff.py --allow-uncommitted --reason "<原因>"`
  - `python scripts/check_agent_handoff.py --final-note "<最终交付文本>"`
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
   - 执行后端选择：`python|numpy|numba_serial|numba_parallel|thread_pool|process_pool`
   - 并发范围、worker 配置名、fallback 与是否需要 benchmark
   - 必跑 gate
   - 返工是否可能回到 `planning`

### Executor
1. 实现改动：先最小可运行，再做必要重构
2. 核对实际实现是否符合 `plan_brief` 的执行后端决策
3. 执行定向测试与文档更新
4. 产出 `execution_report`

### Reviewer
1. 审查 `version` 策略是否符合变更等级
2. 核对 gate 结果、契约一致性与文档同步
3. 审查执行后端风格：
   - 是否存在同一执行路径多层并发
   - 是否将 `numba_parallel` 与线程池/进程池叠加
   - memory-bound 任务使用 `parallel=True` 是否有证据
   - 新 worker 配置是否优先使用 `max_workers` / `numba_threads`
   - fallback 与 benchmark 口径是否明确
4. 核对 commit handoff 是否明确
5. 产出 `review_report`
6. 决策：
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
4. 插件算法改动缺少执行后端决策或 `performance_style_review`
5. 同一执行路径叠加多个并发层且缺少明确证据
6. `review_report` 未记录 gate 结果
7. 提交状态未说明，或存在未提交改动但未给出原因

### Definition of Done
1. `plan_brief`、`execution_report`、`review_report` 齐全
2. 版本策略符合改动等级
3. 插件算法改动已记录并审查执行后端风格
4. 固定 gate 通过
5. 需要时已更新 `plugins-agent` 文档
6. commit handoff 已明确：记录 `已提交` 或 `未提交`
7. 提交不包含无关变更

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
用于 agent 文档、生成区块、引用与锚点一致性检查。仅文档改动默认走本流程；若文档同步的是代码契约变化，继承源 route 的 `workflow_cost` 和 gate。

```bash
python scripts/render_agent_docs.py --check
scripts/check_doc_sync.sh
python scripts/check_doc_anchors.py --check-sync --base HEAD
```

### 触发策略
1. 修改 `AGENTS.md`、`CLAUDE.md`、`docs/agents/**` 时，至少执行本流程。
2. 修改生成区块来源 `docs/agents/index.yaml` 时，必须执行 `python scripts/render_agent_docs.py --check`。
3. 触及插件参考生成结果时，同时执行对应 `waveform-docs generate ...` 命令。

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

# assess_change_impact
python scripts/assess_change_impact.py --base HEAD

# schema_compat_check
python scripts/schema_compat_check.py --base HEAD --run-smoke
```

Agent 文档同步检查（`python scripts/render_agent_docs.py --check`、`scripts/check_doc_sync.sh`、`python scripts/check_doc_anchors.py --check-sync --base HEAD`）属于文档同步流程，不计入本节“四条命令”。若 PR 同时改了 agent 文档，也必须另行记录这些检查结果。

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
4. `schema_compat_check --run-smoke` 与 `python -m pytest tests/` 全测试目录通过
5. 性能检查状态明确

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
