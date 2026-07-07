#!/usr/bin/env python3
"""
Peaklet 效果演示脚本

展示 peaklet 检测流程：
1. 从模拟的 hits 开始
2. 将同通道相近的 hits 合并为 hit_merged
3. 将跨通道时间上重叠的 hit_merged 聚类为 peaklets
4. 提取 peaklet 的波形特征（面积、高度、宽度等）
5. 可视化展示整个处理链
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from waveform_analysis.core.plugins.builtin.cpu.hit_merge import (
    HitMergedComponentsPlugin,
    HitMergePlugin,
)
from waveform_analysis.core.plugins.builtin.cpu.hit_merged_features import HitMergedFeaturesPlugin
from waveform_analysis.core.plugins.builtin.cpu.peaklets import (
    PeakletComponentsPlugin,
    PeakletFeaturesPlugin,
    PeakletPlugin,
    PeakletWaveformPlugin,
    PeakletWaveformPoolPlugin,
    PeaksPlugin,
)
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE


class DummyContext:
    """简单的上下文模拟"""

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


def make_hit(*, record_id, board, channel, edge_start, edge_end, dt=2, timestamp=0):
    """创建一个 hit"""
    arr = np.zeros(1, dtype=THRESHOLD_HIT_DTYPE)
    position = (edge_start + edge_end - 1) // 2
    arr[0]["position"] = position
    arr[0]["edge_start"] = edge_start
    arr[0]["edge_end"] = edge_end
    arr[0]["width"] = edge_end - edge_start
    arr[0]["dt"] = dt
    arr[0]["timestamp"] = timestamp + position * dt * 1000
    arr[0]["board"] = board
    arr[0]["channel"] = channel
    arr[0]["record_id"] = record_id
    return arr[0]


def create_synthetic_data(n_channels=4, n_peaks=3):
    """
    创建合成测试数据，模拟多通道波形和 hits

    参数：
        n_channels: 通道数
        n_peaks: 峰的数量

    返回：
        records: 记录数组
        wave_pool: 波形池
        hits: hit 数组
    """
    dt = 2  # 采样间隔 ns
    event_length = 500  # 每个 record 的采样点数
    baseline = 1000.0

    records = []
    wave_pool = []
    hits = []
    wave_offset = 0

    # 为每个通道生成带有信号的 record
    for ch in range(n_channels):
        # 创建基线
        waveform = np.full(event_length, baseline, dtype=np.uint16)

        # 在不同位置添加信号峰
        for peak_idx in range(n_peaks):
            # 峰的时间位置（有轻微的通道间延迟）
            peak_center = 100 + peak_idx * 150 + ch * 2

            # 峰的幅度（不同通道幅度不同，模拟真实情况）
            amplitude = 200 * (1.0 - ch * 0.15) * (1.0 + 0.3 * np.random.rand())

            # 峰的宽度
            width = 20 + np.random.randint(-5, 5)

            # 生成高斯形状的峰（负极性）
            for i in range(max(0, peak_center - width), min(event_length, peak_center + width)):
                distance = abs(i - peak_center)
                gaussian = amplitude * np.exp(-0.5 * (distance / (width / 3)) ** 2)
                waveform[i] = int(baseline - gaussian)

            # 为这个峰创建一个 hit
            edge_start = max(0, peak_center - width)
            edge_end = min(event_length, peak_center + width)
            hit = make_hit(
                record_id=ch,
                board=0,
                channel=ch,
                edge_start=edge_start,
                edge_end=edge_end,
                dt=dt,
                timestamp=0,
            )
            hits.append(hit)

        # 添加噪声
        noise = np.random.normal(0, 5, event_length)
        waveform = np.clip(waveform.astype(float) + noise, 0, 65535).astype(np.uint16)

        # 创建 record
        record = np.zeros(
            1,
            dtype=[
                ("timestamp", "i8"),
                ("board", "i4"),
                ("channel", "i4"),
                ("event_length", "i4"),
                ("dt", "i4"),
                ("baseline", "f4"),
                ("polarity", "U8"),
                ("wave_offset", "i8"),
                ("record_id", "i8"),
            ],
        )[0]

        record["timestamp"] = 0
        record["board"] = 0
        record["channel"] = ch
        record["event_length"] = event_length
        record["dt"] = dt
        record["baseline"] = baseline
        record["polarity"] = "negative"
        record["wave_offset"] = wave_offset
        record["record_id"] = ch

        records.append(record)
        wave_pool.append(waveform)
        wave_offset += event_length

    records_array = np.array(records)
    wave_pool_array = np.concatenate(wave_pool)
    hits_array = np.array(hits, dtype=THRESHOLD_HIT_DTYPE)

    return records_array, wave_pool_array, hits_array


def visualize_peaklet_pipeline(
    records,
    wave_pool,
    hits,
    hit_merged,
    peaklets,
    peaklet_waveforms,
    peaklet_waveform_pool,
    peaklet_features,
    peaks,
):
    """
    可视化整个 peaklet 检测流程
    """
    n_channels = len(records)
    dt_ns = int(records[0]["dt"])
    baseline = float(records[0]["baseline"])

    fig, axes = plt.subplots(4, 1, figsize=(16, 12))
    fig.suptitle("Peaklet 检测流程可视化", fontsize=16, fontweight="bold")

    # 颜色方案
    channel_colors = plt.cm.tab10(np.linspace(0, 1, n_channels))

    # ========== 子图 1: 原始波形 + hits ==========
    ax1 = axes[0]
    ax1.set_title("步骤 1: 原始波形 + Hit 检测", fontsize=12, fontweight="bold")
    ax1.set_ylabel("信号强度")

    for ch_idx, record in enumerate(records):
        channel = int(record["channel"])
        offset = int(record["wave_offset"])
        length = int(record["event_length"])
        waveform = wave_pool[offset : offset + length]

        # 时间轴（单位：ns）
        time_ns = np.arange(length) * dt_ns

        # 绘制波形（转换为信号：baseline - ADC）
        signal = baseline - waveform
        ax1.plot(
            time_ns,
            signal + ch_idx * 50,
            label=f"Ch {channel}",
            color=channel_colors[ch_idx],
            alpha=0.7,
            linewidth=1.5,
        )

    # 标记 hits
    for hit in hits:
        ch = int(hit["channel"])
        ch_idx = ch
        edge_start = int(hit["edge_start"])
        edge_end = int(hit["edge_end"])

        time_start = edge_start * dt_ns
        time_end = edge_end * dt_ns

        ax1.axvspan(
            time_start,
            time_end,
            ymin=ch_idx / n_channels,
            ymax=(ch_idx + 1) / n_channels,
            alpha=0.2,
            color="red",
            linewidth=0,
        )

    ax1.legend(loc="upper right", ncol=n_channels, framealpha=0.9)
    ax1.grid(True, alpha=0.3)

    # ========== 子图 2: hit_merged 时间区间 ==========
    ax2 = axes[1]
    ax2.set_title("步骤 2: Hit 合并（同通道时间相近的 hits）", fontsize=12, fontweight="bold")
    ax2.set_ylabel("通道")
    ax2.set_yticks(range(n_channels))
    ax2.set_yticklabels([f"Ch {i}" for i in range(n_channels)])

    for merged in hit_merged:
        ch = int(merged["channel"])

        # 计算绝对时间
        names = merged.dtype.names or ()
        timestamp = int(merged["timestamp"]) if "timestamp" in names else 0
        position = int(merged["position"]) if "position" in names else 0
        sample_start = int(merged["sample_start"])
        sample_end = int(merged["sample_end"])
        dt = int(merged["dt"])

        time_start = (timestamp + (sample_start - position) * dt * 1000) / 1000.0  # ns
        time_end = (timestamp + (sample_end - position) * dt * 1000) / 1000.0  # ns

        ax2.barh(
            ch,
            time_end - time_start,
            left=time_start,
            height=0.6,
            color=channel_colors[ch],
            alpha=0.7,
            edgecolor="black",
            linewidth=1.5,
        )

    ax2.grid(True, alpha=0.3, axis="x")

    # ========== 子图 3: peaklets 聚类 ==========
    ax3 = axes[2]
    ax3.set_title(
        "步骤 3: Peaklet 聚类（跨通道时间重叠的 hit_merged）", fontsize=12, fontweight="bold"
    )
    ax3.set_ylabel("Peaklet ID")

    if len(peaklets) > 0:
        ax3.set_yticks(range(len(peaklets)))
        ax3.set_yticklabels([f"P{i}" for i in range(len(peaklets))])

        # 为每个 peaklet 着色
        peaklet_colors = plt.cm.Set3(np.linspace(0, 1, max(len(peaklets), 3)))

        for pk_idx, peaklet in enumerate(peaklets):
            time_start = int(peaklet["time_start"]) / 1000.0  # ps -> ns
            time_end = int(peaklet["time_end"]) / 1000.0  # ps -> ns
            center_time = int(peaklet["center_time"]) / 1000.0  # ps -> ns
            n_hits = int(peaklet["n_hits"])
            n_channels = int(peaklet["n_channels"])

            # 绘制 peaklet 时间范围
            ax3.barh(
                pk_idx,
                time_end - time_start,
                left=time_start,
                height=0.8,
                color=peaklet_colors[pk_idx],
                alpha=0.7,
                edgecolor="black",
                linewidth=2,
            )

            # 标记中心时间
            ax3.plot(center_time, pk_idx, "ko", markersize=8)

            # 添加统计信息
            ax3.text(
                center_time,
                pk_idx,
                f" {n_hits}h/{n_channels}ch",
                va="center",
                ha="left",
                fontsize=9,
                fontweight="bold",
            )

    ax3.grid(True, alpha=0.3, axis="x")

    # ========== 子图 4: peaklet 波形特征 ==========
    ax4 = axes[3]
    ax4.set_title("步骤 4: Peaklet 波形特征提取", fontsize=12, fontweight="bold")
    ax4.set_ylabel("信号 (归一化)")
    ax4.set_xlabel("时间 (ns)")

    if len(peaklets) > 0:
        peaklet_colors = plt.cm.Set3(np.linspace(0, 1, max(len(peaklets), 3)))

        for pk_idx, waveform_row in enumerate(peaklet_waveforms):
            peaklet_id = int(waveform_row["peak_id"])
            time_start = int(waveform_row["time_start"]) / 1000.0  # ps -> ns
            dt = int(waveform_row["dt"])
            wave_offset = int(waveform_row["wave_offset"])
            wave_length = int(waveform_row["wave_length"])

            if wave_length > 0:
                wave = peaklet_waveform_pool[wave_offset : wave_offset + wave_length]
                time_axis = time_start + np.arange(wave_length) * dt

                # 归一化波形
                wave_max = np.max(wave)
                wave_norm = wave / (wave_max + 1e-10) if wave_max > 0 else wave

                # 绘制波形
                ax4.plot(
                    time_axis,
                    wave_norm + pk_idx * 1.5,
                    color=peaklet_colors[peaklet_id],
                    linewidth=2,
                    label=f"Peaklet {peaklet_id}",
                )

                # 标记特征
                if pk_idx < len(peaklet_features):
                    feature = peaklet_features[pk_idx]
                    time_peak = int(feature["time_peak"]) / 1000.0  # ps -> ns
                    area = float(feature["area"])
                    height = float(feature["height"])
                    width = float(feature["width"])

                    # 标记峰值位置
                    max_idx = int((time_peak - time_start) / dt)
                    if 0 <= max_idx < len(wave_norm):
                        ax4.plot(
                            time_peak,
                            wave_norm[max_idx] + pk_idx * 1.5,
                            "r*",
                            markersize=15,
                            markeredgewidth=1.5,
                            markeredgecolor="black",
                        )

                    # 添加特征文本
                    info_text = (
                        f"Area: {area:.1f}\n" f"Height: {height:.1f}\n" f"Width: {width:.1f} ns"
                    )
                    ax4.text(
                        time_start - 30,
                        pk_idx * 1.5 + 0.5,
                        info_text,
                        fontsize=8,
                        bbox={
                            "boxstyle": "round,pad=0.3",
                            "facecolor": peaklet_colors[peaklet_id],
                            "alpha": 0.3,
                        },
                    )

    ax4.legend(loc="upper right", framealpha=0.9)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def main():
    """主函数：运行 peaklet 检测并可视化"""
    print("=" * 60)
    print("Peaklet 检测流程演示")
    print("=" * 60)

    # 1. 创建合成数据
    print("\n[1/5] 创建合成多通道波形数据...")
    records, wave_pool, hits = create_synthetic_data(n_channels=4, n_peaks=3)
    print(f"  ✓ 生成了 {len(records)} 个通道的数据")
    print(f"  ✓ 波形池大小: {len(wave_pool)} 个采样点")
    print(f"  ✓ 检测到 {len(hits)} 个 hits")

    # 2. Hit 合并
    print("\n[2/5] 执行 Hit 合并...")
    merge_ctx = DummyContext(
        {"merge_gap_ns": 10.0, "max_total_width_ns": 10000.0, "dt": 2},
        {"hit_threshold": hits},
    )
    merge_plugin = HitMergePlugin()
    components_plugin = HitMergedComponentsPlugin()
    merge_ctx.register(merge_plugin)
    merge_ctx.register(components_plugin)
    merge_ctx._plugins["hit_merged"] = merge_plugin
    merge_ctx.get_plugin = lambda name: merge_ctx._plugins.get(name)

    hit_merged = merge_plugin.compute(merge_ctx, "demo_run")
    merge_ctx._data["hit_merged"] = hit_merged  # 添加到 context 中
    hit_merged_components = components_plugin.compute(merge_ctx, "demo_run")
    print(f"  ✓ 合并为 {len(hit_merged)} 个 hit_merged")

    # 3. 计算 hit_merged_features（peaklet 依赖）
    print("\n[3/5] 计算 hit_merged 特征...")
    feature_ctx = DummyContext(
        {
            "wave_source": "records",
            "use_filtered": False,
            "dt": 2,
        },
        {
            "hit_threshold": hits,
            "hit_merged": hit_merged,
            "hit_merged_components": hit_merged_components,
            "records": records,
            "wave_pool": wave_pool,
        },
    )
    features = HitMergedFeaturesPlugin().compute(feature_ctx, "demo_run")
    print(f"  ✓ 计算了 {len(features)} 个 hit_merged 的特征")

    # 4. Peaklet 聚类
    print("\n[4/5] 执行 Peaklet 聚类...")
    peaklet_ctx = DummyContext(
        {
            "time_window_ns": 100.0,
            "max_total_width_ns": 10000.0,
            "dt": 2,
            "use_filtered": False,
        },
        {
            "hit_threshold": hits,
            "hit_merged": hit_merged,
            "hit_merged_components": hit_merged_components,
            "hit_merged_features": features,
            "records": records,
            "wave_pool": wave_pool,
        },
    )

    peaklet_plugin = PeakletPlugin()
    peaklet_components_plugin = PeakletComponentsPlugin()
    peaklet_waveform_plugin = PeakletWaveformPlugin()
    peaklet_features_plugin = PeakletFeaturesPlugin()
    peaks_plugin = PeaksPlugin()

    peaklets = peaklet_plugin.compute(peaklet_ctx, "demo_run")
    peaklet_components = peaklet_components_plugin.compute(peaklet_ctx, "demo_run")
    print(f"  ✓ 聚类为 {len(peaklets)} 个 peaklets")
    peaklet_ctx._data["peaklets"] = peaklets
    peaklet_ctx._data["peaklet_components"] = peaklet_components

    # 5. 提取 peaklet 波形和特征
    print("\n[5/5] 提取 Peaklet 波形特征...")
    peaklet_waveforms = peaklet_waveform_plugin.compute(peaklet_ctx, "demo_run")
    peaklet_waveform_pool = peaklet_ctx._data.get("peaklet_waveform_pool", np.array([]))
    peaklet_ctx._data["peaklet_waveforms"] = peaklet_waveforms
    peaklet_ctx._data["peaklet_waveform_pool"] = peaklet_waveform_pool

    peaklet_features = peaklet_features_plugin.compute(peaklet_ctx, "demo_run")
    peaklet_ctx._data["peaklet_features"] = peaklet_features

    # 需要 peaklet_channels 来生成 peaks，这里用简单的实现
    from waveform_analysis.core.plugins.builtin.cpu.peaklet_channels import PeakletChannelsPlugin

    peaklet_channels_plugin = PeakletChannelsPlugin()
    peaklet_channels = peaklet_channels_plugin.compute(peaklet_ctx, "demo_run")
    peaklet_ctx._data["peaklet_channels"] = peaklet_channels

    peaks = peaks_plugin.compute(peaklet_ctx, "demo_run")

    print(f"  ✓ 提取了 {len(peaklet_features)} 个 peaklet 的特征")
    print(f"  ✓ 最终生成 {len(peaks)} 个 peaks")

    # 6. 打印详细结果
    print("\n" + "=" * 60)
    print("检测结果详情")
    print("=" * 60)

    for pk_idx, peak in enumerate(peaks):
        print(f"\n【Peak {pk_idx}】")
        print(f"  时间范围: {peak['time_start']/1000:.1f} - {peak['time_end']/1000:.1f} ns")
        print(f"  中心时间: {peak['center_time']/1000:.1f} ns")
        print(f"  峰值时间: {peak['time_peak']/1000:.1f} ns")
        print(f"  面积: {peak['area']:.2f}")
        print(f"  高度: {peak['height']:.2f}")
        print(f"  宽度: {peak['width']:.2f} ns")
        print(f"  上升时间: {peak['rise_time']:.2f} ns")
        print(f"  下降时间: {peak['fall_time']:.2f} ns")
        print(f"  包含 hits: {peak['n_hits']}")
        print(f"  跨越通道: {peak['n_channels']}")

    # 7. 可视化
    print("\n" + "=" * 60)
    print("生成可视化图表...")
    print("=" * 60)

    fig = visualize_peaklet_pipeline(
        records,
        wave_pool,
        hits,
        hit_merged,
        peaklets,
        peaklet_waveforms,
        peaklet_waveform_pool,
        peaklet_features,
        peaks,
    )

    # 保存图片
    output_dir = Path("examples/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "peaklet_visualization.png"
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\n✓ 可视化结果已保存至: {output_path}")

    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)
    print("\n提示: 查看生成的图片以了解 peaklet 检测的完整流程")


if __name__ == "__main__":
    main()
