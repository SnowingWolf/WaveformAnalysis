"""导出位置重建数据用于可视化

此脚本从 WaveformAnalysis 框架导出位置重建结果，
并提供多种可视化选项（内置工具）。

使用方法：
    # 仅导出数据
    python examples/export_positions_for_visualization.py --run-id run_001 --output output/

    # 生成交互式 HTML 仪表板（推荐）
    python examples/export_positions_for_visualization.py --run-id run_001 --output output/ --dashboard

    # 生成静态图
    python examples/export_positions_for_visualization.py --run-id run_001 --output output/ --plot

输出：
    - CSV/Parquet/Pickle 格式数据文件
    - 可选：交互式 3D HTML 仪表板（基于 Plotly.js）
    - 可选：静态位置分布图（PNG，基于 matplotlib）
"""

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from waveform_analysis.core.context import Context
from waveform_analysis.core.hardware.geometry import (
    load_fallback_layout,
    load_pmt_layout_from_config,
)
from waveform_analysis.utils.s1_s2_pair_accessor import S1S2PairAccessor


def export_positions_to_dataframe(context: Context, run_id: str) -> pd.DataFrame:
    """从框架导出位置重建数据为 DataFrame

    Args:
        context: WaveformAnalysis Context
        run_id: 运行 ID

    Returns:
        包含位置和配对信息的 pandas DataFrame
    """
    # 使用 accessor 获取数据
    accessor = S1S2PairAccessor(context, run_id, selected_only=True)

    # 获取配对数据
    pairs = accessor.pairs
    if len(pairs) == 0:
        print(f"[!] Run {run_id} 没有可用的配对数据")
        return pd.DataFrame()

    # 获取位置数据
    positions = accessor.positions()
    if len(positions) == 0:
        print(f"[!] Run {run_id} 没有位置重建数据，请先运行位置重建插件")
        return pd.DataFrame()

    def _field_or_nan(data, field: str):
        if field in data.dtype.names:
            return data[field]
        return np.full(len(data), np.nan, dtype=np.float32)

    def _peak_feature_lookup(field: str) -> dict[int, float]:
        try:
            peaks = context.get_data(run_id, "peaks")
        except Exception as e:
            print(f"[!] 无法加载 peaks 特征 {field}: {e}")
            return {}

        if field not in peaks.dtype.names:
            return {}
        return {int(peak["peak_id"]): float(peak[field]) for peak in peaks}

    rise_time_by_peak = _peak_feature_lookup("rise_time_10_50")
    width_by_peak = _peak_feature_lookup("width")

    # 合并数据
    df = pd.DataFrame(
        {
            # 位置坐标
            "x_rec": positions["x"],
            "y_rec": positions["y"],
            "z_rec": positions["z"],
            # S1-S2 信息
            "s1_area": pairs["s1_area"],
            "s2_area": pairs["s2_area"],
            "s1_peak_id": pairs["s1_peak_id"],
            "s2_peak_id": pairs["s2_peak_id"],
            "drift_time_ns": pairs["drift_time_ns"],
            "s1_width": _field_or_nan(pairs, "s1_width"),
            "s2_width": _field_or_nan(pairs, "s2_width"),
            "s1_peak_width": [width_by_peak.get(int(pid), np.nan) for pid in pairs["s1_peak_id"]],
            "s2_peak_width": [width_by_peak.get(int(pid), np.nan) for pid in pairs["s2_peak_id"]],
            "s1_rise_time_10_50": [
                rise_time_by_peak.get(int(pid), np.nan) for pid in pairs["s1_peak_id"]
            ],
            "s2_rise_time_10_50": [
                rise_time_by_peak.get(int(pid), np.nan) for pid in pairs["s2_peak_id"]
            ],
            # 质量标志
            "position_valid": (positions["flags"] & 0x1) != 0,  # FLAG_POSITION_VALID
            "edge_event": (positions["flags"] & 0x10) != 0,  # FLAG_EDGE_EVENT
        }
    )

    # 过滤无效位置
    df = df[df["position_valid"]].copy()

    print(f"[✓] 导出 {len(df)} 个有效位置")

    return df


