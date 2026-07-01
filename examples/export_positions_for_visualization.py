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
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from waveform_analysis.core.context import Context
from waveform_analysis.utils.s1_s2_pair_accessor import S1S2PairAccessor
from waveform_analysis.core.hardware.geometry import (
    load_fallback_layout,
    load_pmt_layout_from_config,
)


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
    positions = accessor.get_positions()
    if len(positions) == 0:
        print(f"[!] Run {run_id} 没有位置重建数据，请先运行位置重建插件")
        return pd.DataFrame()

    # 合并数据
    df = pd.DataFrame({
        # 位置坐标
        'x_rec': positions['x'],
        'y_rec': positions['y'],
        'z_rec': positions['z'],

        # S1-S2 信息
        's1_area': pairs['s1_area'],
        's2_area': pairs['s2_area'],
        's1_peak_id': pairs['s1_peak_id'],
        's2_peak_id': pairs['s2_peak_id'],
        'drift_time_ns': pairs['drift_time_ns'],

        # 质量标志
        'position_valid': (positions['flags'] & 0x1) != 0,  # FLAG_POSITION_VALID
        'edge_event': (positions['flags'] & 0x10) != 0,     # FLAG_EDGE_EVENT
    })

    # 过滤无效位置
    df = df[df['position_valid']].copy()

    print(f"[✓] 导出 {len(df)} 个有效位置")

    return df


