"""
演示如何高效地批量绘制多个 peak 的波形

对比两种用法：
1. 直接调用（慢）- 每次都重新加载所有数据
2. 使用 create_peak_plotter（快）- 只加载一次数据
"""

from waveform_analysis.utils.visualization import create_peak_plotter, plot_peak_channels_with_sum


def example_slow_way(ctx, run_id, peak_ids):
    """
    慢速方法：每次调用都重新加载数据

    适用于：只绘制 1-2 个 peak
    缺点：每次都重新加载 wave_pool, records 等大数据
    """
    print("方法 1（慢）：直接调用，每次重新加载数据")
    for peak_id in peak_ids:
        fig, axes = plot_peak_channels_with_sum(
            peak_id=peak_id,
            context=ctx,
            run_id=run_id,
            pad=30,
            group_by="board_channel",
        )
        print(f"  绘制完成 peak_id={peak_id}")


def example_fast_way(ctx, run_id, peak_ids):
    """
    快速方法：预加载数据，然后快速绘制

    适用于：批量绘制多个 peak（3 个以上）
    优点：所有数据只加载一次，后续绘图非常快
    """
    print("方法 2（快）：使用 create_peak_plotter，数据只加载一次")

    # 步骤 1：创建绘图函数（会预加载所有数据）
    plot_func = create_peak_plotter(context=ctx, run_id=run_id)

    # 步骤 2：快速绘制多个 peak
    for peak_id in peak_ids:
        fig, axes = plot_func(peak_id=peak_id)
        print(f"  绘制完成 peak_id={peak_id}")


if __name__ == "__main__":
    # 使用示例
    from waveform_analysis.core.daq_analyzer import DAQAnalyzer

    # 初始化分析器
    analyzer = DAQAnalyzer()
    ctx = analyzer.context
    run_id = "your_run_id"

    # 假设你有一些要绘制的 peak IDs
    peak_ids_to_plot = [42, 43, 44, 45, 46]

    # 方法 1（慢）
    # example_slow_way(ctx, run_id, peak_ids_to_plot)

    # 方法 2（快）- 推荐用于批量绘制
    example_fast_way(ctx, run_id, peak_ids_to_plot)

    # 性能对比：
    # - 方法 1：如果每次加载数据需要 2 秒，绘制 5 个 peak 需要 5 * 2 = 10 秒
    # - 方法 2：加载数据 2 秒 + 绘制 5 个 peak（每个 0.1 秒）= 2.5 秒
    # 加速比：10 / 2.5 = 4 倍
