# 波形预览功能快速入门

## 简介

波形预览功能是一个轻量级工具，允许你在完整数据处理前快速查看原始波形数据，用于确定阈值、基线等参数。

**核心优势**：
- ✅ **轻量级**：无需运行完整处理流程
- ✅ **快速**：流式读取，仅加载必要数据
- ✅ **灵活**：支持按事件范围或时间戳范围选择
- ✅ **独立**：可读取未在 st_waveforms 中的通道数据

---

## 安装

确保已安装 WaveformAnalysis 包：

```bash
cd /mnt/data/Run3/WaveformAnalysis
pip install -e .
```

---

## 快速开始

### 示例 1：基本使用

```python
from waveform_analysis.utils.preview import WaveformPreviewer
import matplotlib.pyplot as plt

# 1. 初始化预览器
previewer = WaveformPreviewer(
    run_name="49V_OV_circulation_CH0_Coincidence_20dB",
    n_channels=4,
    data_root="DAQ"
)

# 2. 按事件范围加载波形
waveforms = previewer.load_by_range(
    channel=2,           # 通道号
    start_event=0,       # 起始事件索引
    end_event=50         # 结束事件索引（不包含）
)

print(f"加载了 {len(waveforms)} 个波形")
```

### 示例 2：叠加显示多个波形

```python
# 叠加显示前10个波形
fig = previewer.plot_overlay(
    waveforms[:10],
    annotate=True,              # 标注基线、峰值、积分区域
    peaks_range=(40, 90),       # 峰值检测区间
    charge_range=(60, 400),     # 电荷积分区间
    figsize=(14, 6)
)
plt.show()
```

### 示例 3：分格显示每个波形

```python
# 每个波形一个子图
fig = previewer.plot_grid(
    waveforms[:6],
    annotate=True,
    ncols=3,                    # 3列布局
    figsize_per_plot=(5, 3.5)
)
plt.show()
```

### 示例 4：计算波形特征

```python
# 计算基线、峰值、电荷等特征
features = previewer.compute_features(waveforms)

print(f"基线均值: {features['baselines'].mean():.2f} ADC")
print(f"峰值均值: {features['peaks'].mean():.2f} ADC")
print(f"电荷均值: {features['charges'].mean():.2f} ADC")
```

### 示例 5：按时间戳范围加载

```python
# 加载特定时间段的波形
waveforms_time = previewer.load_by_timestamp(
    channel=2,
    start_ts=1000000000000,  # 1e12 ps = 1 秒
    end_ts=1002000000000     # 1.002 秒
)

print(f"时间范围内加载了 {len(waveforms_time)} 个事件")
```

### 示例 6：使用便捷函数（一行代码）

```python
from waveform_analysis.utils.preview import preview_waveforms

# 快速预览
fig = preview_waveforms(
    run_name="49V_OV_circulation_CH0_Coincidence_20dB",
    channel=3,
    event_range=(0, 20),
    plot_mode='overlay',     # 'overlay' 或 'grid'
    annotate=True,
    n_channels=4
)
plt.show()
```

---

## 高级用法

### 对比多个通道

```python
import numpy as np
import matplotlib.pyplot as plt

# 加载两个通道的数据
waveforms_ch2 = previewer.load_by_range(channel=2, start_event=0, end_event=50)
waveforms_ch3 = previewer.load_by_range(channel=3, start_event=0, end_event=50)

# 创建对比图
fig, axes = plt.subplots(1, 2, figsize=(16, 5))

# CH2
for i, record in enumerate(waveforms_ch2[:10]):
    wave = record['wave']
    x = np.arange(len(wave)) * 2.0  # 采样间隔 2ns
    axes[0].plot(x, wave, alpha=0.6)
axes[0].set_title('CH2 Waveforms')
axes[0].set_xlabel('Time [ns]')
axes[0].set_ylabel('ADC Value')

# CH3
for i, record in enumerate(waveforms_ch3[:10]):
    wave = record['wave']
    x = np.arange(len(wave)) * 2.0
    axes[1].plot(x, wave, alpha=0.6)
axes[1].set_title('CH3 Waveforms')
axes[1].set_xlabel('Time [ns]')
axes[1].set_ylabel('ADC Value')

plt.tight_layout()
plt.show()
```

