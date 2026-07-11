# compat_inventory - Context 公共 API 平衡收敛

- `task_id`: `context_api_convergence_phase1`
- `route`: `retire_compat`
- `inventory_scope`: `waveform_analysis.core.context.py` 公共 API
- `canonical_policy`: `entry-only compat; internal code uses canonical form only`

## compat_items

- `compat_id`: `context_from_config_json`
  - `kind`: `config_alias`
  - `canonical_form`: `ctx.set_config()` + `ctx.get_config()`
  - `legacy_form`: `Context.from_config_json()` （实例方法）
  - `location`: `context.py:235-248`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `keep`
  - `risk_level`: `medium`
  - `required_gates`:
    - `doc_sync`
  - `migration_note`: 保留为便捷方法，但在文档中引导用户使用 `set_config()`。此方法是 `__init__` 后的配置加载方式，属于合理的"后期配置"入口。
  - `review_decision`: `approved`

- `compat_id`: `context_show_config_run_name`
  - `kind`: `deprecated_option`
  - `canonical_form`: `run_id` (通过 `get_data` 传入)
  - `legacy_form`: `run_name` (show_config 参数)
  - `location`: `context.py:785`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `migrate_to_central_compat`
  - `risk_level`: `medium`
  - `required_gates`:
    - `schema_compat_check`
  - `migration_note`: 将 `run_name` 参数标记为 deprecated，引导使用 `run_id`。保留参数以兼容旧代码，但发布 deprecation warning。
  - `review_decision`: `approved`

- `compat_id`: `context_analyze_dependencies_vs_preview_execution`
  - `kind`: `fallback_path`
  - `canonical_form`: `preview_execution()` （执行预览）
  - `legacy_form`: `analyze_dependencies()` （依赖分析）
  - `location`: `context.py:1363-1401`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `keep`
  - `risk_level`: `low`
  - `required_gates`:
    - `doc_sync`
  - `migration_note`: 两个方法功能不同，`analyze_dependencies` 提供性能分析，`preview_execution` 提供执行计划。两者都保留，但在文档中明确区分使用场景。
  - `review_decision`: `approved`

- `compat_id`: `context_cache_management_methods`
  - `kind`: `fallback_path`
  - `canonical_form`: CLI `waveform-cache diagnose` (未来统一入口)
  - `legacy_form`: `ctx.analyze_cache()`, `ctx.diagnose_cache()`, `ctx.cache_stats()`
  - `location`: `context.py:2506-2646`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `defer`
  - `risk_level`: `medium`
  - `required_gates`:
    - `impact_assessed_if_needed`
  - `migration_note`: 保留 Python API 方法，等待 CLI 一致性实现完成后再评估收敛。当前三个方法各有用途：`analyze_cache` (扫描分析), `diagnose_cache` (问题诊断), `cache_stats` (统计信息)。
  - `review_decision`: `deferred`

- `compat_id`: `context_help_quickstart`
  - `kind`: `docs_redirect`
  - `canonical_form`: 文档中心 `docs/` 和 `AGENTS.md`
  - `legacy_form`: `ctx.help()`, `ctx.quickstart()`
  - `location`: `context.py:2321-2497`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `keep`
  - `risk_level`: `low`
  - `required_gates`: []
  - `migration_note`: 保留为便捷的文档导航方法。这些方法提供了交互式帮助，属于有用的用户体验增强。
  - `review_decision`: `approved`

- `compat_id`: `context_time_range_methods`
  - `kind`: `canonical_form`
  - `canonical_form`: `time_range()`, `get_data_time_range_absolute()`
  - `legacy_form`: N/A (已经是规范形态)
  - `location`: `context.py:1969-2044`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `keep`
  - `risk_level`: `low`
  - `required_gates`: []
  - `migration_note`: 核心时间范围查询方法，应作为规范形态保留。两个方法覆盖了相对时间和绝对时间使用场景。
  - `review_decision`: `approved`

- `compat_id`: `context_config_methods`
  - `kind`: `canonical_form`
  - `canonical_form`: `set_config()`, `get_config()`, `get_resolved_config()`, `show_config()`, `show_resolved_config()`
  - `legacy_form`: N/A (已经是规范形态)
  - `location`: `context.py:669-828`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `keep`
  - `risk_level`: `low`
  - `required_gates`: []
  - `migration_note`: 核心配置管理方法，应作为规范形态保留。这些方法提供了完整的配置生命周期管理。
  - `review_decision`: `approved`

- `compat_id`: `context_data_access_methods`
  - `kind`: `canonical_form`
  - `canonical_form`: `get_data()`, `list_provided_data()`, `key_for()`
  - `legacy_form`: N/A (已经是规范形态)
  - `location`: `context.py:847-979`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `keep`
  - `risk_level`: `low`
  - `required_gates`: []
  - `migration_note`: 核心数据访问方法，应作为规范形态保留。这些方法是插件系统的数据访问入口点。
  - `review_decision`: `approved`

