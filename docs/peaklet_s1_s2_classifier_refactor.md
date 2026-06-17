# PeakletS1S2ClassifierPlugin 重构总结

## 重构内容

对 `PeakletS1S2ClassifierPlugin` 进行了两项重大重构：

### 1. 添加新特征支持
- **n_hits**：peaklet 包含的 hit 数量
- **rise_time_10_50**：信号从 10% 到 50% 面积的上升时间（单位：ns）

### 2. 架构优化
- **配置方式**：从独立配置项改为字典配置（`s1_ranges` 和 `s2_ranges`）
- **依赖简化**：从依赖 `["peaklet_features", "peaklets"]` 改为仅依赖 `["peaks"]`

## 配置对比

### 旧配置方式（v0.1.0）
```python
ctx.set_config(
    {
        # S1 配置
        "s1_width_range": (0.0, 100.0),
        "s1_area_range": (0.0, 500.0),
        "s1_height_range": None,
        "s1_rise_time_range": (0.0, 30.0),
        "s1_fall_time_range": (0.0, 50.0),
        "s1_n_channels_range": None,
        "s1_n_hits_range": None,
        "s1_rise_time_10_50_range": None,

        # S2 配置
        "s2_width_range": (300.0, None),
        "s2_area_range": (1000.0, None),
        "s2_height_range": None,
        "s2_rise_time_range": None,
        "s2_fall_time_range": None,
        "s2_n_channels_range": None,
        "s2_n_hits_range": (8, None),
        "s2_rise_time_10_50_range": (100.0, None),

        "conflict_policy": "unknown",
    },
    plugin_name="peaklet_s1_s2",
)
```

### 新配置方式（v1.0.0）
```python
ctx.set_config(
    {
        # S1 配置 - 使用字典
        "s1_ranges": {
            "width": (0.0, 100.0),
            "area": (0.0, 500.0),
            "rise_time": (0.0, 30.0),
            "fall_time": (0.0, 50.0),
        },

        # S2 配置 - 使用字典
        "s2_ranges": {
            "width": (300.0, None),
            "area": (1000.0, None),
            "n_hits": (8, None),
            "rise_time_10_50": (100.0, None),
        },

        "conflict_policy": "unknown",
    },
    plugin_name="peaklet_s1_s2",
)
```

## 新配置方式的优势

1. **更简洁**
   - 使用字典配置，不需要为每个特征单独定义配置项
   - 只配置需要的特征，未使用的特征不需要显式设置为 None

2. **更灵活**
   - 可以动态添加任何 peaks 中的特征，无需修改插件代码
   - 支持的特征字段：
     - `width`: 宽度 (ns)
     - `area`: 面积
     - `height`: 高度
     - `rise_time`: 上升时间 (ns)，从 10% 到峰值
     - `fall_time`: 下降时间 (ns)，从峰值到 90%
     - `rise_time_10_50`: 上升时间 (ns)，从 10% 到 50%
     - `width_25_75`: 宽度 (ns)，25%-75%
     - `range_90p_area`: 90% 面积范围 (ns)
     - `n_hits`: hits 数量
     - `n_channels`: 通道数量

3. **更直观**
   - 直接看配置就知道用了哪些特征
   - 字典结构清晰展示每个类型使用的判断条件

4. **依赖更简单**
   - 仅依赖 `peaks`，无需分别依赖 `peaklet_features` 和 `peaklets`
   - `peaks` 已包含所有需要的字段（由 `PeaksPlugin` 合并生成）
   - 减少了数据查询和映射的复杂度

## 版本变化

| 版本 | 配置方式 | 依赖 | 新特征支持 |
|------|---------|------|-----------|
| v0.1.0 | 独立配置项 | `["peaklet_features", "peaklets"]` | n_hits, rise_time_10_50 |
| v1.0.0 | 字典配置 | `["peaks"]` | n_hits, rise_time_10_50 |

## 向后兼容性

**⚠️ 不兼容变更**：配置方式已完全改变，旧配置需要迁移到新格式。

### 迁移指南

#### 迁移步骤
1. 将所有 `s1_*_range` 配置项合并到 `s1_ranges` 字典
2. 将所有 `s2_*_range` 配置项合并到 `s2_ranges` 字典
3. 去掉配置项名称中的 `_range` 后缀
4. 更新依赖声明（如果手动管理）

#### 字段名映射
| 旧配置项 | 新字段名 |
|---------|---------|
| `s1_width_range` | `width` |
| `s1_area_range` | `area` |
| `s1_height_range` | `height` |
| `s1_rise_time_range` | `rise_time` |
| `s1_fall_time_range` | `fall_time` |
| `s1_n_channels_range` | `n_channels` |
| `s1_n_hits_range` | `n_hits` |
| `s1_rise_time_10_50_range` | `rise_time_10_50` |

