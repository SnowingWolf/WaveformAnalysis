"""交互式仪表板 - 2D histogram 版本

保持原始布局，将 6 个 1D 直方图改为 2D histogram：
1. XY 投影 + XZ 剖面（保留散点图）
2. 第一行 3 个 2D histogram: XY, XZ, YZ
3. 第二行 3 个 2D histogram: S1-S2, R²-Z, R-cos(theta)
4. 第三行 3 个特征 pair histogram: S1-Width, S2-Rise, Width-Rise
5. 3D 散点图
6. S1/S2 selection bar（滑动条）+ 框选回调
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from waveform_analysis.core.hardware.geometry import PmtLayout


def render_position_dashboard_with_2d_hist(
    df: pd.DataFrame,
    layout: PmtLayout,
    run_id: str = "unknown",
    output_dir: str = "output",
    detector_radius_mm: float = 62.5,
    return_html: bool = False,
) -> str | None:
    """生成交互式仪表板（原始布局 + 2D histogram）

    布局：
    - 上层：XY 散点图 + XZ 散点图
    - 中层第一行：XY、XZ、YZ 的 2D histogram
    - 中层第二行：S1-S2、R²-Z、R-cos(theta) 的 2D histogram
    - 中层第三行：width、rise_time_10_50 相关特征 pair histogram
    - 下层：3D 散点图
    - 控制面板：S1/S2 滑动条、bins 控件、框选回调

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
    optional_feature_cols = ["width", "rise_time_10_50"]
    for col in optional_feature_cols:
        if col in df.columns:
            df_clean[col] = df[col]
        else:
            df_clean[col] = None

    # 添加 drift_time_ns（如果存在）
    if "drift_time_ns" in df.columns:
        df_clean["drift_time_ns"] = df["drift_time_ns"]
    else:
        df_clean["drift_time_ns"] = 0.0

    # 预计算特征
    df_clean["r2_rec"] = df_clean["x_rec"] ** 2 + df_clean["y_rec"] ** 2
    df_clean["r_rec"] = np.sqrt(df_clean["r2_rec"])
    df_clean["theta_rec"] = np.arctan2(df_clean["y_rec"], df_clean["x_rec"])
    df_clean["cos_theta_rec"] = np.cos(df_clean["theta_rec"])
    df_clean["log10_s1"] = np.log10(df_clean["s1_area"].clip(lower=1.0))
    df_clean["log10_s2"] = np.log10(df_clean["s2_area"].clip(lower=1.0))

    # 序列化数据为 JSON
    json_data = json.dumps(df_clean.where(pd.notna(df_clean), None).to_dict(orient="records"))

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
        pmt_list.append(
            {
                "pmt_no": entry.pmt_no,
                "pmt_id": entry.pmt_id,
                "x_mm": entry.x_mm,
                "y_mm": entry.y_mm,
                "gain": entry.gain,
            }
        )
    pmt_config_json = json.dumps(pmt_list)

    # 生成 HTML
    html_content = _generate_dashboard_html(
        json_data=json_data,
        pmt_config_json=pmt_config_json,
        detector_radius_mm=detector_radius_mm,
        z_min=z_min,
        z_max=z_max,
        s1_min_raw=s1_min_raw,
        s1_max_raw=s1_max_raw,
        s2_min_raw=s2_min_raw,
        s2_max_raw=s2_max_raw,
        run_id=run_id,
    )

    if return_html:
        return html_content

    # 保存为独立 HTML 文件
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    output_file = output_dir_path / f"run_{run_id}_dashboard_2d_hist.html"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[✓] 交互式仪表板已保存至: {output_file}")
    return str(output_file)


