"""优化的交互式仪表板 - 重点展示二维分布

相比原始版本的改进：
1. 将一维直方图替换为二维热力图
2. 新增 XY 密度热力图
3. 新增 R²-Z 二维分布
4. S1-S2 改为二维热力图
"""

import json
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from waveform_analysis.core.hardware.geometry import PmtLayout


def render_position_dashboard_2d(
    df: pd.DataFrame,
    layout: PmtLayout,
    run_id: str = "unknown",
    output_dir: str = "output",
    detector_radius_mm: float = 62.5,
    return_html: bool = False,
) -> str | None:
    """生成交互式 2D 密度仪表板

    重点展示：
    - XY 二维密度热力图
    - R²-Z 二维密度热力图
    - S1-S2 二维密度热力图

    Args:
        df: 位置数据 DataFrame
        layout: PMT 几何布局对象
        run_id: 运行 ID
        output_dir: 输出目录
        detector_radius_mm: 探测器有效半径 (mm)
        return_html: 是否返回 HTML 字符串

    Returns:
        输出文件路径或 HTML 字符串
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

    # 预计算特征
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
    r2_max = float(df_clean["r2_rec"].max())

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

    # 生成 HTML（使用简化模板，重点展示 2D 热力图）
    html_content = _generate_2d_dashboard_html(
        json_data=json_data,
        pmt_config_json=pmt_config_json,
        detector_radius_mm=detector_radius_mm,
        z_min=z_min,
        z_max=z_max,
        s1_min_raw=s1_min_raw,
        s1_max_raw=s1_max_raw,
        s2_min_raw=s2_min_raw,
        s2_max_raw=s2_max_raw,
        r2_max=r2_max,
        run_id=run_id,
    )

    if return_html:
        return html_content

    # 保存为独立 HTML 文件
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    output_file = output_dir_path / f"run_{run_id}_position_dashboard_2d.html"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[✓] 2D 密度仪表板已保存至: {output_file}")
    return str(output_file)


def _generate_2d_dashboard_html(
    json_data: str,
    pmt_config_json: str,
    detector_radius_mm: float,
    z_min: float,
    z_max: float,
    s1_min_raw: float,
    s1_max_raw: float,
    s2_min_raw: float,
    s2_max_raw: float,
    r2_max: float,
    run_id: str,
) -> str:
    """生成 2D 密度仪表板 HTML 内容"""

    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Run {run_id} - 2D Density Dashboard</title>
    <style>
        body {{
            background-color: #f7fafc;
            margin: 0;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }}
        #dashboard {{
            background: #fdfdfd;
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            max-width: 1600px;
            margin: 10px auto;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
        }}
        .plot-container {{
            border: 1px solid #edf2f7;
            border-radius: 8px;
            background: #fff;
            margin-bottom: 20px;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div id="dashboard">
        <h1 style="text-align:center; color:#2d3748; margin-bottom:10px;">Run {run_id} - 2D Density Distributions</h1>
        <p style="text-align:center; color:#718096; margin-bottom:30px;">交互式二维密度热力图 | Total Events: {len(json.loads(json_data))}</p>

        <!-- Loading Spinner -->
        <div id="plotly-loader" style="position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(255,255,255,0.95); z-index:9999; display: flex; flex-direction:column; justify-content:center; align-items:center; transition: opacity 0.3s ease;">
            <div style="border: 4px solid #f3f3f3; border-top: 4px solid #3182ce; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin-bottom:15px;"></div>
            <div style="color: #2d3748; font-weight:bold; font-size:16px;">正在加载 Plotly.js...</div>
        </div>

        <!-- 控制面板 -->
        <div style="background: #ffffff; padding: 15px; border-radius: 8px; border: 1px solid #edf2f7; margin-bottom: 20px;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div>
                    <h4 style="margin: 0 0 10px 0; color: #2d3748; font-size: 14px;">S1 Area Filter (PE)</h4>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 11px; width: 40px; color:#718096;">Min:</span>
                        <input type="number" id="s1-min" value="{s1_min_raw:.1f}" style="width: 100px; font-size:11px; padding: 4px; border: 1px solid #cbd5e0; border-radius: 4px;">
                        <span style="font-size: 11px; width: 40px; color:#718096;">Max:</span>
                        <input type="number" id="s1-max" value="{s1_max_raw:.1f}" style="width: 100px; font-size:11px; padding: 4px; border: 1px solid #cbd5e0; border-radius: 4px;">
                        <button id="btn-update" style="padding: 4px 12px; background: #3182ce; color: white; border: none; border-radius: 4px; cursor: pointer; font-size:11px;">Update</button>
                    </div>
                </div>
                <div>
                    <h4 style="margin: 0 0 10px 0; color: #2d3748; font-size: 14px;">S2 Area Filter (PE)</h4>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 11px; width: 40px; color:#718096;">Min:</span>
                        <input type="number" id="s2-min" value="{s2_min_raw:.1f}" style="width: 100px; font-size:11px; padding: 4px; border: 1px solid #cbd5e0; border-radius: 4px;">
                        <span style="font-size: 11px; width: 40px; color:#718096;">Max:</span>
                        <input type="number" id="s2-max" value="{s2_max_raw:.1f}" style="width: 100px; font-size:11px; padding: 4px; border: 1px solid #cbd5e0; border-radius: 4px;">
                        <span id="event-count" style="margin-left:10px; font-size:12px; color:#2b6cb0; font-weight:bold;"></span>
                    </div>
                </div>
            </div>
        </div>

        <!-- 2D 热力图面板 -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
            <div id="plot-xy-density" class="plot-container" style="height: 450px;"></div>
            <div id="plot-r2z-density" class="plot-container" style="height: 450px;"></div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
            <div id="plot-s1s2-density" class="plot-container" style="height: 450px;"></div>
            <div id="plot-3d" class="plot-container" style="height: 450px;"></div>
        </div>

        <script>
        (function() {{
            function loadScript(url, callback) {{
                if (window.Plotly) {{ callback(); return; }}
                const script = document.createElement("script");
                script.type = "text/javascript";
                script.src = url;
                script.onload = callback;
                document.head.appendChild(script);
            }}

            loadScript("https://cdn.plot.ly/plotly-2.24.1.min.js", function() {{
                document.getElementById("plotly-loader").style.display = "none";
                initializeDashboard();
            }});

            function initializeDashboard() {{
                const rawData = {json_data};
                const pmts = {pmt_config_json};
                const r_tpc = {detector_radius_mm};
                const zMin = {z_min};
                const zMax = {z_max};

                function updatePlots() {{
                    const s1Min = parseFloat(document.getElementById('s1-min').value);
                    const s1Max = parseFloat(document.getElementById('s1-max').value);
                    const s2Min = parseFloat(document.getElementById('s2-min').value);
                    const s2Max = parseFloat(document.getElementById('s2-max').value);

                    const filtered = rawData.filter(d =>
                        d.s1_area >= s1Min && d.s1_area <= s1Max &&
                        d.s2_area >= s2Min && d.s2_area <= s2Max
                    );

                    document.getElementById('event-count').innerText = `${{filtered.length}} events`;

                    // === 1. XY 二维密度热力图 ===
                    Plotly.react('plot-xy-density', [{{
                        x: filtered.map(d => d.x_rec),
                        y: filtered.map(d => d.y_rec),
                        type: 'histogram2d',
                        colorscale: 'YlOrRd',
                        nbinsx: 50,
                        nbinsy: 50,
                        colorbar: {{ title: 'Counts' }}
                    }}], {{
                        title: 'XY Density Map',
                        xaxis: {{ title: 'X (mm)', range: [-r_tpc*1.2, r_tpc*1.2] }},
                        yaxis: {{ title: 'Y (mm)', range: [-r_tpc*1.2, r_tpc*1.2], scaleanchor: 'x' }},
                        margin: {{ l:60, r:10, t:40, b:50 }},
                        shapes: [{{ type: 'circle', xref: 'x', yref: 'y', x0: -r_tpc, y0: -r_tpc, x1: r_tpc, y1: r_tpc, line: {{ color: 'blue', width: 2, dash: 'dash' }} }}]
                    }}, {{ displayModeBar: false }});

                    // === 2. R²-Z 二维密度热力图 ===
                    Plotly.react('plot-r2z-density', [{{
                        x: filtered.map(d => d.r2_rec),
                        y: filtered.map(d => d.z_rec),
                        type: 'histogram2d',
                        colorscale: 'Viridis',
                        nbinsx: 50,
                        nbinsy: 50,
                        colorbar: {{ title: 'Counts' }}
                    }}], {{
                        title: 'R²-Z Density Map',
                        xaxis: {{ title: 'R² (mm²)' }},
                        yaxis: {{ title: 'Z (mm)' }},
                        margin: {{ l:60, r:10, t:40, b:50 }},
                        shapes: [{{ type: 'line', x0: r_tpc*r_tpc, x1: r_tpc*r_tpc, y0: zMin, y1: zMax, line: {{ color: 'red', width: 2, dash: 'dash' }} }}]
                    }}, {{ displayModeBar: false }});

                    // === 3. S1-S2 二维密度热力图 ===
                    Plotly.react('plot-s1s2-density', [{{
                        x: filtered.map(d => d.s1_area),
                        y: filtered.map(d => d.s2_area),
                        type: 'histogram2d',
                        colorscale: 'Plasma',
                        nbinsx: 40,
                        nbinsy: 40,
                        colorbar: {{ title: 'Counts' }}
                    }}], {{
                        title: 'S1-S2 Density Map',
                        xaxis: {{ title: 'S1 Area (PE)', type: 'log' }},
                        yaxis: {{ title: 'S2 Area (PE)', type: 'log' }},
                        margin: {{ l:60, r:10, t:40, b:50 }}
                    }}, {{ displayModeBar: false }});

                    // === 4. 3D 散点图 ===
                    Plotly.react('plot-3d', [{{
                        x: filtered.map(d => d.x_rec),
                        y: filtered.map(d => d.y_rec),
                        z: filtered.map(d => d.z_rec),
                        mode: 'markers',
                        type: 'scatter3d',
                        marker: {{
                            size: 2,
                            color: filtered.map(d => d.s2_area),
                            colorscale: 'Viridis',
                            opacity: 0.6,
                            colorbar: {{ title: 'S2 (PE)' }}
                        }}
                    }}], {{
                        title: '3D Distribution',
                        scene: {{
                            xaxis: {{ title: 'X (mm)' }},
                            yaxis: {{ title: 'Y (mm)' }},
                            zaxis: {{ title: 'Z (mm)' }}
                        }},
                        margin: {{ l:0, r:0, t:40, b:0 }}
                    }});
                }}

                document.getElementById('btn-update').addEventListener('click', updatePlots);
                updatePlots();
            }}
        }})();
        </script>
    </div>
</body>
</html>"""

    return html_template
