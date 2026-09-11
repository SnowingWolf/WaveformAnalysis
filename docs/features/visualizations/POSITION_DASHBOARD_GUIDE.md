# 位置二维 Dashboard

**导航**: [文档中心](../../README.md) > [功能特性](../README.md) > 位置二维 Dashboard

位置二维 Dashboard 用于检查位置重建结果、S1/S2 分布和 waveform morphology 相关特征。它输出一个独立 HTML 页面，不需要启动后端服务。

## 直接使用 Python API

如果已经有位置重建结果的 `DataFrame`，不需要创建 `Context`：

```python
import pandas as pd

from waveform_analysis import render_position_dashboard_2d
from waveform_analysis.core.hardware.geometry import load_fallback_layout

df = pd.DataFrame({
    "x_rec": [1.2, -3.4],
    "y_rec": [5.6, 2.1],
    "z_rec": [-40.0, -55.0],
    "s1_area": [120.0, 180.0],
    "s2_area": [1500.0, 2400.0],
    "s2_peak_id": [101, 102],
})

output = render_position_dashboard_2d(
    df=df,
    layout=load_fallback_layout(),
    run_id="run_001",
    output_dir="output",
)
print(output)
```

## `DataFrame` 输入字段

必需字段：

| 字段 | 含义 | 要求 |
|---|---|---|
| `x_rec` | X 坐标 | 可转换为数值 |
| `y_rec` | Y 坐标 | 可转换为数值 |
| `z_rec` | Z 坐标 | 可转换为数值 |
| `s1_area` | S1 面积 | 至少一个正的有限值 |
| `s2_area` | S2 面积 | 至少一个正的有限值 |
| `s2_peak_id` | S2 peak 标识 | 用于追踪事件 |

可选字段：

```text
drift_time_ns
width
rise_time_10_50
s1_width
s2_width
s1_peak_width
s2_peak_width
s1_rise_time_10_50
s2_rise_time_10_50
```

缺失的可选字段不会阻止位置图生成，但对应的特征相关性图没有有效点。`r2_rec`、`r_rec`、`theta_rec`、`cos_theta_rec`、`log10_s1`、`log10_s2` 和 `_row_id` 会由函数内部自动计算，不需要手动添加。

函数会复制输入数据，不会修改原始 `DataFrame`。包含 `NaN` 或无穷值的记录会被安全序列化为 `null`，并由相应前端图表忽略；如果必需列完全没有有限值，函数会抛出 `ValueError`。

## 命令行方式

当需要从指定 run 自动导出位置数据时，使用示例脚本：

```bash
python examples/export_positions_for_visualization.py \
  --run-id run_001 \
  --data-root /path/to/data \
  --output output \
  --dashboard-2d
```

此时脚本内部会使用 `Context` 和 `S1S2PairAccessor` 准备 `DataFrame`；这是 CLI 的数据获取过程，不是 `render_position_dashboard_2d` 的输入要求。

## 输出与交互

默认输出：

```text
output/run_{run_id}_position_dashboard_2d.html
```

设置 `return_html=True` 时，函数直接返回 HTML 字符串，不写文件。

页面包含：

- XY、XZ、YZ 二维 histogram；
- R²-Z、R-cos(θ)、S1-S2 分布；
- S1/S2 面积筛选；
- histogram bin 数调整；
- XY/XZ/二维图框选联动和清除选择；
- 特征宽度/上升时间相关性图；
- 3D 位置图。

HTML 内嵌事件数据，但 Plotly.js 从 CDN 加载。打开页面时需要网络访问 CDN；如果加载失败，页面会显示错误提示。

## 兼容入口

新代码统一使用：

```python
render_position_dashboard_2d(...)
```

旧的 `render_position_dashboard_with_2d_hist` 和 `--dashboard-2d-hist` 仍保留用于兼容旧脚本，但已经弃用。两者最终使用同一套实现，建议迁移到 canonical 入口。
