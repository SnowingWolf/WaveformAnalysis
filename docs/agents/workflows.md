# Agent Workflows

## Workflow: 修改插件

### 目标
在不破坏现有 pipeline 的前提下，完成插件改动并保证可回归、可追溯、可文档化。

### 速查（最短路径）
1. 判级：`L0/L1/L2/L3`。
2. 最小测试集：正常 + 边界 + 兼容。
3. 需要时更新插件文档：`waveform-docs generate plugins-agent --plugin <provides>`。
4. 执行同步检查：`scripts/check_doc_sync.sh` 与 `check_doc_anchors`。

### Preflight
1. 确认目标插件与文件位置。
2. 确认上游依赖与下游消费方。
3. 判断是否影响 `provides`、`depends_on`、`options`、`output_dtype`、`version`。

### 改动分级矩阵

| Level | 触发条件 | version 策略 | 最低测试要求 | 文档要求 | 提交建议 |
| --- | --- | --- | --- | --- | --- |
| `L0` | 仅注释/文档，不改行为 | 不变 | 文档检查 | 更新对应文档 | `docs` 单提交 |
| `L1` | 算法内部调整，输出契约不变 | 建议升级 patch | 定向测试 + 边界测试 | 更新 workflow/说明（必要时） | `code+tests`，可单提交 |
| `L2` | 配置语义或输出字段变化 | 必须升级（至少 minor） | 定向测试 + 边界测试 + dtype/字段兼容测试 | 更新 `plugins-agent` 页面与 agent 流程文档 | 建议拆分 `code+tests` 与 `docs` |
| `L3` | `provides`/依赖链/pipeline 行为变化 | 必须升级（优先 minor/major） | 增加下游兼容回归 | 同步更新路由与插件参考 | 强制拆分提交 |

### 标准步骤
1. 先判级：根据上表确定 `L0/L1/L2/L3`。
2. 影响面确认：定位 `provides`、`depends_on`、`resolve_depends_on()`、`options`、`output_dtype`。
3. 版本策略落地：按等级调整 `version`。
4. 实现改动：先最小可运行，再做必要重构。
5. 执行最小测试集（见下节）。
6. 文档同步：
   - 插件契约变化时，更新 `docs/plugins/reference/agent/`。
   - 流程变化时，更新 `docs/agents/`。
7. 执行同步检查：
   - `scripts/check_doc_sync.sh`
   - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
8. 提交前核对：commit 仅包含本次改动，不混入无关文件。

### 最小测试集
1. 正常路径：典型输入下结果正确。
2. 边界路径：空输入、最小样本、异常参数。
3. 兼容路径：dtype/字段不回归，下游消费方可运行。

### 常用命令模板
```bash
# 1) 跑定向测试
./scripts/run_tests.sh -v -k <plugin_or_feature_keyword>

# 2) 生成插件 agent 文档
waveform-docs generate plugins-agent --plugin <provides>

# 3) 文档同步检查
scripts/check_doc_sync.sh
python scripts/check_doc_anchors.py --check-sync --base HEAD
```

### Definition of Done
1. 版本策略符合改动等级。
2. 最小测试集通过。
3. 需要时已更新 `plugins-agent` 文档。
4. `doc_sync` 与 `doc_anchors` 检查通过。
5. 提交不包含无关变更。

### 路由同步要求
`docs/agents/index.yaml` 的 `task_routes.modify_plugin` 必须与本节命令和入口保持一致。

## Workflow: 排查缓存问题
1. `ctx.preview_execution(run_id, target)`
2. 检查 lineage 输入（版本/配置/dtype）
3. 使用缓存诊断命令定位失效原因

## Workflow: 文档同步检查
```bash
scripts/check_doc_sync.sh
python scripts/check_doc_anchors.py --check-sync --base HEAD
```

## Workflow: 三项固定质量闸门（PR 前）

### 目标
将 `generate_docs`、`assess_change_impact`、`schema_compat_check` 固定为可重复、可审计的 PR 前闸门。

### 固定命令（独立入口）
```bash
waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/
waveform-docs generate plugins-agent -o docs/plugins/reference/agent/
python scripts/assess_change_impact.py --base HEAD
python scripts/schema_compat_check.py --base HEAD --run-smoke
```

