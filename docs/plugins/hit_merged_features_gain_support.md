# hit_merged_features 增益校准功能

## 更新内容

为 `HitMergedFeaturesPlugin` 添加了单光子增益（SPE gain）校准功能，新增 `area_pe` 和 `height_pe` 字段。

## 版本变更

- **版本**: 0.4.0 → 0.5.0
- **变更类型**: MINOR（新增功能，向后兼容）

## 新增字段

在 `HIT_MERGED_FEATURES_DTYPE` 中新增：

- `area_pe` (f4): 峰面积，单位为光电子数（PE）
- `height_pe` (f4): 峰高，单位为光电子数（PE）

原有字段保持不变：
- `area` (f4): 峰面积，单位为 ADC counts
- `height` (f4): 峰高，单位为 ADC counts

## 配置参数

新增配置选项 `gain_adc_per_pe`:

```python
"gain_adc_per_pe": Option(
    default=None,
    type=dict,
    help=(
        '按硬件通道配置 ADC/PE 增益，键请使用 "board:channel"，'
        '例如 {"0:0": 12.5, "0:1": 13.2}。'
        "设置后会新增 area_pe/height_pe 列。"
    ),
)
```

## 使用方法

### 1. 基本配置

```python
from waveform_analysis.core.context import Context

ctx = Context()
ctx.register(...)  # 注册相关插件

# 设置增益配置
gain_config = {
    "0:9": 200.0,   # board 0, channel 9
    "0:10": 200.0,  # board 0, channel 10
    "0:11": 200.0,  # board 0, channel 11
    "0:12": 200.0,  # board 0, channel 12
    "0:13": 200.0,  # board 0, channel 13
    "0:14": 200.0,  # board 0, channel 14
    "0:15": 200.0,  # board 0, channel 15
}

ctx.set_config({"gain_adc_per_pe": gain_config})

# 获取数据
features = ctx.get_array(run_id="your_run", target="hit_merged_features")

# 现在 features 包含:
# - area, height (ADC 单位)
# - area_pe, height_pe (PE 单位)
```

### 2. 数据访问

```python
# 原始 ADC 值
area_adc = features["area"]
height_adc = features["height"]

# 校准后的 PE 值
area_pe = features["area_pe"]
height_pe = features["height_pe"]

# 转换关系
# area_pe = area / gain_adc_per_pe
# height_pe = height / gain_adc_per_pe
```

### 3. 未配置增益的行为

- 如果没有配置 `gain_adc_per_pe`，`area_pe` 和 `height_pe` 将为 `NaN`
- 如果只为部分通道配置增益，未配置的通道对应的 `area_pe` 和 `height_pe` 为 `NaN`

## 实现细节

### 数据流程

```
hit_merged → HitMergedFeaturesPlugin → 计算 area, height (ADC)
                                    ↓
                         _apply_gain_calibration()
                                    ↓
                         添加 area_pe, height_pe (PE)
```

### 增益校准逻辑

1. 从配置中获取 `gain_adc_per_pe` 字典
2. 解析为每个硬件通道的增益映射
3. 对每条 feature 记录：
   - 根据 `board` 和 `channel` 查找对应的增益值
   - 如果找到增益值：`area_pe = area / gain`，`height_pe = height / gain`
   - 如果未找到增益值：`area_pe = NaN`，`height_pe = NaN`

### 性能考虑

- 增益校准在特征计算完成后进行，不影响原有计算性能
- 使用向量化操作，对大数据量友好

## 测试

运行测试示例：

```bash
python examples/test_hit_merged_features_gain.py
```

## 向后兼容性

- ✅ 完全向后兼容
- ✅ 保留所有原有字段
- ✅ 新增字段不影响现有代码
- ✅ 未配置增益时，新字段填充 NaN

## 相关插件

类似的增益校准功能已在以下插件中实现：

- `DataFramePlugin` (df): 已支持 `gain_adc_per_pe`
- `HitMergedFeaturesPlugin` (hit_merged_features): 本次新增

## 示例文件

- `examples/test_hit_merged_features_gain.py`: 测试示例
- `examples/simple_spe_gain_example.py`: 简单配置示例
- `examples/gain_integration_guide.py`: 完整集成指南

## 注意事项

1. **增益值单位**: `gain_adc_per_pe` 表示每个光电子对应的 ADC 计数值
2. **配置格式**: 通道键必须使用 `"board:channel"` 格式（例如 `"0:9"`）
3. **增益值验证**: 增益值必须为正数，否则对应通道的 PE 值为 NaN
4. **缓存失效**: 修改 `gain_adc_per_pe` 配置会触发插件版本升级，导致缓存失效

## 后续工作

可考虑为以下插件添加增益支持：

- `PeakletPlugin`: 添加 peaklet 级别的 PE 校准
- `BasicFeaturesPlugin`: 添加单通道基础特征的 PE 校准

## 更新日期

2026-06-23
