# cache_analysis (CacheAnalysisPlugin)

> Agent-first 插件契约文档。面向自动化执行与改动评估。

## Agent Contract

| Item | Value |
|------|-------|
| Provides | `cache_analysis` |
| Depends On | - |
| Output Kind | `unknown` |
| Version | `0.1.0` |
| Module | `waveform_analysis.core.plugins.builtin.cpu.cache_analysis` |
| Accelerator | `cpu` |

## Inputs

- 无依赖输入（source plugin）

## Outputs

- 无结构化字段信息（`unknown`）

## Config

| Name | Type | Default | Note |
|------|------|---------|------|
| `scan_all_runs` | `bool` | `False` | Scan all runs instead of only the requested run_id. |
| `data_name` | `str` | `None` | Optional data name filter for cache entries. |
| `min_size_bytes` | `int` | `None` | Minimum cache entry size in bytes for filtering. |
| `max_size_bytes` | `int` | `None` | Maximum cache entry size in bytes for filtering. |
| `min_age_days` | `float` | `None` | Minimum cache entry age in days for filtering. |
| `max_age_days` | `float` | `None` | Maximum cache entry age in days for filtering. |
| `compressed_only` | `bool` | `None` | Filter entries by compression state (True/False). |
| `include_entries` | `bool` | `True` | Include per-entry details in the result payload. |
| `max_entries` | `int` | `None` | Limit the number of entries returned (largest by size). |
| `include_metadata` | `bool` | `False` | Include full metadata dict for each cache entry. |
| `include_diagnostics` | `bool` | `False` | Run cache diagnostics and include issue list. |
| `export_format` | `str` | `None` | Export report to output_dir as 'json' or 'csv'. |
| `export_name` | `str` | `cache_analysis` | Base filename for exported report. |
| `export_path` | `str` | `None` | Explicit export path. Overrides export_name/output_dir. |
| `verbose` | `bool` | `False` | Print scan and diagnostic progress. |

## Execution Path

`cache_analysis` 依赖链入口：
`SOURCE -> cache_analysis`

## Failure Modes

- 依赖数据缺失或字段不匹配，导致 compute 阶段报错
- 配置值类型/范围不合法，触发参数校验异常
- 输出 dtype 变更但版本未升级，可能导致缓存命中异常

## Change Playbook

1. 修改 `options`/`output_dtype`/核心算法后同步提升 `version`
2. 保持 `provides` 稳定；若必须变更，更新依赖插件与文档索引
3. 新增/删除输出字段时，同时更新消费方插件和回归测试

## Validation

```bash
# 单插件文档再生成
waveform-docs generate plugins-agent --plugin cache_analysis

# 覆盖率检查
waveform-docs check coverage --strict
```
