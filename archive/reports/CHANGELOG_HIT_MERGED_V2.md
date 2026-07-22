# HIT_MERGED_DTYPE V2 更新日志

## 版本信息
- **版本**: 2.0.0
- **日期**: 2026-06-15
- **类型**: 重大更新（Breaking Change）

## 概述

`HIT_MERGED_DTYPE` 数据结构已从 V1 升级到 V2，添加了绝对时间字段，提供更统一和通用的时间窗口表示。

## 主要改动

### 1. 新增字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `time_start` | `i8` | 绝对开始时间（ps），总是有效 |
| `time_end` | `i8` | 绝对结束时间（ps），总是有效 |
| `is_single_record` | `bool` | 标记所有组件是否属于同一 record |

### 2. 字段语义变更

- **time_start/time_end**: 新增字段，始终包含有效的绝对时间（picosecond 精度），无论是否跨 record
- **sample_start/sample_end**: 语义保持不变，仅在 `is_single_record=True` 时有效，否则为 -1
- **is_single_record**: 新增标记，用于快速判断是否可以使用 sample 坐标快速路径

### 3. 完整数据结构对比

#### V1 (旧版本)
```python
HIT_MERGED_DTYPE = np.dtype([
    ("position", "i8"),
    ("sample_start", "i4"),
    ("sample_end", "i4"),
    ("width", "f4"),
    ("dt", "i4"),
    ("timestamp", "i8"),
    ("board", "i2"),
    ("channel", "i2"),
    ("record_id", "i8"),
    ("component_offset", "i8"),
    ("component_count", "i4"),
])
```

#### V2 (新版本)
```python
HIT_MERGED_DTYPE = np.dtype([
    ("position", "i8"),
    ("time_start", "i8"),          # 新增
    ("time_end", "i8"),            # 新增
    ("sample_start", "i4"),
    ("sample_end", "i4"),
    ("width", "f4"),
    ("dt", "i4"),
    ("timestamp", "i8"),
    ("board", "i2"),
    ("channel", "i2"),
    ("record_id", "i8"),
    ("component_offset", "i8"),
    ("component_count", "i4"),
    ("is_single_record", "?"),     # 新增
])
```

## 优势

### 1. 统一的时间表示
- 不再需要特殊处理跨 record 情况（sample_start/sample_end = -1）
- 所有 `hit_merged` 行都有有效的绝对时间窗口

### 2. 简化下游处理
- `hit_merged_features` 不再需要复杂的 fallback 逻辑
- `event_grouping` 可以直接使用绝对时间进行窗口计算
- `peaklets` 可以根据 `is_single_record` 标记选择最优路径

### 3. 向后兼容
- 保留 `sample_start`/`sample_end` 字段用于性能优化
- 当 `is_single_record=True` 时，快速路径仍然可用
- 下游插件自动兼容新旧字段

## 计算逻辑

### 同 Record 情况
```python
# 所有组件 hit 属于同一个 record
is_single_record = True
time_start = min(所有组件的绝对开始时间)
time_end = max(所有组件的绝对结束时间)
sample_start = min(所有组件的 sample_start)
sample_end = max(所有组件的 sample_end)
```

### 跨 Record 情况
```python
# 组件 hit 来自不同 record
is_single_record = False
time_start = min(所有组件的绝对开始时间)
time_end = max(所有组件的绝对结束时间)
sample_start = -1  # 无法用单一 record 坐标表示
sample_end = -1
```

## 示例

### 示例 1: 跨 Record 合并
```python
# Hit 1: record_id=0, timestamp=100000ps, position=10, sample_start=8, sample_end=12, dt=2ns
# Hit 2: record_id=1, timestamp=108000ps, position=14, sample_start=13, sample_end=16, dt=2ns

# V2 输出:
merged = {
    'position': 10,
    'time_start': 96000,      # min(96000, 106000)
    'time_end': 112000,       # max(104000, 112000)
    'sample_start': -1,       # 跨 record
    'sample_end': -1,         # 跨 record
    'width': -1.0,
    'is_single_record': False,
    ...
}
```

