# plan_brief

- `task_id`: `context_api_convergence_phase1`
- `route`: `retire_compat`
- `lifecycle_profile`: `compat_retirement_review`
- `risk_level`: `medium`
- `scope_in`:
  - `waveform_analysis/core/context.py`: 添加 deprecation warnings
  - `docs/features/context/CONFIGURATION.md`: 更新术语说明
  - `docs/features/context/DATA_ACCESS.md`: 更新示例代码
- `scope_out`:
  - 第一批 deprecated APIs 添加清晰的迁移指导
  - 文档更新完成，术语统一为 `run_id`
  - 所有相关测试通过
- `required_gates`:
  - `compat_inventory_ready`
  - `deletion_scope_confirmed`
  - `doc_sync`
  - `doc_anchors`
  - `schema_compat_check` (配置参数语义变更)
- `executor_role`: `executor.config`
- `blocking_assumptions`:
  - 用户代码中有使用 `run_name` 参数的情况，需要 warnings 引导迁移
  - 配置语义变更不会影响现有缓存的有效性
  - 文档更新不会导致现有用户脚本的破坏性变更

## retire_compat Notes

- `compat_inventory_required`: `true`
- `compat_inventory_path`: `docs/agents/protocol/artifacts/context_api_compat_inventory.md`
- `executor_role_override`: `executor.config`
- `deletion_policy`: `balanced`
- `must_run_commands`:
  - `scripts/check_doc_sync.sh`
  - `python scripts/check_doc_anchors.py --check-sync --base HEAD`
  - `python scripts/schema_compat_check.py --base HEAD --run-smoke`
- `public_surface_confirmation_required`: `false` (仅术语变更，无破坏性 API 变更)
- `high_risk_items_redirected`: `false`

## Implementation Plan

### Phase 1: Add Deprecation Warnings

1. **show_config() method**:
   - 将 `run_name` 参数标记为 deprecated
   - 添加 warning 引导用户使用 `run_id`
   - 更新方法文档说明术语变更

2. **Configuration documentation**:
   - 更新 CONFIGURATION.md 说明 `run_id` 语义
   - 添加迁移指南说明 `run_name` -> `run_id`
   - 更新所有示例使用 `run_id`

### Phase 2: Documentation Updates

1. **DATA_ACCESS.md**:
   - 更新所有示例代码使用 `run_id`
   - 添加术语说明脚注

2. **Migration Guide**:
   - 创建或更新迁移说明文档
   - 提供代码搜索替换建议

### Phase 3: Validation

1. **Run tests**: 确保所有现有测试通过
2. **Schema compatibility check**: 验证配置语义变更不会破坏缓存
3. **Documentation sync**: 验证文档锚点和引用一致性

## Migration Notes

### `run_name` -> `run_id`

**Old usage**:
```python
ctx.show_config(run_name='my_run')
```

**New usage**:
```python
# Use run_id consistently with get_data()
run_id = 'my_run'
ctx.get_data(run_id, 'peaks')
ctx.show_config(run_id=run_id)  # Will show deprecation warning
```

**Reason**: 统一术语，`run_id` 是系统中的唯一标识符，`run_name` 是容易引起混淆的旧术语。
