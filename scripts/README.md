# 脚本工具说明

## 导入管理工具

### `check_imports.py` - 导入规范检查

检查代码库中的导入是否符合规范：

```bash
python scripts/check_imports.py
```

检查内容：
- 禁止使用超过两级的相对导入（`...`）
- 检查导入路径是否正确

### `fix_imports.py` - 自动修复导入

自动修复常见的导入路径问题：

```bash
# 检查并显示问题
python scripts/fix_imports.py

# 自动修复
python scripts/fix_imports.py --fix

# 只检查不修复
python scripts/fix_imports.py --check
```

修复内容：
- 相对导入 → 绝对导入

## 使用 ruff 自动修复

```bash
# 安装 ruff
pip install ruff

# 自动修复所有导入问题
ruff check --fix waveform_analysis/

# 只检查导入
ruff check --select I waveform_analysis/
```

## 插件脚手架

### `scaffold_plugin.py` - 生成插件 + 单测 + 文档

```bash
python scripts/scaffold_plugin.py MyPlugin
```

常用参数：

```bash
python scripts/scaffold_plugin.py MyPlugin --provides my_plugin --depends-on st_waveforms
```

## 缓存清理

### `clear_downstream_cache.py` - 清理下游缓存

根据插件依赖关系，清理指定数据的下游缓存（可选是否包含自身）。

```bash
python scripts/clear_downstream_cache.py run_001 st_waveforms --dry-run
python scripts/clear_downstream_cache.py run_001 st_waveforms --verbose
```

## Agent 质量闸门脚本

### `assess_change_impact.py` - 改动影响面扫描

```bash
python scripts/assess_change_impact.py --base HEAD
```

扫描插件契约变更（`provides/depends_on/output_dtype/version`）、下游受影响插件与 lineage 风险。

### `schema_compat_check.py` - 字段/dtype 兼容检查

```bash
python scripts/schema_compat_check.py --base HEAD --run-smoke
```

输出字段迁移清单，并固定执行链路冒烟：
`raw_files -> st_waveforms -> hit -> df -> events`。

### `performance_regression_check.py` - 性能回归对比

```bash
python scripts/performance_regression_check.py --base HEAD
```

对热点插件记录“改前/改后”耗时与峰值内存对比。

### `release_artifact_sync.py` - 发布前统一校验

```bash
python scripts/release_artifact_sync.py --base HEAD
```

统一检查版本号、`CHANGELOG`、agent/auto 文档、doc anchors、关键测试与性能回归结果。

## 工作流程

1. **开发时**：运行 `check_imports.py` 检查导入规范
2. **重构时**：运行 `fix_imports.py --fix` 自动修复
3. **CI/CD**：集成 `check_imports.py` 和 `ruff check` 到 CI 流程

## 相关文档

- [导入风格指南](../docs/IMPORT_STYLE_GUIDE.md)