### 分析基线分布

```python
# 加载大量事件以分析基线
waveforms = previewer.load_by_range(channel=2, start_event=0, end_event=1000)
features = previewer.compute_features(waveforms)

# 绘制基线分布
plt.figure(figsize=(10, 6))
plt.hist(features['baselines'], bins=50, alpha=0.7, edgecolor='black')
plt.xlabel('Baseline [ADC]')
plt.ylabel('Count')
plt.title('Baseline Distribution (CH2, 1000 events)')
plt.axvline(features['baselines'].mean(), color='r', linestyle='--',
            label=f"Mean: {features['baselines'].mean():.2f}")
plt.axvline(features['baselines'].median(), color='g', linestyle='--',
            label=f"Median: {features['baselines'].median():.2f}")
plt.legend()
plt.grid(True, alpha=0.3)
plt.show()

print(f"基线统计:")
print(f"  均值: {features['baselines'].mean():.2f} ADC")
print(f"  标准差: {features['baselines'].std():.2f} ADC")
print(f"  范围: [{features['baselines'].min():.2f}, {features['baselines'].max():.2f}]")
```

### 确定合适的阈值

```python
# 加载数据并计算峰值分布
waveforms = previewer.load_by_range(channel=2, start_event=0, end_event=500)
features = previewer.compute_features(waveforms)

# 绘制峰值分布
plt.figure(figsize=(10, 6))
plt.hist(features['peaks'], bins=100, alpha=0.7, edgecolor='black')
plt.xlabel('Peak Height [ADC]')
plt.ylabel('Count')
plt.title('Peak Distribution (CH2)')
plt.yscale('log')
plt.grid(True, alpha=0.3)

# 标记可能的阈值
suggested_threshold = features['peaks'].mean() - 2 * features['peaks'].std()
plt.axvline(suggested_threshold, color='r', linestyle='--',
            label=f'Suggested threshold: {suggested_threshold:.1f} ADC')
plt.legend()
plt.show()

print(f"峰值统计:")
print(f"  均值: {features['peaks'].mean():.2f} ADC")
print(f"  标准差: {features['peaks'].std():.2f} ADC")
print(f"  建议阈值（均值 - 2σ）: {suggested_threshold:.2f} ADC")
```

---

## API 参考

### WaveformPreviewer

#### 初始化参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `run_name` | str | - | 运行名称（必需） |
| `data_root` | str | "DAQ" | 数据根目录 |
| `n_channels` | int | 6 | 通道总数 |

#### 主要方法

##### `load_by_range(channel, start_event, end_event)`
按事件范围加载波形数据。

**参数**：
- `channel` (int): 通道号（0-based）
- `start_event` (int): 起始事件索引（包含）
- `end_event` (int): 结束事件索引（不包含）

**返回**：结构化数组 (ST_WAVEFORM_DTYPE)

---

##### `load_by_timestamp(channel, start_ts, end_ts)`
按时间戳范围加载波形数据。

**参数**：
- `channel` (int): 通道号
- `start_ts` (int): 起始时间戳（ps，包含）
- `end_ts` (int): 结束时间戳（ps，不包含）

**返回**：结构化数组 (ST_WAVEFORM_DTYPE)

---

##### `compute_features(waveforms, peaks_range=(40, 90), charge_range=(60, 400))`
计算波形特征。

**参数**：
- `waveforms` (ndarray): 结构化数组
- `peaks_range` (tuple): 峰值检测区间
- `charge_range` (tuple): 电荷积分区间

**返回**：字典，包含 'peaks', 'charges', 'peak_positions', 'baselines'

---

##### `plot_overlay(waveforms, annotate=True, **kwargs)`
叠加显示多个波形。

**参数**：
- `waveforms` (ndarray): 结构化数组
- `annotate` (bool): 是否标注特征
- `peaks_range` (tuple): 峰值检测区间
- `charge_range` (tuple): 电荷积分区间
- `figsize` (tuple): 图像大小
- `sampling_interval_ns` (float): 采样间隔（ns）

