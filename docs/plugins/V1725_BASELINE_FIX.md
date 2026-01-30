# V1725 Baseline 类型修复

## 问题描述

V1725 适配器的 baseline 字段类型与 ST_WAVEFORM_DTYPE 不匹配：

### 修复前

**V1725Reader 返回**:
```python
dtype = [
    ('channel', 'i2'),
    ('timestamp', 'i8'),
    ('baseline', 'i4'),  # ← int32 (整数)
    ('trunc', 'b1'),
    ('wave', 'O'),
]
```

**ST_WAVEFORM_DTYPE 期望**:
```python
ST_WAVEFORM_DTYPE = [
    ('baseline', 'f8'),  # ← float64 (浮点数)
    ('baseline_upstream', 'f8'),
    ('timestamp', 'i8'),
    ...
]
```

### 问题原因

- V1725 的二进制格式中，baseline 存储为 **12-bit 整数** (0-4095)
- ST_WAVEFORM_DTYPE 使用 **float64**，因为 VX2730 的 baseline 是通过平均值计算得到的浮点数
- 类型不匹配会导致后续处理出错

## 解决方案

### 修改位置

**文件**: `waveform_analysis/utils/formats/v1725.py`

**方法**: `V1725Reader._waves_to_array()`

### 修改内容

```python
def _waves_to_array(self, waves: List[V1725Wave]) -> np.ndarray:
    if not waves:
        return np.array([]).reshape(0, 0)

    dtype = np.dtype([
        ("channel", "i2"),
        ("timestamp", "i8"),
        ("baseline", "f8"),  # ← 改为 f8 (float64)
        ("trunc", "b1"),
        ("wave", "O"),
    ])

    arr = np.empty(len(waves), dtype=dtype)
    for i, wave in enumerate(waves):
        arr[i]["channel"] = wave.channel
        arr[i]["timestamp"] = wave.timestamp
        arr[i]["baseline"] = float(wave.baseline)  # ← 转换为 float64
        arr[i]["trunc"] = wave.trunc
        arr[i]["wave"] = wave.waveform
    return arr
```

### 关键改动

1. **dtype 定义**: `("baseline", "i4")` → `("baseline", "f8")`
2. **值转换**: `wave.baseline` → `float(wave.baseline)`

## 验证结果

```bash
$ python3 -c "验证脚本..."

============================================================
V1725 baseline 类型修复验证
============================================================

V1725Reader 输出:
  baseline 字段类型: float64
  baseline 值: [100. 105.]

ST_WAVEFORM_DTYPE:
  baseline 字段类型: float64

✓ 类型完全匹配！
  两者都是: float64

修复成功：V1725 的 baseline 现在是 float64，
与 ST_WAVEFORM_DTYPE 完全兼容！
```

## 优势

### 1. 保持类型一致性
- 所有适配器的 baseline 都是 float64
- 下游代码无需特殊处理

### 2. 语义正确性
- baseline 作为物理量（电压/ADC 值），使用浮点数更合理
- 支持小数精度（虽然 V1725 原始值是整数）

### 3. 向后兼容
- 不影响现有代码
- int32 → float64 是安全的类型提升
- 不会丢失精度（int32 范围 ±2^31，float64 精度 53 位）

### 4. 统一接口
- VX2730 和 V1725 现在返回相同的数据类型
- 插件系统可以统一处理

## 数据流验证

### V1725 数据流（修复后）

```
二进制文件 (.bin)
    ↓ V1725Reader.iter_waves()
V1725Wave 对象
  - baseline: int (100)
    ↓ V1725Reader._waves_to_array()
结构化数组
  - baseline: float64 (100.0)  ← 已转换
    ↓ WaveformsPlugin
waveforms (单个结构化数组)
  - baseline: float64
    ↓ StWaveformsPlugin
st_waveforms (按通道分组)
  - baseline: float64
    ↓ 后续插件
完全兼容 ST_WAVEFORM_DTYPE
```

### 与 VX2730 对比

| 特性 | VX2730 | V1725 (修复后) |
|------|--------|----------------|
| baseline 来源 | 计算平均值 | 二进制字段 |
| 原始类型 | float | int |
| 输出类型 | **float64** | **float64** ✓ |
| 精度 | 浮点精度 | 整数精度 (但用 float64 表示) |
| 兼容性 | ✓ | ✓ |

## 其他类型字段

### 已匹配的字段

| 字段 | V1725 | ST_WAVEFORM_DTYPE | 状态 |
|------|-------|-------------------|------|
| channel | i2 | i2 | ✓ 匹配 |
| timestamp | i8 | i8 | ✓ 匹配 |
| baseline | **f8** | **f8** | ✓ 已修复 |

### 仍需处理的字段

| 字段 | V1725 | ST_WAVEFORM_DTYPE | 状态 |
|------|-------|-------------------|------|
| wave | O (object) | f4[800] (固定长度) | ⚠️ 需转换 |
| baseline_upstream | - | f8 | ⚠️ 需添加 |
| event_length | - | i8 | ⚠️ 需添加 |

## 后续工作

### 1. wave 字段转换

**问题**: V1725 的 wave 是 object 类型（可变长度），ST_WAVEFORM_DTYPE 期望固定长度数组

**解决方案**:
```python
# 在转换时统一长度
max_len = max(len(w) for w in arr['wave'])
fixed_waves = np.zeros((len(arr), max_len), dtype=np.float32)
for i, w in enumerate(arr['wave']):
    fixed_waves[i, :len(w)] = w
```

### 2. 添加缺失字段

**baseline_upstream**:
```python
# V1725 没有上游 baseline，填充 NaN
arr['baseline_upstream'] = np.nan
```

**event_length**:
```python
# 从 wave 长度推断
arr['event_length'] = np.array([len(w) for w in arr['wave']])
```

## 总结

✅ **已完成**: V1725 的 baseline 字段类型已修复为 float64
✅ **验证通过**: 与 ST_WAVEFORM_DTYPE 完全匹配
⚠️ **待处理**: wave 字段转换和缺失字段添加

通过这个修复，V1725 适配器向与标准数据流完全兼容又迈进了一步！