def plot_static_figures(df: pd.DataFrame, output_dir: Path, run_id: str, detector_radius_mm: float):
    """生成静态位置分布图（matplotlib）- 2D histogram 版本

    使用 2D histogram 替代一维直方图，全部使用 LogNorm。

    Args:
        df: 位置数据 DataFrame
        output_dir: 输出目录
        run_id: 运行 ID
        detector_radius_mm: 探测器半径
    """
    import matplotlib

    matplotlib.use("Agg")  # 无头模式
    from matplotlib.colors import LogNorm
    from matplotlib.patches import Circle
    import matplotlib.pyplot as plt

    if len(df) == 0:
        print("[!] 没有数据可供绘图")
        return

    # 创建 2×2 子图布局
    fig = plt.figure(figsize=(14, 12))

    # 过滤有效数据
    valid_mask = ~(np.isnan(df["x_rec"]) | np.isnan(df["y_rec"]) | np.isnan(df["z_rec"]))
    x_valid = df.loc[valid_mask, "x_rec"].values
    y_valid = df.loc[valid_mask, "y_rec"].values
    z_valid = df.loc[valid_mask, "z_rec"].values
    s1_valid = df.loc[valid_mask, "s1_area"].values
    s2_valid = df.loc[valid_mask, "s2_area"].values

    # 计算 r
    r_valid = np.sqrt(x_valid**2 + y_valid**2)

    # === 1. XY 平面分布（2D histogram + LogNorm）===
    ax1 = fig.add_subplot(2, 2, 1)

    h1 = ax1.hist2d(
        x_valid,
        y_valid,
        bins=50,
        cmap="viridis",
        norm=LogNorm(),
        range=[
            [-detector_radius_mm * 1.2, detector_radius_mm * 1.2],
            [-detector_radius_mm * 1.2, detector_radius_mm * 1.2],
        ],
    )

    # 探测器边界
    detector_circle = Circle(
        (0, 0),
        detector_radius_mm,
        fill=False,
        edgecolor="red",
        linewidth=2,
        linestyle="--",
        label=f"Detector boundary (r={detector_radius_mm} mm)",
    )
    ax1.add_patch(detector_circle)

    # 边缘事件高亮
    if "edge_event" in df.columns:
        edge_mask = valid_mask & df["edge_event"]
        if edge_mask.any():
            ax1.scatter(
                df.loc[edge_mask, "x_rec"],
                df.loc[edge_mask, "y_rec"],
                s=100,
                facecolors="none",
                edgecolors="red",
                linewidth=2,
                label="Edge events",
                zorder=10,
            )

    ax1.set_xlabel("X (mm)", fontsize=12)
    ax1.set_ylabel("Y (mm)", fontsize=12)
    ax1.set_title(f"XY Position Distribution (Run {run_id})", fontsize=14, fontweight="bold")
    ax1.set_aspect("equal")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper right")

    cbar1 = plt.colorbar(h1[3], ax=ax1)
    cbar1.set_label("Counts (log scale)", fontsize=10)

    # === 2. Z 分布（2D histogram: X-Z + LogNorm）===
    ax2 = fig.add_subplot(2, 2, 2)

    h2 = ax2.hist2d(
        x_valid,
        z_valid,
        bins=50,
        cmap="plasma",
        norm=LogNorm(),
    )

    ax2.set_xlabel("X (mm)", fontsize=12)
    ax2.set_ylabel("Z (mm)", fontsize=12)
    ax2.set_title(f"X-Z Distribution (n={len(x_valid)})", fontsize=14, fontweight="bold")
    ax2.grid(True, alpha=0.3)

    cbar2 = plt.colorbar(h2[3], ax=ax2)
    cbar2.set_label("Counts (log scale)", fontsize=10)

    # 统计信息
    z_mean = z_valid.mean()
    z_std = z_valid.std()
    ax2.text(
        0.95,
        0.95,
        f"Z: μ = {z_mean:.1f} mm\n    σ = {z_std:.1f} mm",
        transform=ax2.transAxes,
        fontsize=10,
        verticalalignment="top",
        horizontalalignment="right",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
    )

    # === 3. S1-S2 散点图（2D histogram + LogNorm，按位置着色）===
    ax3 = fig.add_subplot(2, 2, 3)

    # 使用对数 bins
    s1_log_bins = np.logspace(np.log10(s1_valid.min()), np.log10(s1_valid.max()), 50)
    s2_log_bins = np.logspace(np.log10(s2_valid.min()), np.log10(s2_valid.max()), 50)

    h3 = ax3.hist2d(
        s1_valid,
        s2_valid,
        bins=[s1_log_bins, s2_log_bins],
        cmap="coolwarm",
        norm=LogNorm(),
    )

    ax3.set_xlabel("S1 Area (PE)", fontsize=12)
    ax3.set_ylabel("S2 Area (PE)", fontsize=12)
    ax3.set_title("S1-S2 Distribution", fontsize=14, fontweight="bold")
    ax3.set_xscale("log")
    ax3.set_yscale("log")
    ax3.grid(True, alpha=0.3)

    cbar3 = plt.colorbar(h3[3], ax=ax3)
    cbar3.set_label("Counts (log scale)", fontsize=10)

    # === 4. 径向分布（2D histogram: R-Z + LogNorm）===
    ax4 = fig.add_subplot(2, 2, 4)

    h4 = ax4.hist2d(
        r_valid,
        z_valid,
        bins=50,
        cmap="viridis",
        norm=LogNorm(),
    )

    ax4.axvline(
        detector_radius_mm,
        color="red",
        linestyle="--",
        linewidth=2,
        label=f"Detector edge (r={detector_radius_mm} mm)",
    )

    ax4.set_xlabel("r (mm)", fontsize=12)
    ax4.set_ylabel("Z (mm)", fontsize=12)
    ax4.set_title(f"Radial Distribution (n={len(r_valid)})", fontsize=14, fontweight="bold")
    ax4.grid(True, alpha=0.3)
    ax4.legend()

    cbar4 = plt.colorbar(h4[3], ax=ax4)
    cbar4.set_label("Counts (log scale)", fontsize=10)

    # 统计信息
    r_mean = r_valid.mean()
    r_std = r_valid.std()
    ax4.text(
        0.95,
        0.95,
        f"r: μ = {r_mean:.1f} mm\n   σ = {r_std:.1f} mm",
        transform=ax4.transAxes,
        fontsize=10,
        verticalalignment="top",
        horizontalalignment="right",
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
    )

    # 总标题
    fig.suptitle(
        f"Position Reconstruction Summary - Run {run_id}\n"
        f"Total events: {len(df)} | Valid positions: {len(x_valid)}",
        fontsize=16,
        fontweight="bold",
        y=0.995,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.98])

    # 保存图片
    output_file = output_dir / f"run_{run_id}_position_distribution.png"
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    print(f"[✓] 位置分布图已保存: {output_file}")

    plt.close()