**返回**：Matplotlib Figure 对象

---

##### `plot_grid(waveforms, annotate=True, **kwargs)`
分格显示每个波形。

**参数**：
- `waveforms` (ndarray): 结构化数组
- `annotate` (bool): 是否标注特征
- `ncols` (int): 列数
- `figsize_per_plot` (tuple): 每个子图大小
- 其他参数同 `plot_overlay`

**返回**：Matplotlib Figure 对象

---

### preview_waveforms (便捷函数)

一行代码快速预览波形。

**参数**：
- `run_name` (str): 运行名称
- `channel` (int): 通道号
- `event_range` (tuple): 事件范围 (start, end)，与 timestamp_range 二选一
- `timestamp_range` (tuple): 时间戳范围 (start_ts, end_ts)
- `plot_mode` (str): 'overlay' 或 'grid'
- `annotate` (bool): 是否标注特征
- `save_path` (str): 保存路径（可选）
- `data_root` (str): 数据根目录
- `n_channels` (int): 通道总数

**返回**：Matplotlib Figure 对象

---

## 常见问题

### Q1: 如何知道某个通道有多少个事件？

可以加载一个大范围，然后查看返回数组的长度：

```python
# 尝试加载大量事件
waveforms = previewer.load_by_range(channel=2, start_event=0, end_event=1000000)
print(f"CH2 总事件数（至少）: {len(waveforms)}")
```

### Q2: 如何自定义峰值和积分区间？

所有绘图和特征计算函数都支持自定义参数：

```python
fig = previewer.plot_overlay(
    waveforms,
    peaks_range=(50, 100),      # 自定义峰值区间
    charge_range=(80, 500)      # 自定义积分区间
)
```

### Q3: 采样间隔如何设置？

默认采样间隔为 2 ns，可通过 `sampling_interval_ns` 参数修改：

```python
fig = previewer.plot_overlay(
    waveforms,
    sampling_interval_ns=1.0    # 1 ns 采样间隔
)
```

### Q4: 如何保存图像？

使用 Matplotlib 的标准方法：

```python
fig = previewer.plot_grid(waveforms)
fig.savefig('waveforms.png', dpi=300, bbox_inches='tight')
```

或使用便捷函数的 `save_path` 参数：

```python
preview_waveforms(
    run_name="...",
    channel=2,
    event_range=(0, 10),
    save_path='preview.png'
)
```

### Q5: 为什么我的通道没有数据？

检查以下几点：
1. 确认该通道的原始文件存在于 `DAQ/<run_name>/RAW/` 目录
2. 检查 `n_channels` 参数是否正确
3. 确认通道号从 0 开始计数

```python
# 检查可用文件
previewer._get_raw_files()
```

---

## 更多示例

完整的测试代码请参考：
- `/mnt/data/Run3/49V_newframe.ipynb` - Notebook 中的完整测试
- `/mnt/data/Run3/WaveformAnalysis/waveform_analysis/utils/preview.py` - 源代码

---

## 技术细节

### 数据结构

加载的波形数据使用 `ST_WAVEFORM_DTYPE` 结构化数组：

```python
ST_WAVEFORM_DTYPE = [
    ('baseline', 'f8'),         # 基线值（float64）
    ('timestamp', 'i8'),        # 时间戳，单位 ps（int64）
    ('event_length', 'i8'),     # 事件长度（int64）
    ('channel', 'i2'),          # 通道号（int16）
    ('wave', 'f4', (800,))      # 波形数据，800个采样点（float32）
]
```

### 特征计算算法

- **基线**：前40个采样点（索引 7-46）的均值
- **峰值**：峰值区间内 `(baseline - wave)` 的最大值（假设负脉冲）
- **峰值位置**：峰值所在的采样点索引
- **电荷**：积分区间内 `sum(baseline - wave)`

---

## 许可证

本功能是 WaveformAnalysis 包的一部分，遵循相同的许可证。