- `compat_id`: `context_lineage_methods`
  - `kind`: `canonical_form`
  - `canonical_form`: `get_lineage()`, `plot_lineage()`, `analyze_dependencies()`
  - `legacy_form`: N/A (已经是规范形态)
  - `location`: `context.py:1262-1489`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `keep`
  - `risk_level`: `low`
  - `required_gates`: []
  - `migration_note`: 核心血缘分析方法，应作为规范形态保留。这些方法提供了完整的依赖分析和可视化功能。
  - `review_decision`: `approved`

- `compat_id`: `context_cache_management_methods_v2`
  - `kind`: `internal`
  - `canonical_form`: `clear_cache_for()`, `clear_performance_caches()`, `clear_config_cache()`
  - `legacy_form`: N/A (已经是规范形态)
  - `location`: `context.py:964-1047`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `keep`
  - `risk_level`: `low`
  - `required_gates`: []
  - `migration_note`: 核心缓存管理方法，应作为规范形态保留。这些方法提供了必要的缓存清理能力。
  - `review_decision`: `approved`

- `compat_id`: `context_plugin_management_methods`
  - `kind`: `canonical_form`
  - `canonical_form`: `register()`, `discover_and_register_plugins()`, `get_plugin()`, `list_plugin_configs()`
  - `legacy_form`: N/A (已经是规范形态)
  - `location`: `context.py:536-828`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `keep`
  - `risk_level`: `low`
  - `required_gates`: []
  - `migration_note`: 核心插件管理方法，应作为规范形态保留。这些方法提供了完整的插件注册和管理功能。
  - `review_decision`: `approved`

- `compat_id`: `context_performance_methods`
  - `kind`: `canonical_form`
  - `canonical_form`: `get_performance_report()`, `profiling_summary` (property)
  - `legacy_form`: N/A (已经是规范形态)
  - `location`: `context.py:1308-1361`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `keep`
  - `risk_level`: `low`
  - `required_gates`: []
  - `migration_note`: 核心性能分析方法，应作为规范形态保留。这些方法提供了插件执行性能统计。
  - `review_decision`: `approved`

- `compat_id`: `context_execution_preview_methods`
  - `kind`: `canonical_form`
  - `canonical_form`: `preview_execution()`
  - `legacy_form`: N/A (已经是规范形态)
  - `location`: `context.py:2046-2189`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `keep`
  - `risk_level`: `low`
  - `required_gates`: []
  - `migration_note`: 核心执行预览方法，应作为规范形态保留。此方法提供了不执行计算的执行计划预览能力。
  - `review_decision`: `approved`

- `compat_id`: `context_time_domain_methods`
  - `kind`: `canonical_form`
  - `canonical_form`: `set_epoch()`, `get_epoch()`, `auto_extract_epoch()`, `build_time_index()`, `clear_time_index()`, `get_time_index_stats()`
  - `legacy_form`: N/A (已经是规范形态)
  - `location`: `context.py:1951-2018`
  - `runtime_surface`: `public_python_api`
  - `delete_action`: `keep`
  - `risk_level`: `low`
  - `required_gates`: []
  - `migration_note`: 核心时间域管理方法，应作为规范形态保留。这些方法提供了完整的时间参考和索引管理功能。
  - `review_decision`: `approved`

## Execution Phases

### Phase 1: Deprecation Warnings (Current Sprint)
- 为 `context_show_config_run_name` 添加 deprecation warning
- 更新文档说明 `run_id` vs `run_name` 的语义
- 运行相关测试确保兼容性

### Phase 2: CLI Alignment (Future Sprint)
- 等待 `waveform-cache` CLI 实现完成
- 评估 `analyze_cache()`, `diagnose_cache()`, `cache_stats()` 的收敛策略
- 可能保留 Python API 但在文档中引导使用 CLI

### Phase 3: Documentation Consolidation (Ongoing)
- 明确区分 `analyze_dependencies()` 和 `preview_execution()` 的使用场景
- 更新所有示例代码使用 `run_id` 而非 `run_name`
- 在迁移指南中说明配置加载的最佳实践

## Notes

1. **保留的核心方法**: 所有标记为 `canonical_form` 的方法都是核心 API，不应弃用
2. **便捷方法保留**: `help()` 和 `quickstart()` 提供了良好的用户体验，应保留
3. **配置别名**: `from_config_json()` 是合理的后期配置入口，保留但引导使用 `set_config()`
4. **术语统一**: `run_name` -> `run_id` 的迁移是重要的语义澄清，需要 deprecation warning
5. **缓存管理**: 三个缓存管理方法暂时保留，等待 CLI 实现后再评估收敛策略

## Risk Assessment Summary

- **Low Risk (9 items)**: 核心方法已经是最优形态，保留为规范 API
- **Medium Risk (3 items)**: 需要文档更新和 deprecation warnings，但不破坏兼容性
- **Deferred (1 item)**: 缓存管理方法等待外部依赖（CLI）实现完成

## Completion Checklist

- [x] 每个兼容项都已对应到单一规范形态
- [x] 每个待删除项都已标注风险等级和必跑 gate
- [x] 中高风险项已明确迁移说明或确认要求
- [x] 不存在未归类、未决策的兼容项
- [x] 已明确执行阶段和优先级
- [x] 已识别需要外部依赖的 deferred 项