def main():
    parser = argparse.ArgumentParser(description="导出位置重建数据并生成可视化")
    parser.add_argument(
        "--run-id",
        type=str,
        required=True,
        help="运行 ID",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=".",
        help="数据根目录（默认：当前目录）",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output",
        help="输出目录（默认：output）",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["csv", "parquet", "pickle"],
        default="csv",
        help="输出格式（默认：csv）",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="生成静态位置分布图（matplotlib）",
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="生成交互式 HTML 仪表板（Plotly.js，原始版本）",
    )
    parser.add_argument(
        "--dashboard-2d",
        action="store_true",
        help="生成 2D 密度热力图仪表板（推荐，重点展示二维分布）",
    )
    parser.add_argument(
        "--dashboard-2d-hist",
        action="store_true",
        help="生成交互式仪表板（原始布局 + 2D histogram，带S1/S2滑动条回调）",
    )
    parser.add_argument(
        "--detector-radius",
        type=float,
        default=62.5,
        help="探测器半径 (mm)，用于边界标注（默认：62.5）",
    )

    args = parser.parse_args()

    # 创建 Context
    print(f"[*] 初始化 Context，数据根目录：{args.data_root}")
    ctx = Context(config={"data_root": args.data_root})

    # 导出数据
    print(f"[*] 导出 Run {args.run_id} 的位置数据...")
    df = export_positions_to_dataframe(ctx, args.run_id)

    if len(df) == 0:
        sys.exit(1)

    # 保存文件
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.format == "csv":
        output_file = output_dir / f"run_{args.run_id}_positions.csv"
        df.to_csv(output_file, index=False)
    elif args.format == "parquet":
        output_file = output_dir / f"run_{args.run_id}_positions.parquet"
        df.to_parquet(output_file, index=False)
    elif args.format == "pickle":
        output_file = output_dir / f"run_{args.run_id}_positions.pkl"
        df.to_pickle(output_file)

    print(f"[✓] 数据已保存至: {output_file}")

    # 可选：生成静态图
    if args.plot:
        print("[*] 生成位置分布图...")
        try:
            plot_static_figures(
                df=df,
                output_dir=output_dir,
                run_id=args.run_id,
                detector_radius_mm=args.detector_radius,
            )
        except Exception as e:
            print(f"[!] 生成位置分布图时出错: {e}")
            import traceback

            traceback.print_exc()

    # 可选：生成交互式 HTML 仪表板
    if args.dashboard:
        print("[*] 生成交互式 HTML 仪表板（原始版本）...")
        try:
            from waveform_analysis.visualization import render_position_dashboard

            # 加载 PMT 布局
            layout = load_pmt_layout_from_config(ctx.config)
            if layout is None:
                layout = load_fallback_layout()

            # 生成仪表板
            render_position_dashboard(
                df=df,
                layout=layout,
                run_id=args.run_id,
                output_dir=str(output_dir),
                detector_radius_mm=args.detector_radius,
            )

        except ImportError as e:
            print(f"[!] 无法导入可视化模块: {e}")
            print("[!] 请确保 waveform_analysis.visualization 模块已安装")
        except Exception as e:
            print(f"[!] 生成仪表板时出错: {e}")
            import traceback

            traceback.print_exc()

    # 可选：生成 2D 密度仪表板
    if args.dashboard_2d:
        print("[*] 生成 2D 密度热力图仪表板（推荐）...")
        try:
            from waveform_analysis.visualization import render_position_dashboard_2d

            # 加载 PMT 布局
            layout = load_pmt_layout_from_config(ctx.config)
            if layout is None:
                layout = load_fallback_layout()

            # 生成仪表板
            render_position_dashboard_2d(
                df=df,
                layout=layout,
                run_id=args.run_id,
                output_dir=str(output_dir),
                detector_radius_mm=args.detector_radius,
            )

        except ImportError as e:
            print(f"[!] 无法导入可视化模块: {e}")
            print("[!] 请确保 waveform_analysis.visualization 模块已安装")
        except Exception as e:
            print(f"[!] 生成 2D 仪表板时出错: {e}")
            import traceback

            traceback.print_exc()

    # 可选：生成 2D histogram 仪表板（原始布局）
    if args.dashboard_2d_hist:
        print("[*] 生成交互式仪表板（原始布局 + 2D histogram）...")
        try:
            from waveform_analysis.visualization import render_position_dashboard_with_2d_hist

            # 加载 PMT 布局
            layout = load_pmt_layout_from_config(ctx.config)
            if layout is None:
                layout = load_fallback_layout()

            # 生成仪表板
            render_position_dashboard_with_2d_hist(
                df=df,
                layout=layout,
                run_id=args.run_id,
                output_dir=str(output_dir),
                detector_radius_mm=args.detector_radius,
            )

        except ImportError as e:
            print(f"[!] 无法导入可视化模块: {e}")
            print("[!] 请确保 waveform_analysis.visualization 模块已安装")
        except Exception as e:
            print(f"[!] 生成 2D histogram 仪表板时出错: {e}")
            import traceback

            traceback.print_exc()

    print("[✓] 完成！")


if __name__ == "__main__":
    main()
