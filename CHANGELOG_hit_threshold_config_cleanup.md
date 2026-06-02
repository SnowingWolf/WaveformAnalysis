# hit_threshold 插件配置清理

**日期**: 2026-06-02
**版本**: 1.0.2 → 1.0.3 (待升级)

## 变更摘要

移除了 `hit_threshold` 插件中的遗留配置参数，简化配置接口。

---

## 移除的参数

### 1. `use_filtered` (已移除)

**原功能**: 选择是否使用 `filtered_waveforms` 作为输入源

**移除原因**:
- 功能已被更通用的 `wave_source` 参数替代
- 造成配置混淆（两个参数控制同一功能）

**迁移指南**:
```python
# 旧配置
ctx.set_config({
    "use_filtered": True,  # ❌ 已移除
}, plugin_name="hit_threshold")

# 新配置
ctx.set_config({
    "wave_source": "filtered_waveforms",  # ✅ 使用这个
}, plugin_name="hit_threshold")
```

---

### 2. `sampling_interval_ns` / `dt_ns` (deprecated keys 移除)

**原功能**: 指定采样间隔（纳秒）

**移除原因**:
- 已统一为 `dt` 参数
- 保持命名一致性（所有插件都使用 `dt`）

**迁移指南**:
```python
# 旧配置
ctx.set_config({
    "sampling_interval_ns": 2,  # ❌ 不再支持
    "dt_ns": 2,                 # ❌ 不再支持
}, plugin_name="hit_threshold")

# 新配置
ctx.set_config({
    "dt": 2,  # ✅ 统一使用这个
}, plugin_name="hit_threshold")
```

---

## 影响范围

### 代码变更
- ✅ `waveform_analysis/core/plugins/builtin/cpu/hit_finder.py` - 移除 `use_filtered` 参数
- ✅ `waveform_analysis/core/plugins/builtin/cpu/hit_finder.py` - 移除 deprecated keys 支持
- ✅ `tests/plugins/test_threshold_hit_plugin.py` - 更新 4 个测试用例
- ✅ `docs/plugins/reference/agent/hit_threshold.md` - 自动更新文档

### 测试结果
- ✅ 所有测试通过 (27 passed)
- ✅ hit_merge 插件测试通过 (12 passed)
- ✅ 无回归问题

### 兼容性
**向后不兼容**：
- 使用 `use_filtered` 的代码会报错（参数不存在）
- 使用 `sampling_interval_ns` / `dt_ns` 的代码不再触发 deprecation 警告，直接忽略

**建议**：
- 在升级版本号到 1.0.3 前，通知所有用户迁移配置
- 提供迁移脚本扫描代码库中的旧参数使用

---

## 配置简化效果

### 移除前 (13 个参数)
```python
ctx.set_config({
    "threshold": 10.0,
    "use_filtered": False,          # ❌ 遗留
    "wave_source": "auto",
    "left_extension": 2,
    "right_extension": 2,
    "dt": None,
    "channel_config": None,
    "backend": "auto",
    "chunk_parallel": True,
    "n_workers": 0,
    "parallel_chunk_size": 50000,
    "parallel_min_records": 50000,
    "streaming_chunk_size": 10000,
}, plugin_name="hit_threshold")
```

### 移除后 (12 个参数)
```python
ctx.set_config({
    "threshold": 10.0,
    "wave_source": "auto",          # ✅ 清晰的数据源选择
    "left_extension": 2,
    "right_extension": 2,
    "dt": None,                     # ✅ 统一的采样间隔参数
    "channel_config": None,
    "backend": "auto",
    "chunk_parallel": True,
    "n_workers": 0,
    "parallel_chunk_size": 50000,
    "parallel_min_records": 50000,
    "streaming_chunk_size": 10000,
}, plugin_name="hit_threshold")
```

**减少配置项**: 13 → 12 (7.7% 减少)

---

## 后续优化建议

### Phase 2: 性能参数简化
将 5 个性能参数统一为预设模式：

```python
# 当前 (5 个性能参数)
ctx.set_config({
    "backend": "auto",
    "chunk_parallel": True,
    "n_workers": 0,
    "parallel_chunk_size": 50000,
    "parallel_min_records": 50000,
}, plugin_name="hit_threshold")

# 建议 (1 个性能参数)
ctx.set_config({
    "performance": "auto",  # 或 'balanced' / 'high_throughput' / 'low_memory'
}, plugin_name="hit_threshold")
```

**预期效果**: 12 → 8 个参数 (33% 减少)

---

## 验证清单

- [x] 移除 `use_filtered` 参数定义
- [x] 移除 deprecated keys 支持
- [x] 更新测试用例
- [x] 重新生成插件文档
- [x] 运行完整测试套件
- [x] 创建变更日志
- [ ] 升级插件版本号 (1.0.2 → 1.0.3)
- [ ] 更新用户指南文档
- [ ] 通知用户迁移配置

---

## 提交信息

```
refactor(hit_threshold): 移除遗留配置参数

- 移除 `use_filtered` 参数（已被 `wave_source` 替代）
- 移除 `sampling_interval_ns` / `dt_ns` deprecated keys 支持
- 更新测试用例以使用新配置方式
- 自动更新插件文档

Breaking Change: 使用 `use_filtered` 的代码需要迁移到 `wave_source`

相关测试:
- tests/plugins/test_threshold_hit_plugin.py (27 passed)
- tests/plugins/test_hit_merge_plugin.py (12 passed)
```