### 示例 2: 同 Record 合并
```python
# Hit 1: record_id=7, timestamp=100000ps, position=10, sample_start=8, sample_end=12, dt=2ns
# Hit 2: record_id=7, timestamp=108000ps, position=14, sample_start=13, sample_end=16, dt=2ns

# V2 输出:
merged = {
    'position': 10,
    'time_start': 96000,      # min(96000, 106000)
    'time_end': 112000,       # max(104000, 112000)
    'sample_start': 8,        # min(8, 13)
    'sample_end': 16,         # max(12, 16)
    'width': 8.0,
    'is_single_record': True,
    ...
}
```

## 影响范围

### 核心文件
1. `waveform_analysis/core/plugins/builtin/cpu/hit_merge.py` - 数据结构和计算逻辑
2. `waveform_analysis/core/plugins/builtin/cpu/hit_merged_features.py` - 已兼容
3. `waveform_analysis/core/plugins/builtin/cpu/peaklets.py` - 已兼容
4. `waveform_analysis/core/plugins/builtin/cpu/event_analysis.py` - 已兼容
5. `waveform_analysis/core/processing/event_grouping.py` - 已兼容

### 测试覆盖
- ✅ `test_hit_merge_plugin.py` (23 个测试通过)
- ✅ `test_hit_merged_features_plugin.py` (8 个测试通过)
- ✅ `test_peaklets_plugin.py` (5 个测试通过)
- ✅ `test_hit_grouped_plugin.py` (8 个测试通过)
- ✅ `test_peaklet_waveforms_plugin.py` (6 个测试通过)
- ✅ `test_peaklet_channels_plugin.py` (4 个测试通过)
- ✅ `test_hit_merge_pretrigger.py` (3 个测试通过)

**总计**: 57 个测试全部通过 ✅

## 迁移指南

### 缓存失效
⚠️ **重要**: 版本号从 1.2.0 升级到 2.0.0 会导致所有 `hit_merged` 缓存失效，需要重新计算。

### 代码迁移
大多数下游代码**无需修改**，因为：
1. 现有的 `sample_start`/`sample_end` 字段仍然存在
2. 下游插件已自动兼容新字段

### 推荐升级方式
如果你的代码直接访问 `hit_merged` 数据：

```python
# 旧代码（仍然有效）
if merged['sample_start'] >= 0:
    # 使用 sample 坐标
    pass

# 新代码（推荐）
if merged['is_single_record']:
    # 使用 sample 坐标快速路径
    start = merged['sample_start']
    end = merged['sample_end']
else:
    # 使用绝对时间
    time_start = merged['time_start']
    time_end = merged['time_end']
```

## 性能影响

- **快速路径**: 性能保持不变（`is_single_record=True` 时）
- **跨 record**: 性能略微提升（不再需要多次 fallback 调用）
- **内存**: 每行增加 17 字节（2个 int64 + 1个 bool）

## 验证

所有相关测试已更新并通过：
```bash
pytest tests/plugins/test_hit_merge_plugin.py \
       tests/plugins/test_hit_merged_features_plugin.py \
       tests/plugins/test_peaklets_plugin.py \
       tests/plugins/test_hit_grouped_plugin.py \
       tests/plugins/test_peaklet_waveforms_plugin.py \
       tests/plugins/test_peaklet_channels_plugin.py \
       tests/plugins/test_hit_merge_pretrigger.py
```

结果: **57 passed** ✅

## 贡献者
- 设计: wxy, Claude (Anthropic)
- 实现: Claude Code
- 测试: 自动化测试套件

## 相关文档
- 实施计划: `/home/wxy/.claude/plans/sample-start-cuddly-matsumoto.md`
- Agent 文档: 见 `HitMergePlugin.agent_doc`
