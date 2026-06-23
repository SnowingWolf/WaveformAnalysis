#!/usr/bin/env python
"""
批量配置增益工具

用于快速为所有 run 设置 gain_adc_per_pe 配置
"""

import argparse
from pathlib import Path

import yaml


def create_run_config(channels: list[int], gain_value: float, board: int = 0) -> dict:
    """创建 run_config 字典"""
    gain_config = {f"{board}:{ch}": gain_value for ch in channels}

    return {"plugins": {"df": {"gain_adc_per_pe": gain_config}}}


def apply_gain_to_runs(
    daq_root: str,
    channels: list[int],
    gain_value: float,
    board: int = 0,
    overwrite: bool = False,
    dry_run: bool = False,
):
    """为所有 run 应用增益配置"""
    daq_path = Path(daq_root)

    if not daq_path.exists():
        print(f"错误: DAQ 目录不存在: {daq_root}")
        return

    # 获取所有 run 目录
    run_dirs = sorted([d for d in daq_path.iterdir() if d.is_dir() and not d.name.startswith(".")])

    if not run_dirs:
        print(f"警告: 在 {daq_root} 下没有找到 run 目录")
        return

    print(f"找到 {len(run_dirs)} 个 run 目录")
    print(f"增益配置: board {board}, 通道 {channels}, 增益值 {gain_value} ADC/PE")
    print("-" * 80)

    # 生成配置
    run_config = create_run_config(channels, gain_value, board)

    created = 0
    updated = 0
    skipped = 0

    for run_dir in run_dirs:
        config_file = run_dir / "run_config.yaml"

        # 检查是否已存在
        if config_file.exists() and not overwrite:
            print(f"⊙ 跳过 {run_dir.name} (已存在，使用 --overwrite 强制覆盖)")
            skipped += 1
            continue

        if dry_run:
            action = "更新" if config_file.exists() else "创建"
            print(f"[试运行] {action} {run_dir.name}/run_config.yaml")
            continue

        # 写入配置
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(run_config, f, default_flow_style=False, allow_unicode=True)

        if config_file.exists():
            print(f"✓ 更新 {run_dir.name}/run_config.yaml")
            updated += 1
        else:
            print(f"✓ 创建 {run_dir.name}/run_config.yaml")
            created += 1

    print("-" * 80)
    print("总结:")
    print(f"  创建: {created} 个")
    print(f"  更新: {updated} 个")
    print(f"  跳过: {skipped} 个")


def main():
    parser = argparse.ArgumentParser(
        description="批量为 run 配置单光子增益",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 为通道 9-15 设置增益 200
  python set_gain_batch.py --channels 9-15 --gain 200

  # 为通道 0,1,2,3 设置增益 15
  python set_gain_batch.py --channels 0,1,2,3 --gain 15

  # 试运行（不实际写入文件）
  python set_gain_batch.py --channels 9-15 --gain 200 --dry-run

  # 强制覆盖已存在的配置
  python set_gain_batch.py --channels 9-15 --gain 200 --overwrite
        """,
    )

    parser.add_argument("--daq-root", default="DAQ", help="DAQ 根目录路径 (默认: DAQ)")
    parser.add_argument("--channels", required=True, help="通道列表，支持格式: '9-15' 或 '0,1,2,3'")
    parser.add_argument("--gain", type=float, required=True, help="增益值 (ADC/PE)")
    parser.add_argument("--board", type=int, default=0, help="板卡编号 (默认: 0)")
    parser.add_argument("--overwrite", action="store_true", help="覆盖已存在的配置文件")
    parser.add_argument("--dry-run", action="store_true", help="试运行，不实际写入文件")

    args = parser.parse_args()

    # 解析通道列表
    channels = []
    if "-" in args.channels:
        # 范围格式: 9-15
        start, end = map(int, args.channels.split("-"))
        channels = list(range(start, end + 1))
    elif "," in args.channels:
        # 列表格式: 0,1,2,3
        channels = [int(ch.strip()) for ch in args.channels.split(",")]
    else:
        # 单个通道
        channels = [int(args.channels)]

    print("=" * 80)
    print("批量配置增益工具")
    print("=" * 80)

    apply_gain_to_runs(
        daq_root=args.daq_root,
        channels=channels,
        gain_value=args.gain,
        board=args.board,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
