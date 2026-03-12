# Repository Guidelines

## Response Language
- 默认使用中文回复用户，除非用户明确要求其他语言。

## Source Of Truth
- 主入口（唯一真源）：`AGENTS.md`
- 入口导航：`docs/agents/INDEX.md`
- 旧链接兼容：`CLAUDE.md`（最小跳转）
- Agent 深度文档：`docs/agents/`
- Agent 插件参考：`docs/plugins/reference/agent/INDEX.md`
- Auto 插件参考（保留不变）：`docs/plugins/reference/builtin/auto/INDEX.md`

## 30 秒入口（按场景）

### 场景 1: 改插件（新增/修改算法）
1. `docs/agents/plugins.md`
2. `docs/agents/conventions.md`
3. `docs/plugins/reference/agent/INDEX.md`

### 场景 2: 改配置/兼容参数
1. `docs/agents/configuration.md`
2. `docs/features/context/CONFIGURATION.md`

### 场景 3: 排查缓存/执行链问题
1. `docs/agents/workflows.md`
2. `docs/features/context/PREVIEW_EXECUTION.md`
3. `docs/features/context/DATA_ACCESS.md`

### 场景 4: 文档同步与发布前检查
1. `docs/agents/references.md`
2. `scripts/check_doc_sync.sh`
3. `python scripts/check_doc_anchors.py --check-sync --base HEAD`

### 场景 5: 插件契约/性能/发布闸门
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
- 统一命名：类名 `PascalCase`，函数/变量 `snake_case`，常量 `UPPER_SNAKE_CASE`。
- 不提交大体积缓存/依赖目录：`node_modules/`, `.cache/`, `.mypy_cache/`, `htmlcov/`。

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

### Quality Gates
```bash
python scripts/assess_change_impact.py --base HEAD
python scripts/schema_compat_check.py --base HEAD --run-smoke
python scripts/performance_regression_check.py --base HEAD
python scripts/release_artifact_sync.py --base HEAD
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

## PR 前固定闸门（三项）
- 固定命令（保持独立命令，不新增统一总入口）：
  - `waveform-docs generate plugins-auto -o docs/plugins/reference/builtin/auto/`
  - `waveform-docs generate plugins-agent -o docs/plugins/reference/agent/`
  - `python scripts/assess_change_impact.py --base HEAD`
  - `python scripts/schema_compat_check.py --base HEAD --run-smoke`
- 触发策略（按改动类型）：
  - 若触及插件实现或插件契约相关改动（如 `waveform_analysis/`），三项全部执行。
  - 若仅文档改动（`docs/**`、`AGENTS.md`、`CLAUDE.md`），不强制三项全跑，继续执行现有文档同步检查。
- PR 记录要求：
  - 在 PR 描述中附三项命令执行摘要（命令 + PASS/FAIL）。

## Commit & PR
- Commit 前缀：`feat:`, `fix:`, `refactor:`, `docs:`, `chore:`。
- PR 至少包含：变更摘要、测试结果、文档变更说明（若用户可见）。

## Common Pitfalls
- 缺失 `run_id` 导致缓存冲突或数据覆盖。
- 生成器数据重复访问会触发重算。
- chunk 边界必须满足 `endtime <= chunk end`。
- 插件输出字段变更但未升级 `version` 会造成缓存问题。

## Deep Links
- Agent 总导航：`docs/agents/INDEX.md`
- 机器可读索引：`docs/agents/index.yaml`
- 核心架构：`docs/architecture/ARCHITECTURE.md`
- 配置：`docs/features/context/CONFIGURATION.md`
- 数据访问：`docs/features/context/DATA_ACCESS.md`
- 执行预览：`docs/features/context/PREVIEW_EXECUTION.md`
- 流式插件：`docs/features/plugin/STREAMING_PLUGINS_GUIDE.md`
- 执行器管理：`docs/features/advanced/EXECUTOR_MANAGER_GUIDE.md`

## Compatibility Notes
- `CLAUDE.md` 保留用于兼容旧链接。
- 新增或更新入口规则时，仅维护本文件。