def plot_static_figures(df: pd.DataFrame, output_dir: Path, run_id: str, detector_radius_mm: float):
    """生成静态位置分布图（matplotlib）- 2D 密度图版本

    Args:
        df: 位置数据 DataFrame
        output_dir: 输出目录
        run_id: 运行 ID
        detector_radius_mm: 探测器半径
    """
    import matplotlib
    matplotlib.use('Agg')  # 无头模式
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle
    from matplotlib.colors import LogNorm

    if len(df) == 0:
        print("[!] 没有数据可供绘图")
        return

    # 创建 2x3 子图布局（增加了图表数量）
    fig = plt.figure(figsize=(18, 12))

    # 过滤有效数据
    valid_mask = ~(np.isnan(df['x_rec']) | np.isnan(df['y_rec']) | np.isnan(df['z_rec']))
    x_valid = df.loc[valid_mask, 'x_rec'].values
    y_valid = df.loc[valid_mask, 'y_rec'].values
    z_valid = df.loc[valid_mask, 'z_rec'].values
    s1_valid = df.loc[valid_mask, 's1_area'].values
    s2_valid = df.loc[valid_mask, 's2_area'].values

    # 计算 r²
    r2_valid = x_valid**2 + y_valid**2

    # === 1. XY 二维密度图 ===
    ax1 = fig.add_subplot(2, 3, 1)

    # 2D 直方图（热力图）
    h1 = ax1.hist2d(
        x_valid,
        y_valid,
        bins=50,
        cmap='YlOrRd',
        range=[[-detector_radius_mm*1.2, detector_radius_mm*1.2],
               [-detector_radius_mm*1.2, detector_radius_mm*1.2]],
        cmin=1,
    )

    # 探测器边界
    detector_circle = Circle(
        (0, 0),
        detector_radius_mm,
        fill=False,
        edgecolor='blue',
        linewidth=2,
        linestyle='--',
        label=f'Detector boundary',
    )
    ax1.add_patch(detector_circle)

    ax1.set_xlabel('X (mm)', fontsize=12)
    ax1.set_ylabel('Y (mm)', fontsize=12)
    ax1.set_title(f'XY Density Map (n={len(x_valid)})', fontsize=14, fontweight='bold')
    ax1.set_aspect('equal')
    ax1.legend(loc='upper right')

    cbar1 = plt.colorbar(h1[3], ax=ax1)
    cbar1.set_label('Counts', fontsize=10)

    # === 2. R²-Z 二维密度图 ===
    ax2 = fig.add_subplot(2, 3, 2)

    h2 = ax2.hist2d(
        r2_valid,
        z_valid,
        bins=50,
        cmap='viridis',
        cmin=1,
    )

    # R² = detector_radius² 边界线
    r2_boundary = detector_radius_mm**2
    ax2.axvline(r2_boundary, color='red', linestyle='--', linewidth=2, label=f'R² boundary')

    ax2.set_xlabel('R² (mm²)', fontsize=12)
    ax2.set_ylabel('Z (mm)', fontsize=12)
    ax2.set_title(f'R²-Z Density Map', fontsize=14, fontweight='bold')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)

    cbar2 = plt.colorbar(h2[3], ax=ax2)
    cbar2.set_label('Counts', fontsize=10)

    # === 3. S1-S2 二维密度图（对数坐标）===
    ax3 = fig.add_subplot(2, 3, 3)

    # 使用对数 bins
    s1_log_bins = np.logspace(np.log10(s1_valid.min()), np.log10(s1_valid.max()), 50)
    s2_log_bins = np.logspace(np.log10(s2_valid.min()), np.log10(s2_valid.max()), 50)

    h3 = ax3.hist2d(
        s1_valid,
        s2_valid,
        bins=[s1_log_bins, s2_log_bins],
        cmap='plasma',
        cmin=1,
        norm=LogNorm(),
    )

    ax3.set_xlabel('S1 Area (PE)', fontsize=12)
    ax3.set_ylabel('S2 Area (PE)', fontsize=12)
    ax3.set_title('S1-S2 Density Map', fontsize=14, fontweight='bold')
    ax3.set_xscale('log')
    ax3.set_yscale('log')
    ax3.grid(True, alpha=0.3, which='both')

    cbar3 = plt.colorbar(h3[3], ax=ax3)
    cbar3.set_label('Counts (log)', fontsize=10)

    # === 4. XY 散点图（按事件数着色，保留传统视图）===
    ax4 = fig.add_subplot(2, 3, 4)

    scatter4 = ax4.scatter(
        x_valid,
        y_valid,
        c=s2_valid,
        cmap='coolwarm',
        s=10,
        alpha=0.5,
        edgecolors='none',
    )

    # 探测器边界
    detector_circle2 = Circle(
        (0, 0),
        detector_radius_mm,
        fill=False,
        edgecolor='blue',
        linewidth=2,
        linestyle='--',
    )
    ax4.add_patch(detector_circle2)

    ax4.set_xlabel('X (mm)', fontsize=12)
    ax4.set_ylabel('Y (mm)', fontsize=12)
    ax4.set_title('XY Scatter (colored by S2)', fontsize=14, fontweight='bold')
    ax4.set_aspect('equal')
    ax4.grid(True, alpha=0.3)

    cbar4 = plt.colorbar(scatter4, ax=ax4)
    cbar4.set_label('S2 Area (PE)', fontsize=10)

    # === 5. Z 一维分布（参考）===
    ax5 = fig.add_subplot(2, 3, 5)

    ax5.hist(z_valid, bins=60, color='steelblue', alpha=0.7, edgecolor='black')

    z_mean = z_valid.mean()
    z_std = z_valid.std()
    ax5.axvline(z_mean, color='red', linestyle='--', linewidth=2, label=f'Mean: {z_mean:.1f} mm')

    ax5.set_xlabel('Z (mm)', fontsize=12)
    ax5.set_ylabel('Count', fontsize=12)
    ax5.set_title(f'Z Distribution', fontsize=14, fontweight='bold')
    ax5.grid(True, alpha=0.3, axis='y')
    ax5.legend()

    ax5.text(
        0.95, 0.95,
        f'μ = {z_mean:.1f} mm\nσ = {z_std:.1f} mm',
        transform=ax5.transAxes,
        fontsize=10,
        verticalalignment='top',
        horizontalalignment='right',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
    )

    # === 6. R² 一维分布（参考）===
    ax6 = fig.add_subplot(2, 3, 6)

    ax6.hist(r2_valid, bins=60, color='coral', alpha=0.7, edgecolor='black')
    ax6.axvline(
        r2_boundary,
        color='red',
        linestyle='--',
        linewidth=2,
        label=f'R² boundary ({detector_radius_mm}² mm²)',
    )

    ax6.set_xlabel('R² (mm²)', fontsize=12)
    ax6.set_ylabel('Count', fontsize=12)
    ax6.set_title(f'R² Distribution', fontsize=14, fontweight='bold')
    ax6.grid(True, alpha=0.3, axis='y')
    ax6.legend()

    r2_mean = r2_valid.mean()
    r2_std = r2_valid.std()
    ax6.text(
        0.95, 0.95,
        f'μ = {r2_mean:.1f} mm²\nσ = {r2_std:.1f} mm²',
        transform=ax6.transAxes,
        fontsize=10,
        verticalalignment='top',
        horizontalalignment='right',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
    )

    # 总标题
    fig.suptitle(
        f'Position Reconstruction - 2D Density Maps (Run {run_id})\n'
        f'Total events: {len(df)} | Valid positions: {len(x_valid)}',
        fontsize=16,
        fontweight='bold',
        y=0.995,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.97])

    # 保存图片
    output_file = output_dir / f"run_{run_id}_position_2d_distributions.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"[✓] 2D 密度分布图已保存: {output_file}")

    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="导出位置重建数据并生成可视化"
    )
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
        print(f"[*] 生成位置分布图...")
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
        print(f"[*] 生成交互式 HTML 仪表板（原始版本）...")
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
        print(f"[*] 生成 2D 密度热力图仪表板（推荐）...")
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

    print(f"[✓] 完成！")


if __name__ == "__main__":
    main()
