#!/usr/bin/env python3
"""为 web 插件索引页生成"插件集合"真实波形配图。

从真实 DAQ 波形（/mnt/data/Run3/DAQ/Argon_w4_o3_Window_0dB_300LSB_200xAmp_Scintillation2）
解析事件，运行真实插件链（hit → hit_merged → peaklets → peaks），并在真实波形上绘制 7 张图，
保存到 waveform_analysis/utils/templates/web/assets/plugin-sets/，由 plugin_doc_generator 复制进站点。

运行：python examples/generate_plugin_set_images.py
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from matplotlib import font_manager
import matplotlib.pyplot as plt
import numpy as np

from waveform_analysis.core.plugins.builtin.cpu.hit_merge import (
    HitMergedComponentsPlugin,
    HitMergePlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.hit_merged_features import (
    HitMergedFeaturesPlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.peaklet_channels import PeakletChannelsPlugin
from waveform_analysis.core.plugins.builtin.cpu.peaklets import (
    PeakletComponentsPlugin,
    PeakletFeaturesPlugin,
    PeakletPlugin,
    PeakletWaveformPlugin,
    PeaksPlugin,
)
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "waveform_analysis" / "utils" / "templates" / "web" / "assets" / "plugin-sets"

# 真实数据：Argon 闪烁体 run，通道 2，含清晰的 S1/S2 脉冲。
DAQ_RUN = "Argon_w4_o3_Window_0dB_300LSB_200xAmp_Scintillation2"
CSV_PATH = Path("/mnt/data/Run3/DAQ") / DAQ_RUN / "RAW" / f"DataR_CH2@VX2730_53013_{DAQ_RUN}.CSV"
CHANNEL = 2
DT_NS = 2  # VX2730 @ 500 MHz

# 站点视觉：各插件集合主色（与 PLUGIN_SET_COLORS 一致）。
SET_COLORS = {
    "io": "#3b78b8",
    "waveform": "#278a5b",
    "hit": "#c76b20",
    "peaks": "#8054b5",
    "basic_features": "#a98219",
    "tabular": "#287e88",
    "events": "#bb4666",
}

_CJK_CANDIDATES = (
    "Noto Sans CJK SC",
    "Noto Sans CJK JP",
    "WenQuanYi Zen Hei",
    "WenQuanYi Micro Hei",
    "SimHei",
    "Microsoft YaHei",
)
_installed_fonts = {f.name for f in font_manager.fontManager.ttflist}
CJK_FONT = next((f for f in _CJK_CANDIDATES if f in _installed_fonts), None)
if CJK_FONT:
    plt.rcParams["font.family"] = CJK_FONT
else:
    print("WARNING: 未找到 CJK 字体，图中中文标签可能显示为方块")


class _DummyContext:
    """最小上下文：为真实插件提供配置与中间数据（同 examples/demo_peaklet_visualization.py）。"""

    def __init__(self, config, data):
        self.config = config
        self._data = data
        self._plugins = {}

    def get_config(self, plugin, key):
        return self.config.get(key)

    def get_data(self, run_id, key):
        return self._data.get(key)

    def register(self, plugin):
        self._plugins[plugin.provides] = plugin

    def get_plugin(self, name):
        return self._plugins.get(name)


def parse_events(limit: int = 60) -> list[np.ndarray]:
    """从真实 DAQ CSV 读取前 limit 个事件波形（int16/float64）。"""
    if not CSV_PATH.is_file():
        raise FileNotFoundError(
            f"缺少真实 DAQ 数据: {CSV_PATH}\n"
            "请确认该 run 的原始 CSV 存在（波形配图脚本依赖真实数据）。"
        )
    events = []
    with open(CSV_PATH) as fh:
        reader = csv.reader(fh, delimiter=";")
        next(reader)  # 表头
        for row in reader:
            if len(events) >= limit:
                break
            samples = [float(x) for x in row[7:] if x.strip()]
            if samples:
                events.append(np.asarray(samples, dtype=np.float64))
    return events


def build_hits(wave, baseline, threshold, dt=DT_NS, channel=CHANNEL, record_id=0):
    """在真实波形上做阈值检测，构造 hit_threshold 结构化数组。"""
    below = wave < baseline - threshold
    hits = []
    i = 0
    while i < len(wave):
        if below[i]:
            j = i
            while j < len(wave) and below[j]:
                j += 1
            hit = np.zeros(1, dtype=THRESHOLD_HIT_DTYPE)[0]
            pos = (i + j - 1) // 2
            hit["position"] = pos
            hit["edge_start"] = i
            hit["edge_end"] = j - 1
            hit["width"] = j - 1 - i
            hit["dt"] = dt
            hit["timestamp"] = pos * dt * 1000  # ps
            hit["board"] = 0
            hit["channel"] = channel
            hit["record_id"] = record_id
            hits.append(hit)
            i = j
        else:
            i += 1
    return np.array(hits, dtype=THRESHOLD_HIT_DTYPE) if hits else np.empty(0, THRESHOLD_HIT_DTYPE)


_RECORD_DTYPE = [
    ("timestamp", "i8"),
    ("board", "i4"),
    ("channel", "i4"),
    ("event_length", "i4"),
    ("dt", "i4"),
    ("baseline", "f4"),
    ("polarity", "U8"),
    ("wave_offset", "i8"),
    ("record_id", "i8"),
]


def _build_records_pool(wave, baseline):
    rec = np.zeros(1, dtype=_RECORD_DTYPE)
    rec[0]["timestamp"] = 0
    rec[0]["board"] = 0
    rec[0]["channel"] = CHANNEL
    rec[0]["event_length"] = len(wave)
    rec[0]["dt"] = DT_NS
    rec[0]["baseline"] = baseline
    rec[0]["polarity"] = "negative"
    rec[0]["wave_offset"] = 0
    rec[0]["record_id"] = 0
    return rec, wave.astype(np.float32)


_PEAKLET_CONFIG = {
    "merge_gap_ns": 50.0,
    "time_window_ns": 1000.0,
    "max_total_width_ns": 100000.0,
    "dt": DT_NS,
    "use_filtered": False,
    "wave_source": "records",
    "n_workers": 1,
    "parallel_threshold": 100000,
    "debug_numba": 0,
    "log_waveform_diagnostics": 0,
    "clip_negative_signal": 0,
    "height_range": [40, 1e9],
    "area_range": [0, 1e9],
}


def run_peaklet_chain(wave, threshold=100.0):
    """在真实波形上运行真实插件链，返回 peaks / peaklet_waveforms / peaklet_features。"""
    baseline = float(np.median(wave))
    hits = build_hits(wave, baseline, threshold)
    if len(hits) == 0:
        return None
    records, wave_pool = _build_records_pool(wave, baseline)

    merge_ctx = _DummyContext(
        {k: _PEAKLET_CONFIG[k] for k in ("merge_gap_ns", "max_total_width_ns", "dt")},
        {"hit_threshold": hits},
    )
    merge_plugin = HitMergePlugin()
    components_plugin = HitMergedComponentsPlugin()
    merge_ctx.register(merge_plugin)
    merge_ctx.register(components_plugin)
    merge_ctx._plugins["hit_merged"] = merge_plugin
    merge_ctx.get_plugin = lambda name: merge_ctx._plugins.get(name)
    hit_merged = merge_plugin.compute(merge_ctx, "demo_run")
    merge_ctx._data["hit_merged"] = hit_merged
    hit_merged_components = components_plugin.compute(merge_ctx, "demo_run")

    feature_ctx = _DummyContext(
        {k: _PEAKLET_CONFIG[k] for k in ("wave_source", "use_filtered", "dt")},
        {
            "hit_threshold": hits,
            "hit_merged": hit_merged,
            "hit_merged_components": hit_merged_components,
            "records": records,
            "wave_pool": wave_pool,
        },
    )
    hit_merged_features = HitMergedFeaturesPlugin().compute(feature_ctx, "demo_run")

    peaklet_ctx = _DummyContext(_PEAKLET_CONFIG, {"hit_threshold": hits, "hit_merged": hit_merged})
    peaklet_ctx._data.update(
        {
            "hit_merged": hit_merged,
            "hit_merged_components": hit_merged_components,
            "hit_merged_features": hit_merged_features,
            "records": records,
            "wave_pool": wave_pool,
        }
    )
    components = PeakletComponentsPlugin().compute(peaklet_ctx, "demo_run")
    peaklet_ctx._data["peaklet_components"] = components
    peaklets = PeakletPlugin().compute(peaklet_ctx, "demo_run")
    peaklet_ctx._data["peaklets"] = peaklets
    peaklet_waveforms = PeakletWaveformPlugin().compute(peaklet_ctx, "demo_run")
    peaklet_ctx._data["peaklet_waveforms"] = peaklet_waveforms
    peaklet_ctx._data["peaklet_waveform_pool"] = peaklet_ctx._data.get(
        "peaklet_waveform_pool", np.array([])
    )
    peaklet_features = PeakletFeaturesPlugin().compute(peaklet_ctx, "demo_run")
    peaklet_ctx._data["peaklet_features"] = peaklet_features
    peaklet_channels = PeakletChannelsPlugin().compute(peaklet_ctx, "demo_run")
    peaklet_ctx._data["peaklet_channels"] = peaklet_channels
    peaks = PeaksPlugin().compute(peaklet_ctx, "demo_run")
    return {
        "hits": hits,
        "hit_merged": hit_merged,
        "peaks": peaks,
        "peaklet_waveforms": peaklet_waveforms,
        "peaklet_features": peaklet_features,
        "wave": wave,
        "baseline": baseline,
    }


def _time_ns(x):
    """sample index -> ns（VX2730 dt=2ns）。"""
    return np.arange(len(x)) * DT_NS


def _peak_sample(peak_time_ps):
    return peak_time_ps / 1000.0 / DT_NS


def pick_two_peak_event(events, threshold=100.0):
    """挑选一个运行真实插件链后得到 >=2 个 peaks 的真实事件（S1/S2 演示）。"""
    for ev in events:
        result = run_peaklet_chain(ev, threshold)
        if result is not None and len(result["peaks"]) >= 2:
            return ev, result
    return events[0], run_peaklet_chain(events[0], threshold)


def plot_io(events, raw_files_by_channel):
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(9.4, 3.6), gridspec_kw={"width_ratios": [1.15, 1]})
    wave = events[0]
    ax.plot(_time_ns(wave), wave, color=SET_COLORS["io"], linewidth=0.9)
    ax.set_xlabel("时间 (ns)")
    ax.set_ylabel("幅度 (ADC)")
    ax.set_title("真实原始事件波形", fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.annotate(
        f"CH{CHANNEL} 首个事件",
        xy=(0.02, 0.97),
        xycoords="axes fraction",
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": SET_COLORS["io"], "alpha": 0.12},
    )
    ax2.axis("off")
    lines = [f"raw_files（{DAQ_RUN}）", "按通道分组原始文件："]
    for ch, files in raw_files_by_channel.items():
        lines.append(f"· CH{ch}: {len(files)} 个文件")
    ax2.text(
        0.02,
        0.97,
        "\n".join(lines),
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "#f1f5f9", "edgecolor": "#c9dff5"},
    )
    fig.tight_layout()
    return fig


def plot_waveform(wave):
    fig, ax = plt.subplots(figsize=(9.4, 3.4))
    ax.plot(_time_ns(wave), wave, color=SET_COLORS["waveform"], linewidth=1.0)
    baseline = float(np.median(wave))
    ax.axhline(baseline, color="#93b8a3", linestyle="--", linewidth=1, label=f"基线 {baseline:.0f}")
    ax.set_xlabel("时间 (ns)")
    ax.set_ylabel("幅度 (ADC)")
    ax.set_title(f"结构化事件波形（{DAQ_RUN} CH{CHANNEL}，真实数据）", fontsize=11)
    ax.legend(framealpha=0.9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def plot_hit(wave, hits, baseline):
    fig, ax = plt.subplots(figsize=(9.4, 3.4))
    ax.plot(_time_ns(wave), wave, color="#5b6b76", linewidth=1.0, label="真实波形")
    threshold = baseline - 100.0
    ax.axhline(threshold, color=SET_COLORS["hit"], linestyle="--", linewidth=1.2, label="检测阈值")
    for hit in hits:
        s = int(hit["edge_start"])
        e = int(hit["edge_end"])
        ax.axvspan(s * DT_NS, e * DT_NS, color=SET_COLORS["hit"], alpha=0.18)
        ax.plot(
            int(hit["position"]) * DT_NS,
            wave[int(hit["position"])],
            "o",
            color=SET_COLORS["hit"],
            markersize=5,
        )
    ax.set_xlabel("时间 (ns)")
    ax.set_ylabel("幅度 (ADC)")
    ax.set_title(f"Hit 检测（{DAQ_RUN} 真实事件，{len(hits)} 个 hits）", fontsize=11)
    ax.legend(framealpha=0.9, loc="lower right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def plot_peaks(wave, result):
    peaks = result["peaks"]
    fig, ax = plt.subplots(figsize=(9.4, 3.6))
    ax.plot(_time_ns(wave), wave, color="#b6b2c9", linewidth=1.0, label="真实波形")
    colors = ["#2b6cb0", "#c0392b"]
    for i, peak in enumerate(sorted(peaks, key=lambda p: int(p["time_start"]))):
        s = int(_peak_sample(peak["time_start"]))
        e = int(_peak_sample(peak["time_end"]))
        ax.axvspan(s * DT_NS, e * DT_NS, color=SET_COLORS["peaks"], alpha=0.16)
        label = f"Peak {i + 1}"
        ax.text(
            (s + e) / 2 * DT_NS,
            np.min(wave[s : e + 1]),
            label,
            ha="center",
            va="bottom",
            fontsize=9,
            color=colors[i % 2],
            fontweight="bold",
        )
        ax.plot(
            int(_peak_sample(peak["time_peak"])) * DT_NS,
            wave[int(_peak_sample(peak["time_peak"]))],
            "o",
            color=colors[i % 2],
            markersize=5,
        )
    ax.set_xlabel("时间 (ns)")
    ax.set_ylabel("幅度 (ADC)")
    ax.set_title(f"Peaklet 聚类 → Peaks（真实插件链输出，{len(peaks)} 个 peaks）", fontsize=11)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def plot_basic_features(wave, result):
    peaks = sorted(result["peaks"], key=lambda p: int(p["time_start"]))
    fig, ax = plt.subplots(figsize=(9.4, 3.6))
    ax.plot(_time_ns(wave), wave, color="#8a939b", linewidth=1.0, label="真实波形")
    for _i, peak in enumerate(peaks[:2]):
        s = int(_peak_sample(peak["time_start"]))
        e = int(_peak_sample(peak["time_end"]))
        color = "#a98219"
        ax.axvspan(s * DT_NS, e * DT_NS, color=color, alpha=0.13)
        ax.plot(
            (s + e) / 2 * DT_NS,
            float(peak["height"]) + float(result["baseline"]),
            "x",
            color=color,
            markersize=8,
        )
        ax.annotate(
            f"height={float(peak['height']):.0f}\narea={float(peak['area']):.0f}",
            xy=((s + e) / 2 * DT_NS, float(peak["height"]) + float(result["baseline"])),
            xytext=(6, 8),
            textcoords="offset points",
            fontsize=8.5,
            color="#7a5f12",
            arrowprops={"arrowstyle": "-", "color": "#c9ad5c", "lw": 0.8},
        )
    ax.set_xlabel("时间 (ns)")
    ax.set_ylabel("幅度 (ADC)")
    ax.set_title("基础特征提取：height / area（真实波形）", fontsize=11)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def plot_tabular(result):
    peaks = sorted(result["peaks"], key=lambda p: int(p["time_start"]))
    fig, ax = plt.subplots(figsize=(9.4, 3.2))
    ax.axis("off")
    cols = ["time_start", "time_peak", "height", "area", "width_ns", "n_hits"]
    rows = []
    for peak in peaks:
        rows.append(
            [
                f"{int(peak['time_start']) / 1000:.0f}",
                f"{int(peak['time_peak']) / 1000:.0f}",
                f"{float(peak['height']):.1f}",
                f"{float(peak['area']):.1f}",
                f"{float(peak['width']):.1f}",
                f"{int(peak['n_hits'])}",
            ]
        )
    table = ax.table(
        cellText=rows,
        colLabels=cols,
        loc="center",
        cellLoc="center",
        colLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)
    for j in range(len(cols)):
        table[0, j].set_facecolor("#e6f4f6")
        table[0, j].set_text_props(fontweight="bold", color="#287e88")
    ax.set_title("表格输出（tabular）：真实 peaks → DataFrame 行", fontsize=11, pad=10)
    fig.tight_layout()
    return fig


def plot_events(wave, result):
    peaks = sorted(result["peaks"], key=lambda p: int(p["time_start"]))
    fig, ax = plt.subplots(figsize=(9.4, 3.6))
    ax.plot(_time_ns(wave), wave, color="#cfc9d8", linewidth=0.9, label="真实事件波形")
    pair = peaks[:2]
    colors = ["#2b6cb0", "#c0392b"]
    names = ["S1", "S2"]
    centers = []
    for i, peak in enumerate(pair):
        s = int(_peak_sample(peak["time_start"]))
        e = int(_peak_sample(peak["time_end"]))
        color = colors[i % 2]
        ax.axvspan(s * DT_NS, e * DT_NS, color=color, alpha=0.14)
        ax.plot(_time_ns(wave)[s : e + 1], wave[s : e + 1], color=color, linewidth=1.6)
        cx = int(_peak_sample(peak["time_peak"])) * DT_NS
        centers.append(cx)
        ax.text(
            cx,
            float(result["baseline"]) + 8,
            names[i],
            ha="center",
            fontsize=10,
            fontweight="bold",
            color=color,
        )
    if len(centers) == 2:
        ax.annotate(
            "S1-S2 配对",
            xy=((centers[0] + centers[1]) / 2, float(result["baseline"])),
            xytext=(0, -30),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color="#bb4666",
            arrowprops={"arrowstyle": "<->", "color": "#bb4666", "lw": 1.1},
        )
    ax.set_xlabel("时间 (ns)")
    ax.set_ylabel("幅度 (ADC)")
    ax.set_title("事件级处理：S1-S2 配对（真实波形）", fontsize=11)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def main():
    events = parse_events(limit=60)
    print(f"已解析 {len(events)} 个真实事件（{DAQ_RUN} CH{CHANNEL}）")

    raw_files_by_channel = {}
    raw_dir = CSV_PATH.parent
    for csv_file in sorted(raw_dir.glob("DataR_*.CSV")):
        ch = None
        for token in csv_file.name.split("_"):
            if token.startswith("CH"):
                ch = token[2:]
                break
        raw_files_by_channel.setdefault(ch or "?", []).append(csv_file.name)
    print(f"raw_files 分组: { {k: len(v) for k, v in raw_files_by_channel.items()} }")

    wave, result = pick_two_peak_event(events)
    if result is None:
        raise RuntimeError("真实事件上未检测到任何 hits，无法运行插件链")
    print(f"选中事件: {len(wave)} 采样点，插件链产出 {len(result['peaks'])} 个 peaks")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plotters = [
        ("io", lambda: plot_io(events, raw_files_by_channel)),
        ("waveform", lambda: plot_waveform(wave)),
        ("hit", lambda: plot_hit(wave, result["hits"], result["baseline"])),
        ("peaks", lambda: plot_peaks(wave, result)),
        ("basic_features", lambda: plot_basic_features(wave, result)),
        ("tabular", lambda: plot_tabular(result)),
        ("events", lambda: plot_events(wave, result)),
    ]
    for name, plotter in plotters:
        try:
            fig = plotter()
            path = OUT_DIR / f"{name}.png"
            fig.savefig(path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            print(f"  ✓ {name}.png  {path.stat().st_size / 1024:.0f} KB")
        except Exception as exc:  # noqa: BLE001 - 一张图失败不中断其余
            print(f"  ✗ {name}.png  失败: {exc}")
    print("\n完成，输出目录:", OUT_DIR)


if __name__ == "__main__":
    main()
