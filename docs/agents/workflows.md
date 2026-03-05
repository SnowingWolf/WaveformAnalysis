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
