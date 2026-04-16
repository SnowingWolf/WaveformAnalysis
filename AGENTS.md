# Repository Guidelines

## Response Language
- 默认使用中文回复用户，除非用户明确要求其他语言。

## Source Of Truth
- 主入口（人类入口 + 硬约束真源）：`AGENTS.md`
- 入口导航：`docs/agents/INDEX.md`
- 生命周期真源：`docs/agents/lifecycle.md`
- 执行流程与完成标准：`docs/agents/workflows.md`
- 机器可读路由：`docs/agents/index.yaml`
- 协议模板：`docs/agents/protocol/README.md`
- 旧链接兼容：`CLAUDE.md`（最小跳转）
- Agent 深度文档：`docs/agents/`
- Agent 插件参考：`docs/plugins/reference/agent/INDEX.md`
- Auto 插件参考（保留不变）：`docs/plugins/reference/builtin/auto/INDEX.md`

## 30 秒入口（按场景）

### 场景 1: 改插件（新增/修改算法）
1. `docs/agents/workflows.md`
2. `docs/agents/lifecycle.md`
3. `docs/agents/plugins.md`
4. `docs/plugins/reference/agent/INDEX.md`

### 场景 2: 改配置/兼容参数
1. `docs/agents/configuration.md`
2. `docs/agents/lifecycle.md`
3. `docs/features/context/CONFIGURATION.md`
4. `docs/agents/protocol/route-profiles/retire_compat.md`

### 场景 3: 删除兼容冗余 / legacy 收敛
1. `docs/agents/workflows.md`
2. `docs/agents/lifecycle.md`
3. `docs/agents/protocol/artifacts/compat_inventory.md`
4. `docs/agents/protocol/route-profiles/retire_compat.md`

### 场景 4: 排查缓存/执行链问题
1. `docs/agents/workflows.md`
2. `docs/agents/lifecycle.md`
3. `docs/features/context/PREVIEW_EXECUTION.md`
4. `docs/features/context/DATA_ACCESS.md`

### 场景 5: 文档同步与发布前检查
1. `docs/agents/references.md`
2. `docs/agents/protocol/README.md`
3. `scripts/check_doc_sync.sh`
4. `python scripts/check_doc_anchors.py --check-sync --base HEAD`

### 场景 6: PR 固定质量闸门
1. `docs/agents/workflows.md`
2. `docs/agents/lifecycle.md`
3. `python scripts/assess_change_impact.py --base HEAD`
4. `python scripts/schema_compat_check.py --base HEAD --run-smoke`

### 场景 7: 扩展检查 / 发布前检查
1. `python scripts/assess_change_impact.py --base HEAD`
2. `python scripts/schema_compat_check.py --base HEAD --run-smoke`
3. `python scripts/performance_regression_check.py --base HEAD`
4. `python scripts/release_artifact_sync.py --base HEAD`

## Hard Rules
- Python 3.10+ 基线：允许使用 `str | Path` 等 3.10+ 语法。
- Context 无状态：所有数据访问都要显式 `run_id`。
- 插件职责单一：每个插件做一件事。
- 插件变更要升级 `version`：行为、输出 dtype、配置语义变更都要升级。
- 统一术语：`run_name`（不再使用 legacy `char`）。
- 通道唯一键统一为 `(board, channel)`；文档/配置中推荐写成 `"board:channel"`，禁止继续使用 boardless key。
- `channel_metadata` 只表达硬件事实或兼容信息，不参与插件行为决策。
- 统一命名：类名 `PascalCase`，函数/变量 `snake_case`，常量 `UPPER_SNAKE_CASE`。
- 不提交大体积缓存/依赖目录：`node_modules/`, `.cache/`, `.mypy_cache/`, `htmlcov/`。
- 在最终回复前必须检查提交状态：至少执行 `git status --short` 与 `git diff --stat`。
- 若本轮修改了仓库文件，最终回复必须显式写明其一：`已提交：<commit hash>` 或 `未提交：<原因>`。
- 用户未明确要求时，不默认自动提交；但不能省略提交状态说明。

## Agent Collaboration Model
- 默认协作拓扑固定为 `Planner -> Executor -> Reviewer`。
- 主状态固定为 `created -> planning -> ready_for_execution -> executing -> reviewing -> completed`。
- `awaiting_user_input`、`awaiting_approval`、`rework_required`、`blocked`、`failed`、`cancelled` 为正式状态，不要用普通进度消息替代。
- `Reviewer` 未放行前，不得进入 `completed`，文档-only 任务也一样。
- 默认返工路径为 `reviewing -> rework_required -> executing`；仅当 `scope_changed=true` 时允许回到 `planning`。

