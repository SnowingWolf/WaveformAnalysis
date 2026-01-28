**导航**: [文档中心](../../README.md) > [plugins](../README.md) > [builtin](README.md) > 电荷计算方法对比

# 电荷计算方法对比

## ChargesPlugin vs WaveformWidthIntegralPlugin["q_total"]

本文档说明 `ChargesPlugin` 和 `WaveformWidthIntegralPlugin` 中 `q_total` 字段的计算差异。

---

### 1. ChargesPlugin

**实现位置:** `waveform_analysis.core.plugins.builtin.cpu.standard.ChargesPlugin`

**计算公式:**
```python
q = sum(baseline - wave)  # 在 area_range 范围内
```

**关键特性:**
- **积分范围**: 由 `area_range` 决定（默认: `(0, None)`，即整个波形）
- **符号约定**: `baseline - wave`（对于负脉冲，结果为正）
- **极性处理**: 无极性过滤，直接对 `baseline - wave` 求和
- **向量化计算**: 使用 NumPy 向量化操作，高效处理大量事件

**代码实现:**
```python
waves_c = st_ch["wave"][:, start_c:end_c]  # 切片到 area_range
baselines = st_ch["baseline"]
q_vals = np.sum(baselines[:, np.newaxis] - waves_c, axis=1)
```

**使用场景:**
- 快速计算指定时间窗口内的电荷
- 需要与历史数据保持一致的计算方法
- 仅关注信号主要部分的电荷

---

### 2. WaveformWidthIntegralPlugin["q_total"]

**实现位置:** `waveform_analysis.core.plugins.builtin.cpu.waveform_width_integral.WaveformWidthIntegralPlugin`

**计算公式:**
```python
signal = wave - baseline
x = polarity_filter(signal)  # 根据 polarity 参数过滤
q_total = sum(x)  # 对整个波形求和
```

**关键特性:**
- **积分范围**: 对整个波形求和（不限制范围）
- **符号约定**: `wave - baseline`（与 ChargesPlugin 符号相反）
- **极性处理**: 支持三种模式
  - `"positive"`: 仅计算正信号部分 `max(signal, 0)`
  - `"negative"`: 仅计算负信号部分 `max(-signal, 0)`
  - `"auto"`: 自动选择面积更大的极性
- **用途**: 主要用于计算积分分位数宽度（t_low/t_high，取决于 q_low/q_high），`q_total` 是副产品

**代码实现:**
```python
signal = wave - baseline

if polarity == "positive":
    x = np.maximum(signal, 0.0)
elif polarity == "negative":
    x = np.maximum(-signal, 0.0)
else:  # auto
    pos_area = np.sum(np.maximum(signal, 0.0))
    neg_area = np.sum(np.maximum(-signal, 0.0))
    x = np.maximum(-signal, 0.0) if neg_area > pos_area else np.maximum(signal, 0.0)

q_total = float(np.sum(x))
```

---

### 3. 主要差异总结

| 特性 | BasicFeaturesPlugin["area"] | WaveformWidthIntegralPlugin["q_total"] |
|------|--------------|----------------------------------------|
| **积分范围** | `area_range` (默认整段波形，可配置子区间) | 整个波形 |
| **符号约定** | `baseline - wave` | `wave - baseline` |
| **极性过滤** | 无 | 支持 positive/negative/auto |
| **主要用途** | 电荷特征提取 | 积分分位数宽度计算（q_total 为副产品） |
| **计算效率** | 向量化，高效 | 逐事件循环，较慢 |
| **输出格式** | `List[np.ndarray]` (每个通道一个数组) | 结构化数组，包含 t_low/t_high/width 等字段 |

---

### 4. 数值关系

对于相同的波形和配置：

1. **符号关系**:
   - 如果 `polarity="auto"` 且自动选择了负极性，则：
     ```
     q_total ≈ -area (在相同范围内)
     ```
   - 如果 `polarity="positive"`，则符号可能不同

2. **范围差异**:
   - `q_total` 包含整个波形的积分
   - `area` 取决于 `area_range`，当配置为子区间时仅积分部分波形
   - 当 `area_range` 不覆盖全波形时，`abs(q_total) >= abs(area)`（在相同极性下）

3. **实际示例**:
   ```python
   # 假设波形长度为 500 采样点，area_range=(60, 400)
   # 对于负脉冲信号：

   # BasicFeaturesPlugin
   area = sum(baseline - wave[60:400])  # 仅 60-400 范围

   # WaveformWidthIntegralPlugin (polarity="auto", 选择负极性)
   q_total = sum(-(wave - baseline))  # 整个波形 0-500
        = sum(baseline - wave)  # 整个波形
   ```

---

### 5. 使用建议

**使用 BasicFeaturesPlugin["area"] 当:**
- 需要快速计算指定时间窗口的电荷
- 需要与历史分析保持一致
- 仅关注信号主要部分的电荷
- 需要向量化高效计算

**使用 WaveformWidthIntegralPlugin["q_total"] 当:**
- 需要计算整个波形的总电荷
- 需要根据极性过滤信号
- 同时需要积分分位数宽度信息（t_low/t_high）
- 需要更精确的电荷估计（包含整个信号）

---

### 6. 代码示例

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import BasicFeaturesPlugin, WaveformWidthIntegralPlugin

ctx = Context()

# 注册插件
ctx.register(BasicFeaturesPlugin())
ctx.register(WaveformWidthIntegralPlugin())

# 计算电荷
basic_features = ctx.get_data('run_001', 'basic_features')  # List[np.ndarray]
width_integral = ctx.get_data('run_001', 'waveform_width_integral')  # List[np.ndarray]

# 比较结果
ch0_area = basic_features[0]['area']  # 每个事件的电荷（area_range 范围内）
ch0_q_total = width_integral[0]['q_total']  # 每个事件的总电荷（整个波形）

# 注意符号和范围的差异
print(f"Area range: {ch0_area.min():.2f} - {ch0_area.max():.2f}")
print(f"Q_total range: {ch0_q_total.min():.2f} - {ch0_q_total.max():.2f}")
```

---

**文档版本:** 1.0.0
**最后更新:** 2026-01-09
