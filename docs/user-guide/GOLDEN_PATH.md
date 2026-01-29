# 黄金路径：5 分钟上手指南

**导航**: [文档中心](../README.md) > [用户指南](README.md) > 黄金路径

> **只看这一页就能跑起来**

---

## 1. 目录结构

WaveformAnalysis 期望的 DAQ 数据目录结构：

```
DAQ/                          # data_root（可配置）
├── run_001/                  # run_id
│   └── RAW/                  # 原始数据子目录
│       ├── DataR_CH6.CSV     # 通道 6 数据文件
│       ├── DataR_CH7.CSV     # 通道 7 数据文件
│       └── ...
├── run_002/
│   └── RAW/
│       └── ...
└── run_003/
    └── RAW/
        └── ...
```

**说明**：
- `DAQ/` 是数据根目录，通过 `data_root` 配置
- `run_001/` 等是运行目录，作为 `run_id` 传入
- `RAW/` 是原始数据子目录（VX2730 默认布局）
- `*CH*.CSV` 是波形数据文件，通道号从文件名提取

---

## 2. 最小代码

```python
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import standard_plugins

# 1. 创建 Context
ctx = Context(storage_dir='./cache')

# 2. 注册标准插件
ctx.register(*standard_plugins)

# 3. 最小配置（只需 3 项）
ctx.set_config({
    'data_root': 'DAQ',           # 数据根目录
    'daq_adapter': 'vx2730',      # DAQ 适配器
    'threshold': 15.0,            # 信号阈值（可选）
})

# 4. 获取数据
run_id = 'run_001'
basic_features = ctx.get_data(run_id, 'basic_features')

# 5. 使用结果
for ch_idx, ch_data in enumerate(basic_features):
    print(f"通道 {ch_idx}: {len(ch_data)} 个事件")
    print(f"  height: {ch_data['height'][:3]}...")
    print(f"  area:   {ch_data['area'][:3]}...")
```

---

## 3. 配置说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `data_root` | str | `"DAQ"` | 数据根目录路径 |
| `daq_adapter` | str | `"vx2730"` | DAQ 适配器名称 |
| `threshold` | float | `10.0` | Hit 检测阈值 |

**内置 DAQ 适配器**：
- `vx2730` - CAEN VX2730 数字化仪（CSV 格式）
- `v1725` - CAEN V1725 数字化仪（二进制格式）

---

## 4. 输出产物

### 4.1 basic_features 结构

`basic_features` 是一个列表，每个元素对应一个通道的 NumPy 结构化数组：

```python
# 数据结构
basic_features: List[np.ndarray]  # 长度 = 通道数

# 每个通道的 dtype
dtype = [
    ('height', 'f4'),  # 波形高度 (max - min)
    ('area', 'f4'),    # 波形面积 (积分)
]
```

**字段说明**：

| 字段 | 类型 | 单位 | 计算方式 |
|------|------|------|----------|
| `height` | float32 | ADC counts | `max(wave) - min(wave)` |
| `area` | float32 | ADC counts × samples | `sum(baseline - wave)` |

### 4.2 访问示例

```python
# 获取所有通道的 height
all_heights = [ch['height'] for ch in basic_features]

# 获取通道 0 的数据
ch0_heights = basic_features[0]['height']
ch0_areas = basic_features[0]['area']

# 统计
print(f"通道 0 平均高度: {ch0_heights.mean():.2f}")
print(f"通道 0 平均面积: {ch0_areas.mean():.2f}")
```

### 4.3 导出为 CSV

```python
import pandas as pd

# 转换为 DataFrame
rows = []
for ch_idx, ch_data in enumerate(basic_features):
    for i in range(len(ch_data)):
        rows.append({
            'channel': ch_idx,
            'height': ch_data['height'][i],
            'area': ch_data['area'][i],
        })

df = pd.DataFrame(rows)
df.to_csv('basic_features.csv', index=False)
```

**导出文件样例** (`basic_features.csv`)：

```csv
channel,height,area
0,125.3,4521.7
0,98.7,3892.1
0,142.5,5103.4
1,87.2,3245.8
1,156.8,5678.2
...
```

---

## 5. 数据流水线

```
raw_files → waveforms → st_waveforms → basic_features
    │           │            │              │
    │           │            │              └─ height/area 特征
    │           │            └─ 结构化数组 (timestamp, baseline, wave)
    │           └─ 原始波形数据 (2D numpy array)
    └─ 文件路径列表
```

**可视化血缘图**：

```python
ctx.plot_lineage('basic_features', kind='labview')
```

---

## 6. 常见问题

### Q: 找不到数据文件？

检查目录结构是否正确：
```python
# 调试：查看扫描到的文件
raw_files = ctx.get_data('run_001', 'raw_files')
print(f"通道数: {len(raw_files)}")
for i, files in enumerate(raw_files):
    print(f"  通道 {i}: {len(files)} 个文件")
```

### Q: 如何查看中间数据？

```python
# 查看结构化波形
st_waveforms = ctx.get_data('run_001', 'st_waveforms')
print(f"通道 0 的 dtype: {st_waveforms[0].dtype}")
print(f"通道 0 的字段: {st_waveforms[0].dtype.names}")
```

### Q: 如何清除缓存重新计算？

```python
ctx.clear_cache('run_001', 'basic_features')
# 或清除所有缓存
ctx.clear_cache('run_001')
```

---

## 7. 下一步

| 需求 | 文档 |
|------|------|
| 更多配置选项 | [配置管理](../features/context/CONFIGURATION.md) |
| 批量处理多个 run | [快速开始 - 批量处理](QUICKSTART_GUIDE.md#场景-2-批量处理) |
| 自定义 DAQ 格式 | [快速开始 - 自定义格式](QUICKSTART_GUIDE.md#场景-4-使用自定义-daq-格式) |
| 可视化数据流 | [血缘可视化指南](../features/context/LINEAGE_VISUALIZATION_GUIDE.md) |
| 开发自定义插件 | [插件开发教程](../features/plugin/SIMPLE_PLUGIN_GUIDE.md) |

---

**快速链接**:
[快速开始](QUICKSTART_GUIDE.md) |
[配置管理](../features/context/CONFIGURATION.md) |
[示例代码](EXAMPLES_GUIDE.md)