## Standard Artifacts
- `plan_brief`：`planning -> ready_for_execution` 前必须存在。
- `compat_inventory`：`retire_compat` 在 `planning` 阶段先于 `plan_brief` 完成，用于锁定删除范围。
- `execution_report`：`executing -> reviewing` 前必须存在。
- `review_report`：`reviewing -> completed` 前必须存在。
- 交接模板统一在 `docs/agents/protocol/artifacts/`，route 模板统一在 `docs/agents/protocol/route-profiles/`。

## Supported Routes
<!-- BEGIN GENERATED: supported_routes -->
- `modify_plugin`：插件与契约改动；主入口：`docs/agents/workflows.md`；profile: `docs/agents/protocol/route-profiles/modify_plugin.md`
- `retire_compat`：兼容冗余识别、分级与删除；主入口：`docs/agents/workflows.md`；profile: `docs/agents/protocol/route-profiles/retire_compat.md`
- `debug_cache`：缓存、lineage 与执行链排障；主入口：`docs/agents/workflows.md`；profile: `docs/agents/protocol/route-profiles/debug_cache.md`
- `generate_docs`：文档生成、引用同步与锚点检查；主入口：`docs/agents/references.md`；profile: `docs/agents/protocol/route-profiles/generate_docs.md`
- `run_tests`：定向或全量测试执行；主入口：`AGENTS.md`；profile: `docs/agents/protocol/route-profiles/run_tests.md`
- `assess_change_impact`：改动影响面扫描与 version 风险检查；主入口：`docs/agents/workflows.md`；profile: `docs/agents/protocol/route-profiles/assess_change_impact.md`
- `schema_compat_check`：dtype、字段兼容与关键链路冒烟；主入口：`docs/agents/workflows.md`；profile: `docs/agents/protocol/route-profiles/schema_compat_check.md`
- `performance_regression_check`：热点插件性能回归检查；主入口：`docs/agents/workflows.md`；profile: `docs/agents/protocol/route-profiles/performance_regression_check.md`
- `release_artifact_sync`：发布前版本、文档与检查结果统一校验；主入口：`docs/agents/workflows.md`；profile: `docs/agents/protocol/route-profiles/release_artifact_sync.md`
<!-- END GENERATED: supported_routes -->

## Route Catalog
<!-- BEGIN GENERATED: route_catalog -->
- `modify_plugin`：`docs/agents/workflows.md` -> `docs/agents/protocol/route-profiles/modify_plugin.md`
- `retire_compat`：`docs/agents/workflows.md` -> `docs/agents/protocol/route-profiles/retire_compat.md`
- `debug_cache`：`docs/agents/workflows.md` -> `docs/agents/protocol/route-profiles/debug_cache.md`
- `generate_docs`：`docs/agents/references.md` -> `docs/agents/protocol/route-profiles/generate_docs.md`
- `run_tests`：`AGENTS.md` -> `docs/agents/protocol/route-profiles/run_tests.md`
- `assess_change_impact`：`docs/agents/workflows.md` -> `docs/agents/protocol/route-profiles/assess_change_impact.md`
- `schema_compat_check`：`docs/agents/workflows.md` -> `docs/agents/protocol/route-profiles/schema_compat_check.md`
- `performance_regression_check`：`docs/agents/workflows.md` -> `docs/agents/protocol/route-profiles/performance_regression_check.md`
- `release_artifact_sync`：`docs/agents/workflows.md` -> `docs/agents/protocol/route-profiles/release_artifact_sync.md`
<!-- END GENERATED: route_catalog -->

## Minimal Commands

### Install
```bash
./install.sh
pip install -e ".[dev]"
```

### Test
```bash
./scripts/run_tests.sh
make test
pytest -v --cov=waveform_analysis --cov-report=html
```

### Plugin Docs
```bash
waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/
waveform-docs generate plugins-agent -o docs/plugins/reference/agent/
waveform-docs generate plugins-agent --plugin <provides>
```

### Doc Sync
```bash
python scripts/render_agent_docs.py --check
scripts/check_doc_sync.sh
python scripts/check_doc_anchors.py --check-sync --base HEAD
```

### Handoff
```bash
git status --short
git diff --stat
python scripts/check_agent_handoff.py
```

### PR Fixed Gates
```bash
waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/
waveform-docs generate plugins-agent -o docs/plugins/reference/agent/
python scripts/assess_change_impact.py --base HEAD
python scripts/schema_compat_check.py --base HEAD --run-smoke
```

### Extended Checks / Release Gates
```bash
python scripts/performance_regression_check.py --base HEAD
python scripts/release_artifact_sync.py --base HEAD
```

### Cache Diagnostics
```bash
waveform-cache diagnose --run <run_id> --dry-run
```

### CLI
```bash
waveform-process --run-name <run_name> --verbose
waveform-process --scan-daq --daq-root DAQ
waveform-process --show-daq --daq-root DAQ
```

