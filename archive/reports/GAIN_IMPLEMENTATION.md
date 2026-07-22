# hit_merged_features 增益校准功能实现总结

## 实现完成 ✅

已成功为 `HitMergedFeaturesPlugin` 添加增益校准功能，支持两种归一化模式。

## 核心变更

### 1. 数据结构变更

在 `HIT_MERGED_FEATURES_DTYPE` 中新增两个字段：

```python
("area_pe", "f4"),      # 峰面积（光电子单位）
("height_pe", "f4"),    # 峰高（光电子单位）
```

### 2. 版本升级

- **版本号**: 0.4.0 → **0.5.0**
- **变更类型**: MINOR（新增功能，向后兼容）
- **缓存**: 因 dtype 变更，现有缓存会失效

### 3. 新增配置选项

#### `gain_adc_per_pe` (dict)

```python
"gain_adc_per_pe": {
    "0:9": 200.0,
    "0:10": 200.0,
    # ...
}
```

#### `normalize_to_pe` (bool, 默认 False)

控制归一化模式的关键配置。

## 两种工作模式

### 模式 1: normalize_to_pe=False (默认，推荐)

```python
ctx.set_config({"gain_adc_per_pe": {...}})
```

**行为**:
- `area`, `height`: 保持 **ADC** 单位（原始值）
- `area_pe`, `height_pe`: **PE** 单位（校准值）

**特点**:
- ✅ 向后兼容
- ✅ 同时保留原始值和校准值
- ✅ 适合需要原始数据的场景

### 模式 2: normalize_to_pe=True (直接归一化)

```python
ctx.set_config({
    "gain_adc_per_pe": {...},
    "normalize_to_pe": True
})
```

**行为**:
- `area`, `height`: **PE** 单位（已归一化）
- `area_pe`, `height_pe`: **NaN**（因为 area/height 已经是 PE）

**特点**:
- ✅ 数据简洁，无冗余
- ✅ 适合只需要 PE 单位的新项目
- ⚠️ 改变了字段语义，不向后兼容旧工作流

## 使用示例

### 快速开始

```python
# 设置通道 9-15 的增益为 200 ADC/PE
ctx.set_config({
    "gain_adc_per_pe": {
        "0:9": 200.0,
        "0:10": 200.0,
        "0:11": 200.0,
        "0:12": 200.0,
        "0:13": 200.0,
        "0:14": 200.0,
        "0:15": 200.0,
    }
})

# 获取数据
features = ctx.get_array(run_id="your_run", target="hit_merged_features")

# area/height 保持 ADC，area_pe/height_pe 输出 PE
```

## 测试示例

```bash
# 对比两种模式
python examples/demo_normalize_modes.py

# 批量配置工具
python examples/set_gain_batch.py --channels 9-15 --gain 200
```

## 文件变更

- ⭐ `waveform_analysis/core/plugins/builtin/cpu/hit_merged_features.py` (修改)
- 📝 `examples/demo_normalize_modes.py` (新增)
- 📝 `examples/simple_spe_gain_example.py` (新增)
- 🛠️ `examples/set_gain_batch.py` (新增)

**状态**: ✅ 实现完成