（S2 配置同理）

#### 迁移示例

**旧配置：**
```python
{
    "s1_width_range": (0.0, 100.0),
    "s1_area_range": (0.0, 500.0),
    "s2_width_range": (300.0, None),
    "s2_n_hits_range": (8, None),
}
```

**新配置：**
```python
{
    "s1_ranges": {
        "width": (0.0, 100.0),
        "area": (0.0, 500.0),
    },
    "s2_ranges": {
        "width": (300.0, None),
        "n_hits": (8, None),
    },
}
```

## 测试覆盖

所有 11 个测试用例通过，覆盖率 91%：
- ✅ 基本分类功能
- ✅ 空输入处理
- ✅ 冲突策略（prefer_s1, prefer_s2, unknown）
- ✅ 严格模式
- ✅ n_channels 过滤
- ✅ 输出字段完整性
- ✅ n_hits 过滤
- ✅ rise_time_10_50 过滤
- ✅ 组合条件（n_hits + rise_time_10_50）

## 文件修改清单

1. **插件实现**：`waveform_analysis/core/plugins/builtin/cpu/peaklet_s1_s2_classifier.py`
   - 版本升级：v0.1.0 → v1.0.0
   - 配置选项重构：独立配置项 → 字典配置
   - 依赖简化：`["peaklet_features", "peaklets"]` → `["peaks"]`
   - 添加辅助方法：`_normalize_ranges`, `_extract_features`, `_check_criteria`

2. **测试文件**：`tests/plugins/test_peaklet_s1_s2_classifier_plugin.py`
   - 更新导入：`PEAKLET_DTYPE, PEAKLET_FEATURES_DTYPE` → `PEAKS_DTYPE`
   - 重写测试数据生成：`_make_peaklet_features()`, `_make_peaklets()` → `_make_peaks()`
   - 更新所有测试配置为新格式

3. **演示脚本**：`examples/demo_peaklet_s1_s2_n_hits_rise_time.py`
   - 更新为使用 `peaks` 数据
   - 展示新配置方式
   - 添加配置方式对比说明

4. **文档**：
   - `docs/peaklet_s1_s2_classifier_update.md`（旧版本特性文档）
   - `docs/peaklet_s1_s2_classifier_refactor.md`（本文档）

## 验证结果

✅ **11/11 测试通过**
✅ **类型检查无错误**
✅ **演示脚本正常运行**
✅ **功能完全保留**
✅ **代码更简洁（100 行 vs 106 行）**

## 使用建议

### 典型的 S2 判断配置
```python
{
    "s2_ranges": {
        "width": (300.0, None),          # 宽脉冲
        "area": (1000.0, None),          # 大面积
        "n_hits": (8, None),             # 多 hit
        "rise_time_10_50": (100.0, None), # 慢速上升
    },
}
```

### 组合使用 S1 和 S2
```python
{
    "s1_ranges": {
        "width": (0.0, 100.0),
        "area": (0.0, 500.0),
        "rise_time_10_50": (0.0, 30.0),
        "n_hits": (1, 7),
    },
    "s2_ranges": {
        "width": (300.0, None),
        "area": (1000.0, None),
        "rise_time_10_50": (100.0, None),
        "n_hits": (8, None),
    },
    "conflict_policy": "unknown",
}
```

## 实现细节

### 数据流

```
peaks (from PeaksPlugin)
  ↓
PeakletS1S2ClassifierPlugin.compute()
  ↓
_extract_features() → 提取特征字典
  ↓
_check_criteria() → 检查 S1/S2 条件
  ↓
应用 conflict_policy → 确定最终标签
  ↓
输出 peaklet_s1_s2 结果
```

### 核心逻辑

```python
# 1. 标准化配置
s1_criteria = _normalize_ranges(s1_ranges)  # dict[str, tuple[float, float]]
s2_criteria = _normalize_ranges(s2_ranges)

# 2. 提取特征
features = _extract_features(peak)  # dict[str, float]

# 3. 检查条件（AND 逻辑）
s1_ok = _check_criteria(features, s1_criteria)
s2_ok = _check_criteria(features, s2_criteria)

# 4. 应用策略
if s1_ok and not s2_ok:
    label = LABEL_S1
elif s2_ok and not s1_ok:
    label = LABEL_S2
elif s1_ok and s2_ok:
    label = apply_conflict_policy()
else:
    label = LABEL_UNKNOWN
```

## 性能影响

- **减少数据查询**：从 2 次（peaklet_features + peaklets）减少到 1 次（peaks）
- **减少映射开销**：不再需要 peak_id 映射
- **内存优化**：仅加载一个数组而非两个
- **代码简化**：逻辑更清晰，维护更容易