## Architecture Essentials
- 插件系统是 DAG：通过 `provides/depends_on` 自动解析依赖。
- 缓存采用 lineage：插件代码、版本、配置、dtype 变化会触发失效。
- 处理模式支持静态与流式。
- `records` 与 `wave_pool` 是正式插件产物，`wave_pool_filtered` 是 records-backed 的正式滤波波形池。
- 需要 records-backed 波形访问时统一使用 `records_view(ctx, run_id)`。

## Recommended Practices
- 推荐导入路径：`waveform_analysis.core.plugins.builtin.cpu`。

## Plugin Contract Checklist
新增/修改插件时至少确认：
1. `provides` 唯一、语义稳定。
2. `depends_on` 与 `resolve_depends_on()` 一致。
3. `options` 的默认值、类型、help 明确。
4. `version` 在行为变更时升级。
5. `output_dtype`（或 `output_kind`）与实际输出匹配。
6. `docs/plugins/reference/agent/` 已同步对应插件页。

## Configuration Rules
- 配置优先级：显式配置 > adapter 推断 > 插件默认值。
- 推荐全局配置 `daq_adapter`，避免链路内插件不一致。
- 使用 `ctx.get_resolved_config()` / `ctx.show_resolved_config()` 检查来源。

## Testing Rules
- 发现目录：`tests/`，模式见 `pyproject.toml`。
- 优先补充与改动相关的定向测试。
- 配置/输出结构改动至少覆盖：正常路径、空输入/边界输入、dtype/字段兼容性。

## PR 前固定闸门（3 类，4 条命令）
- 固定命令（保持独立命令，不新增统一总入口）：
  - `generate_docs`
  - `waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/`
  - `waveform-docs generate plugins-agent -o docs/plugins/reference/agent/`
  - `assess_change_impact`
  - `python scripts/assess_change_impact.py --base HEAD`
  - `schema_compat_check`
  - `python scripts/schema_compat_check.py --base HEAD --run-smoke`
- 触发策略（按改动类型）：
  - 若触及插件实现或插件契约相关改动（如 `waveform_analysis/`），三类闸门全部执行。
  - 若仅文档改动（`docs/**`、`AGENTS.md`、`CLAUDE.md`），不强制执行三类闸门，继续执行现有文档同步检查。
- 扩展检查（默认不纳入 PR 固定闸门）：
  - `python scripts/performance_regression_check.py --base HEAD`
  - `python scripts/release_artifact_sync.py --base HEAD`
- PR 记录要求：
  - 在 PR 描述中附三类闸门执行摘要（命令 + PASS/FAIL）。

## Commit & PR
- Commit 前缀：`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`。
- 收尾时必须显式交代 commit 状态；若未提交，必须说明原因。
- 可使用 `python scripts/check_agent_handoff.py --allow-uncommitted --reason "<原因>"` 记录“未提交但已说明”的交付状态。
- PR 至少包含：变更摘要、测试结果、文档变更说明（若用户可见）。

## Common Pitfalls
- 缺失 `run_id` 导致缓存冲突或数据覆盖。
- 生成器数据重复访问会触发重算。
- chunk 边界必须满足 `endtime <= chunk end`。
- 插件输出字段变更但未升级 `version` 会造成缓存问题。

## Deep Links
- Agent 总导航：`docs/agents/INDEX.md`
- 生命周期真源：`docs/agents/lifecycle.md`
- 机器可读索引：`docs/agents/index.yaml`
- 协议模板：`docs/agents/protocol/README.md`
- 协议产物模板：`docs/agents/protocol/artifacts/plan_brief.md`
- 兼容清单模板：`docs/agents/protocol/artifacts/compat_inventory.md`
- 路由模板：`docs/agents/protocol/route-profiles/modify_plugin.md`
- 兼容收敛路由：`docs/agents/protocol/route-profiles/retire_compat.md`
- 参考索引：`docs/agents/references.md`
- Skills 适配：`docs/agents/adapters/skills.md`
- MCP 适配：`docs/agents/adapters/mcp.md`
- 核心架构：`docs/architecture/ARCHITECTURE.md`
- 配置：`docs/features/context/CONFIGURATION.md`
- 数据访问：`docs/features/context/DATA_ACCESS.md`
- 执行预览：`docs/features/context/PREVIEW_EXECUTION.md`
- 流式插件：`docs/features/plugin/STREAMING_PLUGINS_GUIDE.md`
- 执行器管理：`docs/features/advanced/EXECUTOR_MANAGER_GUIDE.md`
- CLI: `docs/cli/WAVEFORM_PROCESS.md`
- 文档 CLI: `docs/cli/WAVEFORM_DOCS.md`
- 缓存 CLI: `docs/cli/WAVEFORM_CACHE.md`

## Compatibility Notes
- `CLAUDE.md` 保留用于兼容旧链接。
- 新增或更新入口导航与硬约束时，仅维护本文件。
- 流程、命令集合与 Definition of Done 以 `docs/agents/workflows.md` 为准。
