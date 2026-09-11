# 二维密度分布可视化更新

## 📊 更新内容

将原有的一维直方图改为**二维密度热力图**，更直观地展示数据分布特征。

---

## 🎯 新增功能

### 1. **静态图（matplotlib）- 2×3 布局**

#### 主要图表（2D 热力图）：
1. **XY 二维密度图**
   - 类型：`hist2d`（2D 直方图热力图）
   - 显示：事件在 XY 平面的密度分布
   - 配色：YlOrRd（黄-橙-红）
   - 特点：叠加探测器边界圆

2. **R²-Z 二维密度图**
   - 类型：`hist2d`
   - 显示：径向位置（R²）与深度（Z）的关联
   - 配色：Viridis
   - 特点：标注 R² 边界线（探测器半径²）

3. **S1-S2 二维密度图**
   - 类型：`hist2d`（对数坐标）
   - 显示：S1 和 S2 信号的关联分布
   - 配色：Plasma
   - 特点：使用对数 bins 和归一化

#### 辅助图表（保留参考）：
4. **XY 散点图**（按 S2 着色）
5. **Z 一维分布**（直方图 + 统计信息）
6. **R² 一维分布**（直方图 + 边界标记）

### 2. **交互式 2D 仪表板（Plotly.js）**

#### 主要特性：
- **XY 密度热力图**：`histogram2d` 类型，50×50 bins
- **R²-Z 密度热力图**：显示径向-深度关联
- **S1-S2 密度热力图**：对数坐标，40×40 bins
- **3D 散点图**：保留三维视角

#### 交互功能：
- 实时 S1/S2 过滤器
- 事件计数实时更新
- 缩放、平移、旋转
- XY/XZ/YZ、R²-Z、R-cos(θ) 和 S1-S2 的二维 histogram
- Plotly 框选联动、清除选择和大数据集选择保护
- Plotly CDN 加载失败提示和响应式布局

`render_position_dashboard_2d` 是当前唯一推荐的二维仪表板入口。
旧的 `render_position_dashboard_with_2d_hist` 和 `--dashboard-2d-hist`
仍可兼容调用，但已经弃用，输出统一为 `run_{run_id}_position_dashboard_2d.html`。

---

## 🚀 使用方法

### 命令行使用

```bash
# 1. 生成静态 2D 密度图（推荐）
python examples/export_positions_for_visualization.py \
    --run-id run_001 \
    --output output/ \
    --plot

# 2. 生成增强版交互式 2D 密度仪表板（推荐）
python examples/export_positions_for_visualization.py \
    --run-id run_001 \
    --output output/ \
    --dashboard-2d

# 3. 同时生成所有可视化
python examples/export_positions_for_visualization.py \
    --run-id run_001 \
    --output output/ \
    --plot \
    --dashboard-2d \
    --format csv
```

### Python API

```python
from waveform_analysis import render_position_dashboard_2d
from waveform_analysis.core.hardware.geometry import load_fallback_layout
import pandas as pd

# 准备数据
df = pd.DataFrame({
    'x_rec': [...],
    'y_rec': [...],
    'z_rec': [...],
    's1_area': [...],
    's2_area': [...],
    's2_peak_id': [...],
})

# 生成 2D 密度仪表板
layout = load_fallback_layout()
render_position_dashboard_2d(
    df=df,
    layout=layout,
    run_id="run_001",
    output_dir="output",
)
```

---

## 📂 输出文件

### 静态图
- **文件名**: `run_{run_id}_position_2d_distributions.png`
- **尺寸**: 18×12 英寸（2×3 布局）
- **分辨率**: 150 DPI
- **内容**: 3 个 2D 热力图 + 3 个参考图

### 交互式仪表板
- **文件名**: `run_{run_id}_position_dashboard_2d.html`
- **大小**: 随事件数量变化
- **特点**: 纯前端，无需服务器；支持二维 histogram 和框选联动

---

## 🎨 可视化对比

### 改进前（一维分布）
```
[XY 散点] [Z 直方图]
[S1-S2]   [R 直方图]
```
- ❌ 无法直观看出 XY 平面的密度聚集
- ❌ 无法看出 R²-Z 的关联
- ❌ S1-S2 散点图点太多时重叠严重

### 改进后（二维分布）
```
[XY 密度热力图]     [R²-Z 密度热力图]
[S1-S2 密度热力图]  [XY 散点（参考）]
[Z 分布（参考）]    [R² 分布（参考）]
```
- ✅ XY 密度热力图清晰显示事件聚集区域
- ✅ R²-Z 热力图揭示径向-深度关联
- ✅ S1-S2 热力图避免点重叠，清晰显示能量关联
- ✅ 保留一维分布作为参考

