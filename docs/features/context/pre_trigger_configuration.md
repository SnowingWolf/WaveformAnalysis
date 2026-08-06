# Pre-trigger 配置支持

## 概述

许多 DAQ 系统（如 CAEN V1725/VX2730）在数据采集时会记录触发点（trigger point）之前的一段波形，这被称为 pre-trigger。在这些系统中，`record.timestamp` 字段对应的是**触发点时间**，而不是波形 sample 0 的时间。

为了正确计算跨 record 的 hit 绝对时间（用于 hit 合并、时间对齐等），需要在配置中指定 `pre_trigger_ns` 参数。

## 配置方法

在 Context 初始化或配置文件中添加 `pre_trigger_ns` 参数：

```python
from waveform_analysis.core.context import Context

ctx = Context()
ctx.config['pre_trigger_ns'] = 200  # 200 纳秒的 pre-trigger
```

或在配置字典中：

```python
config = {
    'pre_trigger_ns': 200,  # 单位：纳秒 (ns)
    'merge_gap_ns': 10.0,
    'max_total_width_ns': 10000.0,
}
```

## 时间计算原理

### 没有 pre_trigger 配置时（默认）

假设：
- `record.timestamp` 对应 sample 0 的时间
- Hit 在 position=100 处，dt=2 ns
- 绝对时间 = `timestamp + position * dt`

### 配置 pre_trigger 后

假设：
- `record.timestamp` 对应触发点时间
- `pre_trigger_ns = 200` (100 个采样点)
- Sample 0 的实际时间 = `timestamp - pre_trigger_ns * 1000` (转为 ps)
- Hit 在 position=100 处
- 绝对时间 = `(timestamp - pre_trigger_ps) + position * dt_ps`

## 示例

### 跨 record hit 合并

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.hit import HitMergePlugin, ThresholdHitPlugin

# 创建 Context 并配置
ctx = Context()
ctx.config['pre_trigger_ns'] = 200  # DAQ 系统的 pre-trigger 设置
ctx.config['merge_gap_ns'] = 10.0   # 10 ns 合并间隔
ctx.config['max_total_width_ns'] = 10000.0

# 注册插件
ctx.register(ThresholdHitPlugin(), HitMergePlugin())

# 处理数据
ctx.make('run_001', 'hit_merged')
merged_hits = ctx.get_data('run_001', 'hit_merged')
```

### Record 1 和 Record 2 的 hit 合并示例

假设：
- dt = 2 ns
- pre_trigger = 100 samples = 200 ns

**Record 1:**
- `timestamp = 1000000` ps（触发点时间）
- Sample 0 实际时间 = 1000000 - 200×1000 = 800000 ps
- Hit at position=100，绝对时间 = 800000 + 100×2000 = 1000000 ps

**Record 2:**
- `timestamp = 1001000` ps（触发点时间）
- Sample 0 实际时间 = 1001000 - 200×1000 = 801000 ps
- Hit at position=100，绝对时间 = 801000 + 100×2000 = 1001000 ps

**时间间隔：**
- 1001000 - 1000000 = 1000 ps = 1 ns
- 小于 merge_gap_ns = 10 ns，**应该合并** ✓

## 向后兼容性

- **默认值：** `pre_trigger_ns = 0`
- 不设置或设置为 0 时，保持原有行为（假设 timestamp 对应 sample 0）
- 现有代码和数据无需修改即可正常运行

## 影响范围

配置 `pre_trigger_ns` 会影响以下插件的时间计算：

### 已支持（当前实现）
- ✅ `hit_merged` - hit 合并插件
- ✅ `hit_merge_clusters` - hit 聚类插件
- ✅ `hit_merged_components` - hit 组件插件

### 计划支持（后续实现）
- ⏳ `hit_threshold` - hit 查找插件
- ⏳ `hit_merged_features` - hit 特征提取插件
- ⏳ `peaklets` - peaklet 插件
- ⏳ `peak_finding` - peak 查找插件

## 获取 pre_trigger 值

如果需要从代码中获取当前的 pre_trigger 配置：

```python
from waveform_analysis.core.processing.time_utils import get_pre_trigger_offset_ps

# 返回 pre_trigger 的皮秒值
pre_trigger_ps = get_pre_trigger_offset_ps(context)

# 转换为纳秒
pre_trigger_ns = pre_trigger_ps / 1000
```

## 调试与验证

### 检查时间计算是否正确

```python
# 验证跨 record 合并的 hit 数量
merged = ctx.get_data('run_001', 'hit_merged')
print(f"Merged hits: {len(merged)}")
print(f"Component counts: {merged['component_count']}")

# 检查是否有跨 record 的合并（component_count > 1 且 width = -1）
cross_record = merged[(merged['component_count'] > 1) & (merged['width'] < 0)]
print(f"Cross-record merges: {len(cross_record)}")
```

### 测试不同 pre_trigger 值的影响

```python
for pre_trigger in [0, 100, 200, 500]:
    ctx = Context()
    ctx.config['pre_trigger_ns'] = pre_trigger
    # ... 运行分析
    merged = ctx.get_data('run_001', 'hit_merged')
    print(f"pre_trigger={pre_trigger} ns: {len(merged)} merged hits")
```

## 常见问题

### Q: 如何确定我的 DAQ 系统的 pre_trigger 值？

A: 查看 DAQ 配置文件或硬件设置。常见值：
- CAEN V1725: 通常 100-200 个采样点
- CAEN VX2730: 可配置，查看寄存器设置
- 自定义系统: 查看 FPGA 配置或数据格式文档

### Q: 我的数据没有 pre_trigger，需要配置吗？

A: 不需要。默认 `pre_trigger_ns = 0` 假设 timestamp 已经是 sample 0 的时间。

### Q: 配置错误的 pre_trigger 值会有什么影响？

A: 会导致跨 record 的时间对齐偏差，可能造成：
- 本应合并的 hit 没有合并
- 本不应合并的 hit 被错误合并
- 时间特征计算不准确

### Q: 如何验证 pre_trigger 配置是否正确？

A:
1. 检查跨 record 合并的 hit 是否合理
2. 对比已知的物理事件时间与计算结果
3. 使用标定数据验证时间分辨率

## 参考

- 源代码：`waveform_analysis/core/processing/time_utils.py`
- 单元测试：`tests/core/processing/test_time_utils.py`
- 集成测试：`tests/plugins/test_hit_merge_pretrigger.py`
- 实现计划：`.claude/plans/add_pretrigger_support.md`
