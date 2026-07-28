# 位置重建可视化模块

基于 `xihu_fast_analysis` 优化并集成到 WaveformAnalysis 的交互式可视化工具。

## 功能特性

### 1. 交互式 3D 仪表板（推荐）
- **技术栈**: Plotly.js（纯前端，无需后端服务器）
- **输出格式**: 独立 HTML 文件，可在浏览器直接打开
- **交互功能**:
  - XY 平面投影（带 PMT 布局和探测器边界）
  - XZ 深度剖面图
  - 3D WebGL 立体事件分布
  - 实时 S1/S2 能量过滤器
  - 空间坐标直方图（X, Y, Z）
  - 能量谱（S1, S2）和 R² 均匀性检测
  - 事件悬停信息显示

### 2. 静态图表（matplotlib）
- 2x2 布局的位置分布图
- XY 平面分布（按 S2 着色）
- Z 坐标直方图
- S1-S2 散点图（按径向位置着色）
- 径向分布直方图

## 使用方法

### 命令行工具

```bash
# 1. 仅导出数据（CSV 格式）
python examples/export_positions_for_visualization.py \
    --run-id run_001 \
    --output output/

# 2. 生成交互式 HTML 仪表板（推荐）
python examples/export_positions_for_visualization.py \
    --run-id run_001 \
    --output output/ \
    --dashboard

# 3. 生成静态图（PNG）
python examples/export_positions_for_visualization.py \
    --run-id run_001 \
    --output output/ \
    --plot

# 4. 同时生成所有可视化
python examples/export_positions_for_visualization.py \
    --run-id run_001 \
    --output output/ \
    --dashboard \
    --plot \
    --format parquet
```

### Python API

```python
from waveform_analysis import Context, render_position_dashboard
from waveform_analysis.utils.s1_s2_pair_accessor import S1S2PairAccessor
from waveform_analysis.core.hardware.geometry import load_fallback_layout
import pandas as pd

# 1. 初始化 Context
ctx = Context(config={"data_root": "/path/to/data"})

# 2. 获取位置数据
accessor = S1S2PairAccessor(ctx, "run_001", selected_only=True)
positions = accessor.positions()
pairs = accessor.pairs

# 3. 准备 DataFrame
df = pd.DataFrame({
    'x_rec': positions['x'],
    'y_rec': positions['y'],
    'z_rec': positions['z'],
    's1_area': pairs['s1_area'],
    's2_area': pairs['s2_area'],
    's2_peak_id': pairs['s2_peak_id'],
    'drift_time_ns': pairs['drift_time_ns'],
})

# 4. 加载 PMT 布局
layout = load_fallback_layout()  # 或从配置加载

# 5. 生成交互式仪表板
render_position_dashboard(
    df=df,
    layout=layout,
    run_id="run_001",
    output_dir="output",
    detector_radius_mm=62.5,
)
```

### Jupyter Notebook 集成

```python
from waveform_analysis import render_position_dashboard
from IPython.display import HTML

# 返回 HTML 字符串用于内嵌显示
html_content = render_position_dashboard(
    df=df,
    layout=layout,
    run_id="run_001",
    return_html=True,  # 关键参数
)

# 在 Jupyter 中显示
display(HTML(html_content))
```

## 输出文件

### 交互式仪表板
- 文件名: `run_{run_id}_position_dashboard.html`
- 位置: `{output_dir}/run_{run_id}_position_dashboard.html`
- 大小: 通常 < 5 MB（取决于事件数量）
- 特点: 完全自包含，可直接分享

### 静态图
- 文件名: `run_{run_id}_position_distribution.png`
- 分辨率: 150 DPI
- 尺寸: 14×12 英寸

### 数据文件
- CSV: `run_{run_id}_positions.csv`
- Parquet: `run_{run_id}_positions.parquet`
- Pickle: `run_{run_id}_positions.pkl`

## 数据要求

### 必需字段
- `x_rec`, `y_rec`, `z_rec`: 重建坐标 (mm)
- `s1_area`, `s2_area`: S1/S2 信号面积 (PE)
- `s2_peak_id`: S2 peak ID（用于悬停信息）

### 可选字段
- `drift_time_ns`: 漂移时间（用于详细信息显示）
- `edge_event`: 边缘事件标记（用于高亮显示）

## 与 xihu_fast_analysis 的区别

### 优势
1. **解耦依赖**: 不再需要硬编码路径或外部工具
2. **统一数据结构**: 直接使用 WaveformAnalysis 的 `PmtLayout`
3. **模块化设计**: 可以独立导入使用
4. **增强错误处理**: 完整的数据验证和异常处理

### 兼容性
- 内部使用 `dashboard_original.py` 作为备选实现
- 如果找不到模板文件，自动回退到原始实现
- API 完全向后兼容

## 配置选项

### 探测器参数
```python
render_position_dashboard(
    df=df,
    layout=layout,
    detector_radius_mm=62.5,  # 探测器有效半径
)
```

### PMT 布局来源
1. **全局配置**: `detector_geometry` 字段
2. **runinfo.json**: 从数据目录自动加载
3. **Fallback**: 7-PMT 六角密排配置

## 性能优化

### 大数据集处理
- **自动降采样**: 超过 25,000 个事件时自动降采样散点图
- **预计算特征**: 在后端计算 log10、r² 等特征
- **WebGL 渲染**: 使用 `scattergl` 模式加速渲染

### 推荐配置
- **< 10k 事件**: 全功能无限制
- **10k-50k 事件**: 自动降采样，直方图使用全数据
- **> 50k 事件**: 考虑先导出 CSV，使用外部工具分析

## 故障排查

### 常见问题

**Q: ImportError: cannot import name 'render_position_dashboard'**
```bash
# 解决方案：确保可视化模块存在
ls waveform_analysis/visualization/
# 应该看到: __init__.py, dashboard.py
```

**Q: 仪表板无法显示**
- 检查浏览器控制台错误
- 确保 Plotly.js CDN 可访问
- 尝试使用本地 Plotly.js 副本

**Q: PMT 布局错误**
```python
# 检查布局来源
layout = load_fallback_layout()
print(f"Layout source: {layout.source}")
print(f"PMT count: {len(layout.entries)}")
```

## 未来计划

- [ ] 支持自定义配色方案
- [ ] 添加更多统计图表（能量分辨率、位置分辨率）
- [ ] 支持多 run 对比
- [ ] 集成机器学习模型的预测结果可视化
- [ ] 支持导出高分辨率矢量图（SVG/PDF）

## 参考

- 原始工具: `xihu_fast_analysis/dashboard.py`
- Plotly.js 文档: https://plotly.com/javascript/
- WaveformAnalysis 文档: `docs/`