def _generate_dashboard_html(
    json_data: str,
    pmt_config_json: str,
    detector_radius_mm: float,
    z_min: float,
    z_max: float,
    s1_min_raw: float,
    s1_max_raw: float,
    s2_min_raw: float,
    s2_max_raw: float,
    run_id: str,
) -> str:
    """生成仪表板 HTML 内容"""

    # 计算对数范围
    s1_min_log = np.log10(s1_min_raw)
    s1_max_log = np.log10(s1_max_raw)
    s2_min_log = np.log10(s2_min_raw)
    s2_max_log = np.log10(s2_max_raw)

    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Run {run_id} - Interactive Dashboard (2D Histograms)</title>
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
            margin-bottom: 15px;
        }}
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div id="dashboard">
        <h1 style="text-align:center; color:#2d3748; margin-bottom:10px;">Run {run_id} - Interactive Dashboard</h1>
        <p style="text-align:center; color:#718096; margin-bottom:20px;">
            <span id="event-count" style="background:#edf2f7; padding:4px 12px; border-radius:12px; color:#2b6cb0; font-weight:bold;">
                Loading...
            </span>
        </p>

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
                    <div style="margin-bottom: 8px;">
                        <span style="font-size: 11px; color:#718096;">Min (Log):</span>
                        <input type="range" id="s1-range-min" min="{s1_min_log:.4f}" max="{s1_max_log:.4f}" step="0.01" value="{s1_min_log:.4f}" style="width: 70%; cursor:pointer;">
                        <input type="number" id="s1-num-min" value="{s1_min_raw:.1f}" style="width: 80px; font-size:11px; padding: 2px; border: 1px solid #cbd5e0; border-radius: 4px;">
                        <span style="font-size: 11px; color:#a0aec0;">PE</span>
                    </div>
                    <div>
                        <span style="font-size: 11px; color:#718096;">Max (Log):</span>
                        <input type="range" id="s1-range-max" min="{s1_min_log:.4f}" max="{s1_max_log:.4f}" step="0.01" value="{s1_max_log:.4f}" style="width: 70%; cursor:pointer;">
                        <input type="number" id="s1-num-max" value="{s1_max_raw:.1f}" style="width: 80px; font-size:11px; padding: 2px; border: 1px solid #cbd5e0; border-radius: 4px;">
                        <span style="font-size: 11px; color:#a0aec0;">PE</span>
                    </div>
                </div>
                <div>
                    <h4 style="margin: 0 0 10px 0; color: #2d3748; font-size: 14px;">S2 Area Filter (PE)</h4>
                    <div style="margin-bottom: 8px;">
                        <span style="font-size: 11px; color:#718096;">Min (Log):</span>
                        <input type="range" id="s2-range-min" min="{s2_min_log:.4f}" max="{s2_max_log:.4f}" step="0.01" value="{s2_min_log:.4f}" style="width: 70%; cursor:pointer;">
                        <input type="number" id="s2-num-min" value="{s2_min_raw:.1f}" style="width: 80px; font-size:11px; padding: 2px; border: 1px solid #cbd5e0; border-radius: 4px;">
                        <span style="font-size: 11px; color:#a0aec0;">PE</span>
                    </div>
                    <div>
                        <span style="font-size: 11px; color:#718096;">Max (Log):</span>
                        <input type="range" id="s2-range-max" min="{s2_min_log:.4f}" max="{s2_max_log:.4f}" step="0.01" value="{s2_max_log:.4f}" style="width: 70%; cursor:pointer;">
                        <input type="number" id="s2-num-max" value="{s2_max_raw:.1f}" style="width: 80px; font-size:11px; padding: 2px; border: 1px solid #cbd5e0; border-radius: 4px;">
                        <span style="font-size: 11px; color:#a0aec0;">PE</span>
                    </div>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 12px; margin-top: 12px; padding-top: 12px; border-top: 1px solid #edf2f7;">
                <span style="font-size: 12px; color:#2d3748; font-weight: 600;">2D Histogram Bins</span>
                <input type="range" id="hist-bins-range" min="20" max="200" step="5" value="40" style="width: 220px; cursor:pointer;">
                <input type="number" id="hist-bins-num" min="20" max="200" step="5" value="40" style="width: 64px; font-size:11px; padding: 2px; border: 1px solid #cbd5e0; border-radius: 4px;">
                <button id="clear-selection" type="button" style="padding: 4px 10px; background: #edf2f7; color: #2d3748; border: 1px solid #cbd5e0; border-radius: 4px; cursor: pointer; font-size: 11px;">Clear Selection</button>
            </div>
        </div>

        <!-- 1. XY 投影与 XZ 剖面（散点图） -->
        <div style="display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 15px; margin-bottom: 15px;">
            <div id="plot-xy" class="plot-container" style="height: 380px;"></div>
            <div id="plot-xz" class="plot-container" style="height: 380px;"></div>
        </div>

        <!-- 2. 第一行 2D histograms: XY, XZ, YZ -->
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 15px;">
            <div id="hist-xy" class="plot-container" style="height: 280px;"></div>
            <div id="hist-xz" class="plot-container" style="height: 280px;"></div>
            <div id="hist-yz" class="plot-container" style="height: 280px;"></div>
        </div>

        <!-- 3. 第二行 2D histograms: S1-S2, R²-Z, R-cos(theta) -->
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 15px;">
            <div id="hist-s1s2" class="plot-container" style="height: 280px;"></div>
            <div id="hist-r2z" class="plot-container" style="height: 280px;"></div>
            <div id="hist-rtheta" class="plot-container" style="height: 280px;"></div>
        </div>

        <!-- 4. Feature pair histograms: corner-hist style diagnostics -->
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 15px;">
            <div id="hist-s1-width" class="plot-container" style="height: 280px;"></div>
            <div id="hist-s2-rise" class="plot-container" style="height: 280px;"></div>
            <div id="hist-width-rise" class="plot-container" style="height: 280px;"></div>
        </div>

        <!-- 5. 3D 散点图 -->
        <div id="plot-3d" class="plot-container" style="height: 480px;"></div>

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

                // 控制元素
                const s1RMin = document.getElementById('s1-range-min');
                const s1RMax = document.getElementById('s1-range-max');
                const s1NMin = document.getElementById('s1-num-min');
                const s1NMax = document.getElementById('s1-num-max');
                const s2RMin = document.getElementById('s2-range-min');
                const s2RMax = document.getElementById('s2-range-max');
                const s2NMin = document.getElementById('s2-num-min');
                const s2NMax = document.getElementById('s2-num-max');
                const binsRange = document.getElementById('hist-bins-range');
                const binsNum = document.getElementById('hist-bins-num');
                const clearSelection = document.getElementById('clear-selection');
                const badge = document.getElementById('event-count');
                const selectionState = {{ rowIds: null }};
                rawData.forEach((d, i) => {{ d._row_id = i; }});

                // 绑定回调
                function bindEvents(rangeEl, numEl) {{
                    rangeEl.addEventListener('input', () => {{
                        const val = Math.pow(10, parseFloat(rangeEl.value));
                        numEl.value = val.toFixed(1);
                        updateAllPlots();
                    }});
                    numEl.addEventListener('change', () => {{
                        const val = Math.log10(Math.max(parseFloat(numEl.value), 1.0));
                        rangeEl.value = val;
                        updateAllPlots();
                    }});
                }}

                bindEvents(s1RMin, s1NMin);
                bindEvents(s1RMax, s1NMax);
                bindEvents(s2RMin, s2NMin);
                bindEvents(s2RMax, s2NMax);

                function syncBins(value) {{
                    const bins = Math.max(20, Math.min(200, parseInt(value, 10) || 40));
                    binsRange.value = bins;
                    binsNum.value = bins;
                    updateAllPlots();
                }}

                binsRange.addEventListener('input', () => syncBins(binsRange.value));
                binsNum.addEventListener('change', () => syncBins(binsNum.value));
                clearSelection.addEventListener('click', () => {{
                    selectionState.rowIds = null;
                    updateAllPlots();
                }});

                function bindSelectionCallback(plotId) {{
                    const element = document.getElementById(plotId);
                    if (!element || element.dataset.selectionBound === 'true') {{
                        return;
                    }}
                    element.dataset.selectionBound = 'true';
                    element.on('plotly_selected', eventData => {{
                        if (!eventData || !eventData.points || eventData.points.length === 0) {{
                            return;
                        }}
                        selectionState.rowIds = new Set(
                            eventData.points
                                .map(point => point.data && point.data.meta === 'event-selection' ? point.customdata : null)
                                .filter(rowId => rowId !== undefined && rowId !== null)
                        );
                        if (selectionState.rowIds.size === 0) {{
                            selectionState.rowIds = null;
                            return;
                        }}
                        updateAllPlots();
                    }});
                    element.on('plotly_deselect', () => {{
                        selectionState.rowIds = null;
                        updateAllPlots();
                    }});
                }}

                function getFinitePairs(data, xField, yField, logX=false, logY=false) {{
                    const pairs = [];
                    for (const d of data) {{
                        const rawX = d[xField];
                        const rawY = d[yField];
                        if (rawX === null || rawY === null || rawX === undefined || rawY === undefined) {{
                            continue;
                        }}
                        const x = Number(rawX);
                        const y = Number(rawY);
                        if (
                            Number.isFinite(x) && Number.isFinite(y) &&
                            (!logX || x > 0) &&
                            (!logY || y > 0)
                        ) {{
                            pairs.push([x, y]);
                        }}
                    }}
                    return pairs;
                }}

                function buildBinSpec(values, nBins, useLog) {{
                    if (values.length === 0) {{
                        const edges = Array.from({{ length: nBins + 1 }}, (_, i) => i);
                        const centers = Array.from({{ length: nBins }}, (_, i) => i + 0.5);
                        return {{ edges, centers, tMin: 0, tMax: nBins, step: 1, transform: v => v }};
                    }}

                    const transform = useLog ? (v => Math.log10(v)) : (v => v);
                    let tMin = Math.min(...values.map(transform));
                    let tMax = Math.max(...values.map(transform));

                    if (tMin === tMax) {{
                        const pad = useLog ? 0.5 : Math.max(Math.abs(tMin) * 0.05, 0.5);
                        tMin -= pad;
                        tMax += pad;
                    }}

                    const step = (tMax - tMin) / nBins;
                    const edges = Array.from({{ length: nBins + 1 }}, (_, i) => {{
                        const edge = tMin + i * step;
                        return useLog ? Math.pow(10, edge) : edge;
                    }});
                    const centers = Array.from({{ length: nBins }}, (_, i) => {{
                        const center = tMin + (i + 0.5) * step;
                        return useLog ? Math.pow(10, center) : center;
                    }});

                    return {{ edges, centers, tMin, tMax, step, transform }};
                }}

                function buildLogCountColorbar(maxCount) {{
                    const maxLog = Math.max(Math.log10(Math.max(maxCount, 1)), 0);
                    const tickMax = Math.max(Math.floor(maxLog), 0);
                    const tickvals = Array.from({{ length: tickMax + 1 }}, (_, i) => i);
                    if (maxLog > tickMax) {{
                        tickvals.push(maxLog);
                    }}
                    const ticktext = tickvals.map(v => {{
                        const count = Math.pow(10, v);
                        return count >= 1000 ? count.toExponential(0) : Math.round(count).toString();
                    }});
                    return {{ maxLog, tickvals, ticktext }};
                }}

                function makeLogHist2dTrace(data, config) {{
                    const pairs = getFinitePairs(data, config.xField, config.yField, config.logX, config.logY);
                    const xValues = pairs.map(([x]) => x);
                    const yValues = pairs.map(([, y]) => y);
                    const xBins = buildBinSpec(xValues, config.nbinsx, config.logX);
                    const yBins = buildBinSpec(yValues, config.nbinsy, config.logY);
                    const counts = Array.from(
                        {{ length: config.nbinsy }},
                        () => Array(config.nbinsx).fill(0)
                    );

                    for (const [x, y] of pairs) {{
                        const tx = xBins.transform(x);
                        const ty = yBins.transform(y);
                        let ix = Math.floor((tx - xBins.tMin) / xBins.step);
                        let iy = Math.floor((ty - yBins.tMin) / yBins.step);

                        if (ix === config.nbinsx) ix = config.nbinsx - 1;
                        if (iy === config.nbinsy) iy = config.nbinsy - 1;
                        if (ix >= 0 && ix < config.nbinsx && iy >= 0 && iy < config.nbinsy) {{
                            counts[iy][ix] += 1;
                        }}
                    }}

                    const maxCount = Math.max(1, ...counts.flat());
                    const colorbar = buildLogCountColorbar(maxCount);
                    const z = counts.map(row => row.map(count => count > 0 ? Math.log10(count) : null));

                    return {{
                        x: xBins.centers,
                        y: yBins.centers,
                        z: z,
                        customdata: counts,
                        type: 'heatmap',
                        colorscale: config.colorscale,
                        zmin: 0,
                        zmax: colorbar.maxLog,
                        hovertemplate:
                            `${{config.xTitle}}: %{{x:.3g}}<br>` +
                            `${{config.yTitle}}: %{{y:.3g}}<br>` +
                            'Counts: %{{customdata}}<extra></extra>',
                        colorbar: {{
                            title: 'Counts',
                            tickmode: 'array',
                            tickvals: colorbar.tickvals,
                            ticktext: colorbar.ticktext
                        }}
                    }};
                }}

                function makeSelectionTrace(data, config) {{
                    const points = data.filter(d => {{
                        const rawX = d[config.xField];
                        const rawY = d[config.yField];
                        if (rawX === null || rawY === null || rawX === undefined || rawY === undefined) {{
                            return false;
                        }}
                        const x = Number(rawX);
                        const y = Number(rawY);
                        return (
                            Number.isFinite(x) && Number.isFinite(y) &&
                            (!config.logX || x > 0) &&
                            (!config.logY || y > 0)
                        );
                    }});

                    return {{
                        x: points.map(d => d[config.xField]),
                        y: points.map(d => d[config.yField]),
                        customdata: points.map(d => d._row_id),
                        meta: 'event-selection',
                        mode: 'markers',
                        type: 'scattergl',
                        showlegend: false,
                        hoverinfo: 'skip',
                        marker: {{
                            size: 5,
                            color: 'rgba(26, 32, 44, 0.03)',
                            line: {{ width: 0 }}
                        }}
                    }};
                }}

                function updateAllPlots() {{
                    const s1Min = parseFloat(s1NMin.value);
                    const s1Max = parseFloat(s1NMax.value);
                    const s2Min = parseFloat(s2NMin.value);
                    const s2Max = parseFloat(s2NMax.value);
                    const histBins = parseInt(binsNum.value, 10) || 40;

                    const areaFiltered = rawData.filter(d =>
                        d.s1_area >= s1Min && d.s1_area <= s1Max &&
                        d.s2_area >= s2Min && d.s2_area <= s2Max
                    );
                    const filtered = selectionState.rowIds
                        ? areaFiltered.filter(d => selectionState.rowIds.has(d._row_id))
                        : areaFiltered;

                    const selectionText = selectionState.rowIds ? `, box: ${{selectionState.rowIds.size.toLocaleString()}}` : '';
                    badge.innerText = `Selected: ${{filtered.length.toLocaleString()}} / ${{rawData.length.toLocaleString()}} events${{selectionText}}`;

                    // === 1. XY 散点图 ===
                    Plotly.react('plot-xy', [{{
                        x: filtered.map(d => d.x_rec),
                        y: filtered.map(d => d.y_rec),
                        customdata: filtered.map(d => d._row_id),
                        meta: 'event-selection',
                        mode: 'markers',
                        type: 'scattergl',
                        marker: {{
                            size: 3,
                            color: filtered.map(d => d.z_rec),
                            colorscale: 'Viridis',
                            showscale: true,
                            colorbar: {{ title: 'Z (mm)' }}
                        }}
                    }}], {{
                        title: 'XY Projection',
                        xaxis: {{ title: 'X (mm)', range: [-r_tpc*1.2, r_tpc*1.2] }},
                        yaxis: {{ title: 'Y (mm)', range: [-r_tpc*1.2, r_tpc*1.2], scaleanchor: 'x' }},
                        dragmode: 'select',
                        margin: {{ l:50, r:10, b:50, t:30 }},
                        shapes: [{{ type: 'circle', xref: 'x', yref: 'y', x0: -r_tpc, y0: -r_tpc, x1: r_tpc, y1: r_tpc, line: {{ color: 'red', width: 2, dash: 'dash' }} }}]
                    }}, {{ displayModeBar: true }});
                    bindSelectionCallback('plot-xy');

                    // === 2. XZ 散点图 ===
                    Plotly.react('plot-xz', [{{
                        x: filtered.map(d => d.x_rec),
                        y: filtered.map(d => d.z_rec),
                        customdata: filtered.map(d => d._row_id),
                        meta: 'event-selection',
                        mode: 'markers',
                        type: 'scattergl',
                        marker: {{
                            size: 3,
                            color: filtered.map(d => d.s2_area),
                            colorscale: 'Plasma',
                            showscale: true,
                            colorbar: {{ title: 'S2 (PE)' }}
                        }}
                    }}], {{
                        title: 'XZ Profile',
                        xaxis: {{ title: 'X (mm)' }},
                        yaxis: {{ title: 'Z (mm)', autorange: 'reversed' }},
                        dragmode: 'select',
                        margin: {{ l:55, r:10, b:50, t:30 }}
                    }}, {{ displayModeBar: true }});
                    bindSelectionCallback('plot-xz');

                    // === 3. 2D histograms (LogNorm color scale) ===
                    // XY histogram
                    Plotly.react('hist-xy', [makeLogHist2dTrace(filtered, {{
                        xField: 'x_rec',
                        yField: 'y_rec',
                        nbinsx: histBins,
                        nbinsy: histBins,
                        colorscale: 'YlOrRd',
                        xTitle: 'X (mm)',
                        yTitle: 'Y (mm)'
                    }})], {{
                        title: {{ text: 'XY Density', font: {{ size: 11 }} }},
                        xaxis: {{ title: 'X (mm)' }},
                        yaxis: {{ title: 'Y (mm)', scaleanchor: 'x' }},
                        margin: {{ l:45, r:10, b:35, t:25 }}
                    }}, {{ displayModeBar: false }});

                    // XZ histogram
                    Plotly.react('hist-xz', [makeLogHist2dTrace(filtered, {{
                        xField: 'x_rec',
                        yField: 'z_rec',
                        nbinsx: histBins,
                        nbinsy: histBins,
                        colorscale: 'Viridis',
                        xTitle: 'X (mm)',
                        yTitle: 'Z (mm)'
                    }})], {{
                        title: {{ text: 'XZ Density', font: {{ size: 11 }} }},
                        xaxis: {{ title: 'X (mm)' }},
                        yaxis: {{ title: 'Z (mm)', autorange: 'reversed' }},
                        margin: {{ l:45, r:10, b:35, t:25 }}
                    }}, {{ displayModeBar: false }});

                    // YZ histogram
                    Plotly.react('hist-yz', [makeLogHist2dTrace(filtered, {{
                        xField: 'y_rec',
                        yField: 'z_rec',
                        nbinsx: histBins,
                        nbinsy: histBins,
                        colorscale: 'Plasma',
                        xTitle: 'Y (mm)',
                        yTitle: 'Z (mm)'
                    }})], {{
                        title: {{ text: 'YZ Density', font: {{ size: 11 }} }},
                        xaxis: {{ title: 'Y (mm)' }},
                        yaxis: {{ title: 'Z (mm)', autorange: 'reversed' }},
                        margin: {{ l:45, r:10, b:35, t:25 }}
                    }}, {{ displayModeBar: false }});

                    // S1-S2 histogram
                    Plotly.react('hist-s1s2', [
                        makeLogHist2dTrace(filtered, {{
                            xField: 's1_area',
                            yField: 's2_area',
                            nbinsx: histBins,
                            nbinsy: histBins,
                            colorscale: 'Hot',
                            logX: true,
                            logY: true,
                            xTitle: 'S1 (PE)',
                            yTitle: 'S2 (PE)'
                        }}),
                        makeSelectionTrace(filtered, {{
                            xField: 's1_area',
                            yField: 's2_area',
                            logX: true,
                            logY: true
                        }})
                    ], {{
                        title: {{ text: 'S1-S2 Density', font: {{ size: 11 }} }},
                        xaxis: {{ title: 'S1 (PE)', type: 'log' }},
                        yaxis: {{ title: 'S2 (PE)', type: 'log' }},
                        dragmode: 'select',
                        margin: {{ l:45, r:10, b:35, t:25 }}
                    }}, {{ displayModeBar: true }});
                    bindSelectionCallback('hist-s1s2');

                    // R²-Z histogram
                    Plotly.react('hist-r2z', [makeLogHist2dTrace(filtered, {{
                        xField: 'r2_rec',
                        yField: 'z_rec',
                        nbinsx: histBins,
                        nbinsy: histBins,
                        colorscale: 'Cividis',
                        xTitle: 'R² (mm²)',
                        yTitle: 'Z (mm)'
                    }})], {{
                        title: {{ text: 'R²-Z Density', font: {{ size: 11 }} }},
                        xaxis: {{ title: 'R² (mm²)' }},
                        yaxis: {{ title: 'Z (mm)', autorange: 'reversed' }},
                        margin: {{ l:45, r:10, b:35, t:25 }}
                    }}, {{ displayModeBar: false }});

                    // R-cos(theta) histogram
                    Plotly.react('hist-rtheta', [makeLogHist2dTrace(filtered, {{
                        xField: 'r_rec',
                        yField: 'cos_theta_rec',
                        nbinsx: histBins,
                        nbinsy: histBins,
                        colorscale: 'Portland',
                        xTitle: 'R (mm)',
                        yTitle: 'cos(θ)'
                    }})], {{
                        title: {{ text: 'R-cos(θ) Density', font: {{ size: 11 }} }},
                        xaxis: {{ title: 'R (mm)' }},
                        yaxis: {{ title: 'cos(θ)' }},
                        margin: {{ l:45, r:10, b:35, t:25 }}
                    }}, {{ displayModeBar: false }});

                    // Corner-hist style feature pairs
                    Plotly.react('hist-s1-width', [makeLogHist2dTrace(filtered, {{
                        xField: 's1_area',
                        yField: 'width',
                        nbinsx: histBins,
                        nbinsy: histBins,
                        colorscale: 'Magma',
                        logX: true,
                        xTitle: 'S1 (PE)',
                        yTitle: 'Width'
                    }})], {{
                        title: {{ text: 'S1-Width Density', font: {{ size: 11 }} }},
                        xaxis: {{ title: 'S1 (PE)', type: 'log' }},
                        yaxis: {{ title: 'Width' }},
                        margin: {{ l:45, r:10, b:35, t:25 }}
                    }}, {{ displayModeBar: false }});

                    Plotly.react('hist-s2-rise', [makeLogHist2dTrace(filtered, {{
                        xField: 's2_area',
                        yField: 'rise_time_10_50',
                        nbinsx: histBins,
                        nbinsy: histBins,
                        colorscale: 'Turbo',
                        logX: true,
                        xTitle: 'S2 (PE)',
                        yTitle: 'Rise 10-50'
                    }})], {{
                        title: {{ text: 'S2-Rise 10-50 Density', font: {{ size: 11 }} }},
                        xaxis: {{ title: 'S2 (PE)', type: 'log' }},
                        yaxis: {{ title: 'Rise 10-50' }},
                        margin: {{ l:45, r:10, b:35, t:25 }}
                    }}, {{ displayModeBar: false }});

                    Plotly.react('hist-width-rise', [makeLogHist2dTrace(filtered, {{
                        xField: 'width',
                        yField: 'rise_time_10_50',
                        nbinsx: histBins,
                        nbinsy: histBins,
                        colorscale: 'Viridis',
                        xTitle: 'Width',
                        yTitle: 'Rise 10-50'
                    }})], {{
                        title: {{ text: 'Width-Rise 10-50 Density', font: {{ size: 11 }} }},
                        xaxis: {{ title: 'Width' }},
                        yaxis: {{ title: 'Rise 10-50' }},
                        margin: {{ l:45, r:10, b:35, t:25 }}
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
                            color: filtered.map(d => Math.log10(d.s2_area)),
                            colorscale: 'Viridis',
                            opacity: 0.7,
                            colorbar: {{ title: 'log10(S2)' }}
                        }}
                    }}], {{
                        title: '3D Distribution',
                        scene: {{
                            xaxis: {{ title: 'X (mm)' }},
                            yaxis: {{ title: 'Y (mm)' }},
                            zaxis: {{ title: 'Z (mm)', autorange: 'reversed' }}
                        }},
                        margin: {{ l:0, r:0, b:0, t:30 }}
                    }});
                }}

                updateAllPlots();
            }}
        }})();
        </script>
    </div>
</body>
</html>"""

    return html_template