---

## 🔍 二维分布的物理意义

### 1. XY 密度热力图
**用途**: 检测位置重建的空间均匀性
- **聚集区域**: 可能表示探测器响应不均匀
- **边缘效应**: 检查边界附近的事件密度
- **对称性**: 验证探测器的几何对称性

### 2. R²-Z 密度热力图
**用途**: 检验径向-深度关联
- **理想情况**: 均匀分布（无明显关联）
- **异常模式**:
  - 径向依赖：边缘事件深度偏差
  - 分层结构：可能的系统偏差

### 3. S1-S2 密度热力图
**用途**: 粒子类型分类和能量标定
- **主带（band）**: 电子反冲事件
- **低 S2/S1 区域**: 核反冲事件
- **异常点**: 可能的本底或探测器效应

---

## 📊 技术细节

### 静态图（matplotlib）

#### 2D 直方图参数
```python
hist2d(
    x, y,
    bins=50,              # XY: 50×50 bins
    cmap='YlOrRd',        # 配色方案
    range=[...],          # 数据范围
    cmin=1,               # 最小计数（避免零值）
)
```

#### S1-S2 对数 bins
```python
s1_log_bins = np.logspace(
    np.log10(s1_min),
    np.log10(s1_max),
    50
)
```

### 交互式仪表板（Plotly.js）

#### histogram2d 配置
```javascript
{
    type: 'histogram2d',
    x: [...],
    y: [...],
    colorscale: 'YlOrRd',
    nbinsx: 50,
    nbinsy: 50,
    colorbar: {title: 'Counts'}
}
```

---

## 🎯 推荐工作流程

### 快速检查（静态图）
```bash
python examples/export_positions_for_visualization.py \
    --run-id run_001 \
    --output output/ \
    --plot
```
- 快速生成 PNG 图片
- 适合论文/报告
- 一次性查看所有分布

### 详细分析（交互式）
```bash
python examples/export_positions_for_visualization.py \
    --run-id run_001 \
    --output output/ \
    --dashboard-2d
```
- 实时过滤和缩放
- 探索数据细节
- 适合数据质量检查

### 完整导出（所有格式）
```bash
python examples/export_positions_for_visualization.py \
    --run-id run_001 \
    --output output/ \
    --plot \
    --dashboard \
    --dashboard-2d \
    --format parquet
```

---

## 🐛 故障排查

### 问题：热力图显示空白
**原因**: 数据范围设置不当或数据为 NaN
**解决**: 检查数据有效性
```python
print(f"X range: [{df['x_rec'].min()}, {df['x_rec'].max()}]")
print(f"Y range: [{df['y_rec'].min()}, {df['y_rec'].max()}]")
print(f"NaN count: {df.isna().sum()}")
```

### 问题：S1-S2 热力图颜色不均
**原因**: 对数坐标下 bins 分布不均
**解决**: 调整 bins 数量或使用 `LogNorm()`
```python
norm=LogNorm()  # 对数归一化
```

### 问题：图片太大/太小
**解决**: 调整 figsize 和 DPI
```python
fig = plt.figure(figsize=(18, 12))  # 尺寸
plt.savefig(..., dpi=150)           # 分辨率
```

---

## 📈 性能考虑

### 数据量 vs 性能

| 事件数 | 静态图耗时 | 交互式加载 | 建议 |
|--------|-----------|-----------|------|
| < 1k   | < 1s      | 即时      | 全功能 |
| 1k-10k | 1-3s      | < 2s      | 推荐 |
| 10k-50k| 3-10s     | 2-5s      | 考虑降采样 |
| > 50k  | > 10s     | > 5s      | 分批处理 |

### 优化建议
1. **大数据集**: 使用 Parquet 格式存储
2. **热力图**: bins 数量不要超过 100
3. **交互式**: 考虑预过滤数据

---

## 🔄 版本兼容

### 向后兼容
- 原始 `--dashboard` 选项保留
- 新增并统一 `--dashboard-2d` 选项
- `--dashboard-2d-hist` 保留为弃用兼容别名
- 静态图自动切换到 2D 密度图

### 迁移指南
```bash
# 旧版本（一维直方图）
--plot  # 已更新为 2D 密度图

# 新版本（推荐）
--plot           # 静态 2D 密度图
--dashboard-2d   # 交互式 2D 密度图
```

---

**更新日期**: 2026-08-26
**作者**: Claude Code (Opus 4.8)
**状态**: ✅ 已集成
