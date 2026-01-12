# -*- coding: utf-8 -*-
"""
命令行接口
"""

import argparse
import sys
from pathlib import Path

from waveform_analysis import WaveformDataset
from waveform_analysis.utils.daq import DAQAnalyzer


def main():
    """主命令行入口"""
    parser = argparse.ArgumentParser(
        description="Waveform Analysis - 波形数据处理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 处理单个数据集
  waveform-process --run-name 50V_OV_circulation_20thr --output results.csv
  
  # 指定时间窗口
  waveform-process --run-name 50V_OV_circulation_20thr --time-window 200
  
  # 详细输出
  waveform-process --run-name 50V_OV_circulation_20thr --verbose
        """,
    )

    parser.add_argument(
        "--run-name",
        "--char",
        type=str,
        dest="run_name",
        required=False,
        help="数据集标识符（目录名）。当使用 --show-daq 时可省略。",
    )

    parser.add_argument("--n-channels", type=int, default=2, help="处理的通道数（默认: 2）")

    parser.add_argument("--start-channel", type=int, default=6, help="起始通道索引（默认: 6）")

    parser.add_argument("--time-window", type=float, default=100, help="事件配对时间窗口（ns，默认: 100）")

    parser.add_argument("--output", type=str, help="输出文件路径（可选）")

    parser.add_argument("--verbose", action="store_true", help="显示详细信息")

    # DAQ 扫描选项
    parser.add_argument("--scan-daq", action="store_true", help="扫描 DAQ 目录并导出 JSON 报告（会忽略其它处理选项）")
    parser.add_argument("--daq-root", type=str, default="DAQ", help="DAQ 根目录（默认: DAQ）")
    parser.add_argument("--daq-out", type=str, default="daq_analysis.json", help="DAQ 扫描结果输出路径")

    # CLI 显示 DAQ 表格
    parser.add_argument("--show-daq", type=str, help="显示指定运行的 DAQ 通道详情（run name）")
    parser.add_argument("--show-daq-files", action="store_true", help="在显示中包含每个通道的文件明细")

    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    args = parser.parse_args()

    # 创建数据集
    if args.verbose:
        print(f"处理数据集: {args.run_name}")
        print(f"通道数: {args.n_channels}")
        print(f"时间窗口: {args.time_window} ns")

    try:
        # 若为普通数据处理（非 --show-daq），则 --run-name 为必需
        if not args.show_daq and not args.run_name:
            print("错误: --run-name 是必需的（除非使用 --show-daq）", file=sys.stderr)
            return 2

        # DAQ 扫描分支
        if args.scan_daq:
            analyzer = DAQAnalyzer(args.daq_root)
            analyzer.scan_all_runs()
            out = analyzer.save_to_json(args.daq_out)
            if out is None:
                print("DAQ 扫描或保存失败", file=sys.stderr)
                return 1
            if args.verbose:
                print(f"DAQ 扫描完成，结果保存到: {out}")
            return 0

        # CLI 显示单个运行的 DAQ 信息
        if args.show_daq:
            analyzer = DAQAnalyzer(args.daq_root)
            analyzer.scan_all_runs()
            analyzer.display_run_channel_details(args.show_daq, show_files=args.show_daq_files)
            return 0

        # 正常数据处理分支
        dataset = WaveformDataset(
            run_name=args.run_name, n_channels=args.n_channels, start_channel_slice=args.start_channel
        )

        # 执行处理流程
        (
            dataset.load_raw_data()
            .extract_waveforms()
            .structure_waveforms()
            .build_waveform_features()
            .build_dataframe()
            .group_events(time_window_ns=args.time_window)
            .pair_events()
        )

        # 获取结果
        df_paired = dataset.get_paired_events()

        if args.verbose:
            print("\n处理完成！")
            print(f"配对事件数: {len(df_paired)}")

        # 保存结果
        if args.output:
            output_path = Path(args.output)
            if output_path.suffix == ".parquet":
                df_paired.to_parquet(output_path)
            else:
                df_paired.to_csv(output_path, index=False)

            if args.verbose:
                print(f"结果已保存到: {output_path}")
        else:
            dataset.save_results()
            if args.verbose:
                print(f"结果已保存到: outputs/{args.char}_paired.csv")

        return 0

    except FileNotFoundError as e:
        print(f"错误: 数据文件未找到 - {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
