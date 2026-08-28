# xihu_fast_analysis/dashboard.py
import json
import os

from IPython.display import HTML, display
import numpy as np
import pandas as pd

from .layout import PmtLayout


def render_instant_html_dashboard(
    df: pd.DataFrame,
    layout: PmtLayout,
    r_tpc: float = 62.5,
    run_id: str = "unknown",
    output_dir: str = "output",
) -> str:
    """
    生成纯前端零延迟大面板，含 X-Y、X-Z 剖面、1D 空间直方图、1D 能量能谱与 R² 不均匀性检测图
    """
    df_clean = df[
        ["x_rec", "y_rec", "z_rec", "s1_area", "s2_area", "s2_peak_id", "drift_time_ns"]
    ].copy()

    # 预计算特征，防止前端大算力计算引起页面假死
    df_clean["r2_rec"] = df_clean["x_rec"] ** 2 + df_clean["y_rec"] ** 2
    df_clean["log10_s1"] = np.log10(df_clean["s1_area"].clip(lower=1.0))
    df_clean["log10_s2"] = np.log10(df_clean["s2_area"].clip(lower=1.0))

    json_data = json.dumps(df_clean.to_dict(orient="records"))

    z_min = float(df_clean["z_rec"].min())
    z_max = float(df_clean["z_rec"].max())
    s1_min_raw = float(max(df_clean["s1_area"].min(), 1.0))
    s1_max_raw = float(df_clean["s1_area"].max())
    s2_min_raw = float(max(df_clean["s2_area"].min(), 1.0))
    s2_max_raw = float(df_clean["s2_area"].max())

    # 序列化当前的 PMT 排布信息传到前端进行图形绘制
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

    html_template = """
    <div id="wltpc-dashboard" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #fdfdfd; padding: 15px; border-radius: 12px; border: 1px solid #e2e8f0; max-width: 1200px; margin: 10px auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">

        <!-- Loading Spinner -->
        <div id="plotly-loader" style="position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(255,255,255,0.9); z-index:9999; display: flex; flex-direction:column; justify-content:center; align-items:center; transition: opacity 0.3s ease;">
            <div style="border: 4px solid #f3f3f3; border-top: 4px solid #3182ce; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin-bottom:15px;"></div>
            <div style="color: #2d3748; font-weight:bold; font-size:16px;">正在加载 Plotly.js 物理交互引擎...</div>
            <div style="color: #718096; font-size:12px; margin-top:5px;">正在加载自适应物理布局，请稍候</div>
            <style>
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            </style>
        </div>

        <!-- A. 顶部控制面板 -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; background: #ffffff; padding: 15px; border-radius: 8px; border: 1px solid #edf2f7;">
            <div>
                <h4 style="margin: 0 0 10px 0; color: #2d3748; font-size: 14px; display: flex; justify-content: space-between;">
                    <span>S1 Area Filter (Log10)</span>
                    <span id="s1-count-badge" style="background:#edf2f7; padding: 2px 8px; border-radius: 12px; font-size:11px; font-weight: bold; color: #2b6cb0;"></span>
                </h4>
                <div style="display: flex; flex-direction: column; gap: 6px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 11px; width: 60px; color:#718096;">Min (Log):</span>
                        <input type="range" id="s1-range-min" min="__S1_MIN_LOG__" max="__S1_MAX_LOG__" step="0.01" value="__S1_MIN_LOG__" style="flex:1; cursor:pointer;">
                        <input type="number" id="s1-num-min" value="__S1_MIN_RAW__" style="width: 80px; font-size:11px; padding: 2px; border: 1px solid #cbd5e0; border-radius: 4px;">
                        <span style="font-size: 11px; color:#a0aec0; width: 25px;">PE</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 11px; width: 60px; color:#718096;">Max (Log):</span>
                        <input type="range" id="s1-range-max" min="__S1_MIN_LOG__" max="__S1_MAX_LOG__" step="0.01" value="__S1_MAX_LOG__" style="flex:1; cursor:pointer;">
                        <input type="number" id="s1-num-max" value="__S1_MAX_RAW__" style="width: 80px; font-size:11px; padding: 2px; border: 1px solid #cbd5e0; border-radius: 4px;">
                        <span style="font-size: 11px; color:#a0aec0; width: 25px;">PE</span>
                    </div>
                </div>
            </div>
            <div>
                <h4 style="margin: 0 0 10px 0; color: #2d3748; font-size: 14px;">S2 Area Filter (Log10)</h4>
                <div style="display: flex; flex-direction: column; gap: 6px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 11px; width: 60px; color:#718096;">Min (Log):</span>
                        <input type="range" id="s2-range-min" min="__S2_MIN_LOG__" max="__S2_MAX_LOG__" step="0.01" value="__S2_MIN_LOG__" style="flex:1; cursor:pointer;">
                        <input type="number" id="s2-num-min" value="__S2_MIN_RAW__" style="width: 80px; font-size:11px; padding: 2px; border: 1px solid #cbd5e0; border-radius: 4px;">
                        <span style="font-size: 11px; color:#a0aec0; width: 25px;">PE</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 11px; width: 60px; color:#718096;">Max (Log):</span>
                        <input type="range" id="s2-range-max" min="__S2_MIN_LOG__" max="__S2_MAX_LOG__" step="0.01" value="__S2_MAX_LOG__" style="flex:1; cursor:pointer;">
                        <input type="number" id="s2-num-max" value="__S2_MAX_RAW__" style="width: 80px; font-size:11px; padding: 2px; border: 1px solid #cbd5e0; border-radius: 4px;">
                        <span style="font-size: 11px; color:#a0aec0; width: 25px;">PE</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- B. 绘图面板网格 -->
        <!-- 1. XY 投影与 XZ 剖面 -->
        <div style="display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 15px; margin-bottom: 15px;">
            <div id="plot-xy" style="height: 380px; border: 1px solid #edf2f7; border-radius:8px; background:#fff;"></div>
            <div id="plot-xz" style="height: 380px; border: 1px solid #edf2f7; border-radius:8px; background:#fff;"></div>
        </div>

        <!-- 2. 位置 1D 统计直方图 -->
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 15px;">
            <div id="hist-x" style="height: 180px; border: 1px solid #edf2f7; border-radius:8px; background:#fff;"></div>
            <div id="hist-y" style="height: 180px; border: 1px solid #edf2f7; border-radius:8px; background:#fff;"></div>
            <div id="hist-z" style="height: 180px; border: 1px solid #edf2f7; border-radius:8px; background:#fff;"></div>
        </div>

        <!-- 3. 【新增诊断面板】 S1 面积谱、S2 面积谱与 R² 不均匀性校验直方图 -->
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 15px;">
            <div id="hist-s1" style="height: 190px; border: 1px solid #edf2f7; border-radius:8px; background:#fff;"></div>
            <div id="hist-s2" style="height: 190px; border: 1px solid #edf2f7; border-radius:8px; background:#fff;"></div>
            <div id="hist-r2" style="height: 190px; border: 1px solid #edf2f7; border-radius:8px; background:#fff;"></div>
        </div>

        <!-- 4. 3D WebGL 事例立体图 -->
        <div id="plot-3d" style="height: 480px; border: 1px solid #edf2f7; border-radius:8px; background:#fff;"></div>

        <!-- C. JS 渲染逻辑 -->
        <script>
        (() => {
            function loadScript(url, callback) {
                if (window.Plotly) { callback(); return; }
                const script = document.createElement("script");
                script.type = "text/javascript"; script.src = url;
                script.onload = callback; document.head.appendChild(script);
            }

            const cdn_url = "https://cdn.plot.ly/plotly-2.24.1.min.js";

            loadScript(cdn_url, () => {
                const loader = document.getElementById("plotly-loader");
                if (loader) loader.style.opacity = "0";
                setTimeout(() => { if(loader) loader.style.display = "none"; }, 300);
                initializeDashboard();
            });

            function initializeDashboard() {
                const rawData = __JSON_DATA__;
                const pmts = __PMT_CONFIG_JSON__;
                const r_tpc = __R_TPC__;
                const r_tpc2 = r_tpc * r_tpc;
                const zMin = __Z_MIN__;
                const zMax = __Z_MAX__;

                const s1RMin = document.getElementById('s1-range-min');
                const s1RMax = document.getElementById('s1-range-max');
                const s1NMin = document.getElementById('s1-num-min');
                const s1NMax = document.getElementById('s1-num-max');
                const s2RMin = document.getElementById('s2-range-min');
                const s2RMax = document.getElementById('s2-range-max');
                const s2NMin = document.getElementById('s2-num-min');
                const s2NMax = document.getElementById('s2-num-max');
                const badge = document.getElementById('s1-count-badge');

                function getRotatedSquare(cx, cy, size = 21.5, angle = 30.0) {
                    const hs = size / 2.0;
                    const localVertices = [[-hs, -hs], [hs, -hs], [hs, hs], [-hs, hs], [-hs, -hs]];
                    const rad = angle * Math.PI / 180.0;
                    const cos = Math.cos(rad), sin = Math.sin(rad);
                    return {
                        x: localVertices.map(v => v[0] * cos - v[1] * sin + cx),
                        y: localVertices.map(v => v[0] * sin + v[1] * cos + cy)
                    };
                }

                function computeHist(data, key, minVal, maxVal, numBins) {
                    const step = (maxVal - minVal) / numBins;
                    const counts = new Array(numBins).fill(0);
                    const xCenter = [];
                    for (let i = 0; i < numBins; i++) { xCenter.push(minVal + step * (i + 0.5)); }
                    for (let i = 0; i < data.length; i++) {
                        const val = data[i][key];
                        if (val >= minVal && val <= maxVal) {
                            const binIdx = Math.floor((val - minVal) / step);
                            if (binIdx >= 0 && binIdx < numBins) counts[binIdx]++;
                            else if (binIdx === numBins) counts[numBins - 1]++;
                        }
                    }
                    return { x: xCenter, y: counts, width: step * 0.9 };
                }

                const pmtTraces2D = [];
                pmts.forEach(p => {
                    const geom = getRotatedSquare(p.x_mm, p.y_mm, 21.5, 30.0);
                    pmtTraces2D.push({
                        x: geom.x, y: geom.y, mode: 'lines',
                        line: { color: '#4a5568', width: 1.5 },
                        showlegend: false, hoverinfo: 'none', type: 'scatter'
                    });
                    pmtTraces2D.push({
                        x: [p.x_mm], y: [p.y_mm], mode: 'text',
                        text: [String(p.pmt_no)], textposition: 'middle center',
                        textfont: { size: 12, color: '#1a202c', weight: 'bold' },
                        showlegend: false, hoverinfo: 'none', type: 'scatter'
                    });
                });

                const theta = Array.from({ length: 100 }, (_, i) => i * 2 * Math.PI / 99);
                const tpcCircleTrace = {
                    x: theta.map(t => r_tpc * Math.cos(t)),
                    y: theta.map(t => r_tpc * Math.sin(t)),
                    mode: 'lines', line: { color: 'navy', width: 2 },
                    showlegend: false, hoverinfo: 'none', type: 'scatter'
                };

                const pmtTraces3D = [];
                pmts.forEach(p => {
                    const geom = getRotatedSquare(p.x_mm, p.y_mm, 21.5, 30.0);
                    const zs = Array(geom.x.length).fill(zMin - 1.5);
                    pmtTraces3D.push({
                        x: geom.x, y: geom.y, z: zs, mode: 'lines',
                        line: { color: 'rgba(220, 53, 69, 0.9)', width: 2.5 },
                        type: 'scatter3d', showlegend: false, hoverinfo: 'none'
                    });
                    pmtTraces3D.push({
                        x: [p.x_mm], y: [p.y_mm], z: [zMin - 3.5], mode: 'text',
                        text: [String(p.pmt_no)], textposition: 'middle center',
                        textfont: { size: 11, color: '#e53e3e', weight: 'bold' },
                        type: 'scatter3d', showlegend: false, hoverinfo: 'none'
                    });
                });

                const scatterMarker = {
                    size: 4, color: [], colorscale: 'Plasma', cmin: zMin, cmax: zMax,
                    colorbar: { title: { text: 'Depth Z [mm]', font: { size: 10 } }, thickness: 12, len: 0.85 },
                    opacity: 0.75, line: { color: 'black', width: 0.2 }
                };

                const layoutXY = {
                    title: { text: 'Transverse (X-Y) Coordinates', font: { size: 13, weight: 'bold' } },
                    xaxis: { range: [-75, 75], title: 'X_rec [mm]', gridcolor: '#edf2f7' },
                    yaxis: { range: [-75, 75], title: 'Y_rec [mm]', scaleanchor: 'x', gridcolor: '#edf2f7' },
                    margin: { l: 50, r: 10, b: 50, t: 30 }, plot_bgcolor: '#fff'
                };

                const layoutXZ = {
                    title: { text: 'Depth (X-Z) Profile', font: { size: 13, weight: 'bold' } },
                    xaxis: { range: [-75, 75], title: 'X_rec [mm]', gridcolor: '#edf2f7' },
                    yaxis: { range: [zMax + 5, zMin - 5], title: 'Drift Depth Z [mm]', gridcolor: '#edf2f7' },
                    margin: { l: 55, r: 10, b: 50, t: 30 }, plot_bgcolor: '#fff'
                };

                const histLayout = (title, xLabel) => ({
                    title: { text: title, font: { size: 11, weight: 'bold' } },
                    xaxis: { title: xLabel, gridcolor: '#edf2f7' }, yaxis: { title: 'Counts', gridcolor: '#edf2f7' },
                    margin: { l: 45, r: 10, b: 35, t: 25 }, plot_bgcolor: '#fff'
                });

                const layout3D = {
                    title: { text: '3D Event Spatial Distribution', font: { size: 13, weight: 'bold' } },
                    scene: {
                        xaxis: { title: 'X [mm]', range: [-75, 75] },
                        yaxis: { title: 'Y [mm]', range: [-75, 75] },
                        zaxis: { title: 'Depth Z [mm]', range: [zMax + 5, zMin - 5] },
                        aspectratio: { x: 1, y: 1, z: 1.2 }
                    }, margin: { l: 0, r: 0, b: 0, t: 30 }
                };

                function updateAllPlots() {
                    const s1Min = parseFloat(s1NMin.value), s1Max = parseFloat(s1NMax.value);
                    const s2Min = parseFloat(s2NMin.value), s2Max = parseFloat(s2NMax.value);

                    const filtered = rawData.filter(d =>
                        d.s1_area >= s1Min && d.s1_area <= s1Max && d.s2_area >= s2Min && d.s2_area <= s2Max
                    );

                    let displayData = filtered;
                    const MAX_RENDER_POINTS = 25000;
                    let isDownsampled = false;

                    if (filtered.length > MAX_RENDER_POINTS) {
                        isDownsampled = true; displayData = [];
                        const step = Math.ceil(filtered.length / MAX_RENDER_POINTS);
                        for (let i = 0; i < filtered.length; i += step) { displayData.push(filtered[i]); }
                    }

                    if (isDownsampled) {
                        badge.innerText = `Selected: ${filtered.length.toLocaleString()} / ${rawData.length.toLocaleString()} (Scatter Sampled ${displayData.length.toLocaleString()})`;
                        badge.style.background = "#fff3cd"; badge.style.color = "#856404";
                    } else {
                        badge.innerText = `Selected: ${filtered.length.toLocaleString()} / ${rawData.length.toLocaleString()} Events`;
                        badge.style.background = "#edf2f7"; badge.style.color = "#2b6cb0";
                    }

                    const xs = displayData.map(d => d.x_rec), ys = displayData.map(d => d.y_rec), zs = displayData.map(d => d.z_rec);
                    const s2_areas = displayData.map(d => d.s2_area);
                    const hoverTexts = displayData.map(d =>
                        `S2 ID: ${d.s2_peak_id}<br>X_rec: ${d.x_rec.toFixed(1)} mm<br>Y_rec: ${d.y_rec.toFixed(1)} mm<br>Z_rec: ${d.z_rec.toFixed(1)} mm<br>S1: ${d.s1_area.toFixed(0)} PE<br>S2: ${d.s2_area.toFixed(0)} PE`
                    );

                    const activeMarker = { ...scatterMarker, color: zs };
                    Plotly.react('plot-xy', [...pmtTraces2D, tpcCircleTrace, {
                        x: xs, y: ys, mode: 'markers', marker: activeMarker, text: hoverTexts, hoverinfo: 'text', showlegend: false, type: 'scattergl'
                    }], layoutXY, { displayModeBar: false });

                    Plotly.react('plot-xz', [{
                        x: xs, y: zs, mode: 'markers', marker: activeMarker, text: hoverTexts, hoverinfo: 'text', showlegend: false, type: 'scattergl'
                    }], layoutXZ, { displayModeBar: false });

                    const hx = computeHist(filtered, 'x_rec', -75, 75, 35);
                    Plotly.react('hist-x', [{ x: hx.x, y: hx.y, type: 'bar', width: hx.width, marker: { color: '#E53E3E', opacity: 0.85 } }], histLayout('X Coordinate Dist', 'X [mm]'), { displayModeBar: false });

                    const hy = computeHist(filtered, 'y_rec', -75, 75, 35);
                    Plotly.react('hist-y', [{ x: hy.x, y: hy.y, type: 'bar', width: hy.width, marker: { color: '#319795', opacity: 0.85 } }], histLayout('Y Coordinate Dist', 'Y [mm]'), { displayModeBar: false });

                    const hz = computeHist(filtered, 'z_rec', zMin, zMax, 35);
                    Plotly.react('hist-z', [{ x: hz.x, y: hz.y, type: 'bar', width: hz.width, marker: { color: '#3182CE', opacity: 0.85 } }], histLayout('Z Depth Dist', 'Depth Z [mm]'), { displayModeBar: false });

                    // 【新诊断视图绘图：100% 事例精度的能谱与 R² 均匀性检测】
                    const hs1 = computeHist(filtered, 'log10_s1', Math.log10(s1Min), Math.log10(s1Max), 35);
                    Plotly.react('hist-s1', [{ x: hs1.x, y: hs1.y, type: 'bar', width: hs1.width, marker: { color: '#D69E2E', opacity: 0.85 } }], histLayout('S1 Energy Spectrum', 'Log10(S1 Area [PE])'), { displayModeBar: false });

                    const hs2 = computeHist(filtered, 'log10_s2', Math.log10(s2Min), Math.log10(s2Max), 35);
                    Plotly.react('hist-s2', [{ x: hs2.x, y: hs2.y, type: 'bar', width: hs2.width, marker: { color: '#805AD5', opacity: 0.85 } }], histLayout('S2 Energy Spectrum', 'Log10(S2 Area [PE])'), { displayModeBar: false });

                    const hr2 = computeHist(filtered, 'r2_rec', 0, r_tpc2, 35);
                    Plotly.react('hist-r2', [{ x: hr2.x, y: hr2.y, type: 'bar', width: hr2.width, marker: { color: '#38A169', opacity: 0.85 } }], histLayout('Uniformity Check (R²)', 'R² (X²+Y²) [mm²]'), { displayModeBar: false });

                    const trace3D = {
                        x: xs, y: ys, z: zs, mode: 'markers',
                        marker: {
                            size: 3, color: s2_areas.map(v => Math.log10(v)), colorscale: 'Plasma',
                            colorbar: { title: { text: "Log10(S2)", font: { size: 10 } }, thickness: 12, len: 0.7 },
                            opacity: 0.8, line: { color: 'black', width: 0.1 }
                        }, text: hoverTexts, hoverinfo: 'text', type: 'scatter3d'
                    };
                    const traces3D_all = [trace3D, ...pmtTraces3D];
                    const loop3D = Array.from({ length: 60 }, (_, i) => i * 2 * Math.PI / 59);
                    [zMin, zMax].forEach(zRing => {
                        traces3D_all.push({
                            x: loop3D.map(t => r_tpc * Math.cos(t)), y: loop3D.map(t => r_tpc * Math.sin(t)), z: Array(60).fill(zRing),
                            mode: 'lines', line: { color: 'rgba(128,128,128,0.25)', width: 1.2 }, type: 'scatter3d', showlegend: false, hoverinfo: 'none'
                        });
                    });
                    Plotly.react('plot-3d', traces3D_all, layout3D);
                }

                function bindEvents(rangeEl, numEl) {
                    rangeEl.addEventListener('input', () => {
                        const val = Math.pow(10, parseFloat(rangeEl.value));
                        numEl.value = val.toFixed(1); updateAllPlots();
                    });
                    numEl.addEventListener('change', () => {
                        const val = Math.log10(Math.max(parseFloat(numEl.value), 1.0));
                        rangeEl.value = val; updateAllPlots();
                    });
                }

                bindEvents(s1RMin, s1NMin); bindEvents(s1RMax, s1NMax);
                bindEvents(s2RMin, s2NMin); bindEvents(s2RMax, s2NMax);
                updateAllPlots();
            }
        })();
        </script>
    </div>
    """

    # 数据填空
    html_content = html_template
    html_content = html_content.replace("__JSON_DATA__", json_data)
    html_content = html_content.replace("__PMT_CONFIG_JSON__", pmt_config_json)
    html_content = html_content.replace("__R_TPC__", str(r_tpc))
    html_content = html_content.replace("__Z_MIN__", str(z_min))
    html_content = html_content.replace("__Z_MAX__", str(z_max))

    html_content = html_content.replace("__S1_MIN_RAW__", f"{s1_min_raw:.1f}")
    html_content = html_content.replace("__S1_MAX_RAW__", f"{s1_max_raw:.1f}")
    html_content = html_content.replace("__S2_MIN_RAW__", f"{s2_min_raw:.1f}")
    html_content = html_content.replace("__S2_MAX_RAW__", f"{s2_max_raw:.1f}")

    html_content = html_content.replace("__S1_MIN_LOG__", f"{np.log10(s1_min_raw):.4f}")
    html_content = html_content.replace("__S1_MAX_LOG__", f"{np.log10(s1_max_raw):.4f}")
    html_content = html_content.replace("__S2_MIN_LOG__", f"{np.log10(s2_min_raw):.4f}")
    html_content = html_content.replace("__S2_MAX_LOG__", f"{np.log10(s2_max_raw):.4f}")

    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"run_{run_id}_3d_reconstruction_dashboard.html")

    full_html_page = f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Run {run_id} - 3D Reconstruction Interactive Board</title>
        <style>body {{ background-color: #f7fafc; margin: 0; padding: 20px; }}</style>
    </head>
    <body>{html_content}</body>
    </html>"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(full_html_page)

    print(f"[✓] 离线网页文件已成功导出至: {file_path}")
    # display(HTML(html_content))
