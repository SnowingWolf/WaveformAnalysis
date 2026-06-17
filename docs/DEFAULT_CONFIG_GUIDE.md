# PeakletS1S2ClassifierPlugin 默认配置说明

## 🎯 默认分类规则

插件使用 **n_hits** 和 **rise_time_10_50** 作为默认分类条件：

```
┌─────────────┬──────────────────┬──────────┬────────────────────────────────┐
│ n_hits      │ rise_time_10_50  │ 分类结果 │ 说明                           │
├─────────────┼──────────────────┼──────────┼────────────────────────────────┤
│ < 8         │ 任意             │ S1       │ 少量 hits（单通道或少量通道）  │
│ >= 8        │ <= 100 ns        │ S1       │ 多 hits 但快速上升（类 S1）    │
│ >= 8        │ > 100 ns         │ S2       │ 多 hits 且慢速上升（典型 S2）  │
└─────────────┴──────────────────┴──────────┴────────────────────────────────┘
```

## 📝 使用示例

### 使用默认配置（推荐）

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import PeakletS1S2ClassifierPlugin

ctx = Context()
ctx.register(PeakletS1S2ClassifierPlugin())

# 不需要任何配置，直接使用默认规则
labels = ctx.get_data(run_id, "peaklet_s1_s2")
```

**默认配置等价于：**
```python
ctx.set_config(
    {
        "s2_ranges": {
            "n_hits": (8, None),
            "rise_time_10_50": (100.01, None),
        },
        "default_label": "s1",  # 不满足 S2 条件的都判为 S1
    },
    plugin_name="peaklet_s1_s2",
)
```

### 自定义配置

```python
# 例 1：添加更多 S2 判断条件
ctx.set_config(
    {
        "s2_ranges": {
            "n_hits": (8, None),
            "rise_time_10_50": (100.01, None),
            "width": (300.0, None),      # 额外：宽脉冲
            "area": (1000.0, None),      # 额外：大面积
        },
    },
    plugin_name="peaklet_s1_s2",
)

# 例 2：同时配置 S1 和 S2
ctx.set_config(
    {
        "s1_ranges": {
            "width": (0.0, 100.0),
            "n_hits": (1, 7),
        },
        "s2_ranges": {
            "width": (300.0, None),
            "n_hits": (8, None),
            "rise_time_10_50": (100.01, None),
        },
        "default_label": "unknown",  # 改为 Unknown
    },
    plugin_name="peaklet_s1_s2",
)
```

## ⚙️ 配置选项说明

### s2_ranges (dict)
**默认值：** `{"n_hits": (8, None), "rise_time_10_50": (100.01, None)}`

S2 特征范围字典，所有条件必须**同时满足**（AND 逻辑）。

### s1_ranges (dict)
**默认值：** `None`

S1 特征范围字典。默认不配置，依赖 `default_label` 将不满足 S2 的判为 S1。

### default_label (str)
**默认值：** `"s1"`
**可选值：** `"unknown"`, `"s1"`, `"s2"`

当不满足任何配置条件时的默认标签。

- `"s1"` - 凡不满足 S2 的都判为 S1（**推荐用于默认配置**）
- `"unknown"` - 不满足条件时标记为 Unknown
- `"s2"` - 凡不满足 S1 的都判为 S2

### conflict_policy (str)
**默认值：** `"prefer_s1"`
**可选值：** `"unknown"`, `"prefer_s1"`, `"prefer_s2"`

当同时满足 S1 和 S2 条件时的处理策略。

### strict (bool)
**默认值：** `False`

是否要求至少配置一个 S1 或 S2 判断条件。

## 🔬 物理意义

### 为什么用 n_hits 和 rise_time_10_50？

1. **n_hits >= 8** - S2 的多通道特性
   - S2 信号由电子漂移产生，扩散范围大
   - 触发多个 PMT 通道，产生更多 hit
   - n_hits < 8 通常是局域化的 S1 直接闪烁

2. **rise_time_10_50 > 100 ns** - S2 的慢速上升特性
   - S2 信号上升时间长，反映电子云的扩散过程
   - S1 信号上升极快（< 30 ns），直接闪烁光子
   - rise_time_10_50 测量 10% 到 50% 面积的时间，更稳定

### 边界情况处理

**n_hits >= 8 但 rise_time_10_50 <= 100 ns**：
- 可能是强 S1 信号（高能量导致多通道响应）
- 可能是 PMT 阵列几何效应
- 默认判为 S1（快速上升特性占主导）

## 📊 测试验证

运行测试脚本验证默认配置：
```bash
python examples/test_default_config.py
```

预期输出：
```
✓ Peak 0: n_hits= 5, rise_time_10_50=  50.0 ns → S1
✓ Peak 1: n_hits= 8, rise_time_10_50=  80.0 ns → S1
✓ Peak 2: n_hits= 8, rise_time_10_50= 120.0 ns → S2
✓ Peak 3: n_hits=15, rise_time_10_50=  90.0 ns → S1
✓ Peak 4: n_hits=20, rise_time_10_50= 150.0 ns → S2
```

## 🎓 常见问题

### Q: 为什么默认不配置 S1 范围？
**A:** 使用 `default_label="s1"` 更简洁。只需定义 S2 的明确条件，其他都自动判为 S1。

### Q: 如何调整分类阈值？
**A:** 根据实验数据调整配置：
```python
{
    "s2_ranges": {
        "n_hits": (10, None),        # 提高到 10
        "rise_time_10_50": (120.0, None),  # 提高到 120 ns
    },
}
```

### Q: 如何让边界情况返回 Unknown？
**A:** 设置 `default_label="unknown"`：
```python
{
    "s2_ranges": {
        "n_hits": (8, None),
        "rise_time_10_50": (100.01, None),
    },
    "default_label": "unknown",
}
```

### Q: 可以只用 n_hits 或只用 rise_time_10_50 吗？
**A:** 可以，单独配置其中一个：
```python
# 仅用 n_hits
{"s2_ranges": {"n_hits": (8, None)}}

# 仅用 rise_time_10_50
{"s2_ranges": {"rise_time_10_50": (100.01, None)}}
```

## 🔗 相关文档

- **完整实现总结**：`docs/IMPLEMENTATION_SUMMARY.md`
- **重构说明**：`docs/peaklet_s1_s2_classifier_refactor.md`
- **演示脚本**：`examples/demo_peaklet_s1_s2_n_hits_rise_time.py`
- **默认配置测试**：`examples/test_default_config.py`