### 触发策略（按改动类型）
1. 若改动触及插件实现或契约相关代码（如 `waveform_analysis/`），执行全部三项。
2. 若仅文档改动（`docs/**`、`AGENTS.md`、`CLAUDE.md`），不强制执行全部三项，按现有文档同步流程执行。

### 执行顺序
1. `generate_docs`
2. `assess_change_impact`
3. `schema_compat_check`

### Definition of Done
1. 命中触发条件时，三项命令全部执行并通过。
2. PR 描述包含执行命令与 PASS/FAIL 摘要。
3. `docs/agents/index.yaml` 对应 route 命令与本节一致。

## Workflow: assess_change_impact

### 目标
在改代码前做影响面扫描：定位 `provides/depends_on/output_dtype/version` 变化、下游受影响插件、缓存 lineage 风险。

### 命令
```bash
python scripts/assess_change_impact.py --base HEAD
```

### 通过标准
1. 已识别变更插件类和关键契约字段变化。
2. 已列出下游受影响插件列表。
3. 若存在 `output_dtype/depends_on` 变化，且 `version` 未变，视为高风险，必须先处理再继续。

## Workflow: schema_compat_check

### 目标
专门处理字段/dtype 变更，输出迁移清单，并固定执行关键链路冒烟：
`raw_files -> st_waveforms -> hit -> df -> events`。

### 命令
```bash
python scripts/schema_compat_check.py --base HEAD --run-smoke
```

### 通过标准
1. dtype 字段增删改、类型变化已输出。
2. 已生成迁移清单（字段重命名候选、类型变更处置）。
3. 冒烟链路可跑通，且 `st_waveforms/events` 关键字段契约完整。

## Workflow: performance_regression_check

### 目标
对热点插件做“改前/改后”耗时与内存对比，避免性能静默退化。

### 命令
```bash
python scripts/performance_regression_check.py --base HEAD
```

### 口径
1. 固定小样本数据，保证可重复。
2. 默认目标插件：`st_waveforms, hit, df, events`。
3. 默认阈值：平均耗时 `+10%`、平均峰值内存 `+15%` 以上判定回归。

## Workflow: release_artifact_sync

### 目标
发布前统一校验：版本号、`CHANGELOG`、agent/auto 文档、doc anchors、关键测试结果是否齐全。

### 命令
```bash
python scripts/release_artifact_sync.py --base HEAD
```

### 通过标准
1. 版本与 `CHANGELOG` 状态一致。
2. `plugins-auto` 与 `plugins-agent` 生成结果与仓库文档一致。
3. `doc_sync` 与 `doc_anchors` 检查通过。
4. 关键链路测试（含固定冒烟）通过。
5. 性能回归检查通过。

## Route -> Skill 评估矩阵（本轮仅评估，不落地）

| Route | 自动化程度 | 是否适合 skill | 结论 |
| --- | --- | --- | --- |
| `modify_plugin` | 高 | 中 | 保持 route；后续可做“插件改动守门”skill |
| `debug_cache` | 中 | 中 | 保持 route；参数分歧较多，先沉淀模板 |
| `generate_docs` | 高 | 高 | 可优先转 skill（文档生成动作稳定） |
| `run_tests` | 高 | 低 | 直接命令足够，skill 价值有限 |
| `release_check` | 高 | 中 | 已被 `release_artifact_sync` 吸收，暂不单独 skill 化 |
| `assess_change_impact` | 高 | 高 | 适合未来转 skill（输入/输出清晰） |
| `schema_compat_check` | 高 | 高 | 适合未来转 skill（迁移清单可模板化） |
| `performance_regression_check` | 中 | 中 | 可转 skill，但需先稳定基线策略 |
| `release_artifact_sync` | 高 | 中 | 暂保留 route，作为统一发布闸门入口 |

### 本轮决策
1. 当前阶段维持 `task_routes + workflows` 为主，不新增 `.agents/skills`。
2. 下一阶段优先评估 skill 候选：`generate_docs`、`assess_change_impact`、`schema_compat_check`。
