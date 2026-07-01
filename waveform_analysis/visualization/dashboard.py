"""交互式 3D 位置重建仪表板

基于 Plotly.js 的纯前端交互式可视化工具，无需后端服务器。

改编自 xihu_fast_analysis/dashboard.py，优化如下：
- 解耦外部依赖，使用 WaveformAnalysis 的 PmtLayout
- 支持独立 HTML 输出和 Jupyter 内嵌显示
- 增强数据验证和错误处理

Author: Claude Code (adapted from xihu_fast_analysis)
Version: 1.0.0
"""

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from waveform_analysis.core.hardware.geometry import PmtLayout


def render_position_dashboard(
    df: pd.DataFrame,
    layout: PmtLayout,
    run_id: str = "unknown",
    output_dir: str = "output",
    detector_radius_mm: float = 62.5,
    return_html: bool = False,
) -> str | None:
    """生成交互式 3D 位置重建仪表板

    功能特性：
    - XY 平面投影（带 PMT 布局和探测器边界）
    - XZ 深度剖面图
    - 空间坐标 1D 直方图 (X, Y, Z)
    - 能量谱 (S1, S2) 和 R² 均匀性检测
    - 3D WebGL 立体事件分布
    - 实时过滤器（S1/S2 范围调节）

    Args:
        df: 位置数据 DataFrame，必需字段：
            - x_rec, y_rec, z_rec: 重建坐标 (mm)
            - s1_area, s2_area: S1/S2 信号面积 (PE)
            - s2_peak_id: S2 peak ID（用于悬停信息）
            - drift_time_ns: 漂移时间（可选）
        layout: PMT 几何布局对象
        run_id: 运行 ID
        output_dir: 输出目录
        detector_radius_mm: 探测器有效半径 (mm)
        return_html: 是否返回 HTML 字符串（用于 Jupyter）

    Returns:
        如果 return_html=True，返回 HTML 字符串；否则返回输出文件路径

    Example:
        >>> from waveform_analysis.core.context import Context
        >>> from waveform_analysis.utils.s1_s2_pair_accessor import S1S2PairAccessor
        >>> from waveform_analysis.visualization import render_position_dashboard
        >>>
        >>> ctx = Context()
        >>> accessor = S1S2PairAccessor(ctx, "run_001", selected_only=True)
        >>> positions = accessor.get_positions()
        >>> pairs = accessor.pairs
        >>>
        >>> df = pd.DataFrame({
        ...     'x_rec': positions['x'],
        ...     'y_rec': positions['y'],
        ...     'z_rec': positions['z'],
        ...     's1_area': pairs['s1_area'],
        ...     's2_area': pairs['s2_area'],
        ...     's2_peak_id': pairs['s2_peak_id'],
        ... })
        >>>
        >>> layout = ctx._load_pmt_layout()
        >>> render_position_dashboard(df, layout, run_id="run_001")
    """
    # 数据验证
    required_cols = ["x_rec", "y_rec", "z_rec", "s1_area", "s2_area", "s2_peak_id"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"DataFrame 缺少必需字段: {missing_cols}")

    if len(df) == 0:
        raise ValueError("DataFrame 为空，无法生成仪表板")

    # 准备数据
    df_clean = df[required_cols].copy()

    # 添加 drift_time_ns（如果存在）
    if "drift_time_ns" in df.columns:
        df_clean["drift_time_ns"] = df["drift_time_ns"]
    else:
        df_clean["drift_time_ns"] = 0.0

    # 预计算特征（避免前端计算过载）
    df_clean["r2_rec"] = df_clean["x_rec"] ** 2 + df_clean["y_rec"] ** 2
    df_clean["log10_s1"] = np.log10(df_clean["s1_area"].clip(lower=1.0))
    df_clean["log10_s2"] = np.log10(df_clean["s2_area"].clip(lower=1.0))

    # 序列化数据为 JSON
    json_data = json.dumps(df_clean.to_dict(orient="records"))

    # 计算数据范围
    z_min = float(df_clean["z_rec"].min())
    z_max = float(df_clean["z_rec"].max())
    s1_min_raw = float(max(df_clean["s1_area"].min(), 1.0))
    s1_max_raw = float(df_clean["s1_area"].max())
    s2_min_raw = float(max(df_clean["s2_area"].min(), 1.0))
    s2_max_raw = float(df_clean["s2_area"].max())

    # 序列化 PMT 布局
    pmt_list = []
    for entry in layout.entries:
        pmt_list.append({
            "pmt_no": entry.pmt_no,
            "pmt_id": entry.pmt_id,
            "x_mm": entry.x_mm,
            "y_mm": entry.y_mm,
            "gain": entry.gain,
        })
    pmt_config_json = json.dumps(pmt_list)

    # 读取 HTML 模板
    template_path = Path(__file__).parent / "dashboard_template.html"

    if not template_path.exists():
        # 如果模板文件不存在，使用原始实现的简化版
        from .dashboard_original import render_instant_html_dashboard as original_render

        # 将 WaveformAnalysis 的 PmtLayout 转换为 xihu_fast_analysis 格式
        class CompatLayout:
            def __init__(self, wf_layout):
                self.entries = wf_layout.entries

        compat_layout = CompatLayout(layout)

        # 调用原始函数
        return original_render(
            df=df_clean,
            layout=compat_layout,
            r_tpc=detector_radius_mm,
            run_id=run_id,
            output_dir=output_dir,
        )

    # 使用模板文件
    with open(template_path, encoding="utf-8") as f:
        html_template = f.read()

    # 替换模板变量
    html_content = html_template.format(
        run_id=run_id,
        json_data=json_data,
        pmt_config_json=pmt_config_json,
        detector_radius_mm=detector_radius_mm,
        z_min=z_min,
        z_max=z_max,
        s1_min_raw=f"{s1_min_raw:.1f}",
        s1_max_raw=f"{s1_max_raw:.1f}",
        s2_min_raw=f"{s2_min_raw:.1f}",
        s2_max_raw=f"{s2_max_raw:.1f}",
        s1_min_log=f"{np.log10(s1_min_raw):.4f}",
        s1_max_log=f"{np.log10(s1_max_raw):.4f}",
        s2_min_log=f"{np.log10(s2_min_raw):.4f}",
        s2_max_log=f"{np.log10(s2_max_raw):.4f}",
    )

    if return_html:
        return html_content

    # 保存为独立 HTML 文件
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    output_file = output_dir_path / f"run_{run_id}_position_dashboard.html"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[✓] 交互式仪表板已保存至: {output_file}")
    return str(output_file)
