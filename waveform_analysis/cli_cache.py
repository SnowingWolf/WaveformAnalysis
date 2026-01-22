# -*- coding: utf-8 -*-
"""
缓存管理命令行接口

提供 waveform-cache 命令用于管理缓存数据。
"""

import argparse
import sys
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    """创建命令行解析器"""
    parser = argparse.ArgumentParser(
        prog="waveform-cache",
        description="WaveformAnalysis 缓存管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查看缓存信息
  waveform-cache info --storage-dir ./strax_data

  # 详细统计
  waveform-cache stats --detailed --storage-dir ./strax_data

  # 诊断缓存问题
  waveform-cache diagnose --run run_001

  # 清理旧缓存（预览）
  waveform-cache clean --strategy oldest --days 30 --dry-run

  # 实际清理
  waveform-cache clean --strategy lru --size-mb 500
        """,
    )

    # 全局选项（在主解析器中定义，用于在子命令之前使用）
    parser.add_argument(
        "--storage-dir",
        type=str,
        default="./strax_data",
        help="缓存存储目录（默认: ./strax_data）"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细信息"
    )

    # 创建全局选项的 parent parser，用于在子命令之后使用
    global_parser = argparse.ArgumentParser(add_help=False)
    global_parser.add_argument(
        "--storage-dir",
        type=str,
        default="./strax_data",
        help="缓存存储目录（默认: ./strax_data）"
    )
    global_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细信息"
    )

    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # info 命令（添加 parents 以支持全局选项在子命令之后使用）
    info_parser = subparsers.add_parser("info", help="显示缓存概览", parents=[global_parser])
    info_parser.add_argument("--run", type=str, help="仅显示指定运行")
    info_parser.add_argument("--detailed", action="store_true", help="显示详细信息")

    # stats 命令（添加 parents 以支持全局选项在子命令之后使用）
    stats_parser = subparsers.add_parser("stats", help="显示缓存统计", parents=[global_parser])
    stats_parser.add_argument("--run", type=str, help="仅统计指定运行")
    stats_parser.add_argument("--detailed", action="store_true", help="显示详细统计")
    stats_parser.add_argument("--export", type=str, help="导出统计到文件（.json 或 .csv）")

    # diagnose 命令（添加 parents 以支持全局选项在子命令之后使用）
    diag_parser = subparsers.add_parser("diagnose", help="诊断缓存问题", parents=[global_parser])
    diag_parser.add_argument("--run", type=str, help="仅诊断指定运行")
    diag_parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题")
    diag_parser.add_argument("--dry-run", action="store_true", default=True,
                             help="仅预演修复操作（默认）")
    diag_parser.add_argument("--no-dry-run", action="store_false", dest="dry_run",
                             help="实际执行修复操作")

    # clean 命令（添加 parents 以支持全局选项在子命令之后使用）
    clean_parser = subparsers.add_parser("clean", help="清理缓存", parents=[global_parser])
    clean_parser.add_argument(
        "--strategy",
        choices=["lru", "oldest", "largest", "version", "integrity"],
        default="lru",
        help="清理策略（默认: lru）"
    )
    clean_parser.add_argument("--size-mb", type=float, help="目标释放空间（MB）")
    clean_parser.add_argument("--days", type=float, help="保留最近 N 天的数据")
    clean_parser.add_argument("--run", type=str, help="仅清理指定运行")
    clean_parser.add_argument("--data-type", type=str, help="仅清理指定数据类型")
    clean_parser.add_argument("--dry-run", action="store_true", default=True,
                              help="仅预演清理操作（默认）")
    clean_parser.add_argument("--no-dry-run", action="store_false", dest="dry_run",
                              help="实际执行清理操作")
    clean_parser.add_argument("--max-entries", type=int, help="最多删除的条目数")

    # list 命令（添加 parents 以支持全局选项在子命令之后使用）
    list_parser = subparsers.add_parser("list", help="列出缓存条目", parents=[global_parser])
    list_parser.add_argument("--run", type=str, help="按运行过滤")
    list_parser.add_argument("--data-type", type=str, help="按数据类型过滤")
    list_parser.add_argument("--min-size", type=int, help="最小大小（字节）")
    list_parser.add_argument("--max-size", type=int, help="最大大小（字节）")
    list_parser.add_argument("--limit", type=int, default=50, help="最多显示条目数（默认: 50）")

    return parser


def get_context(storage_dir: str):
    """获取 Context 实例"""
    from waveform_analysis.core.context import Context
    return Context(storage_dir=storage_dir)


def cmd_info(args):
    """info 命令处理"""
    ctx = get_context(args.storage_dir)

    from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer

    analyzer = CacheAnalyzer(ctx)
    analyzer.scan(verbose=args.verbose)

    if args.run:
        summary = analyzer.get_run_summary(args.run)
        print(f"\n运行 {args.run} 的缓存信息:")
        print(f"  条目数: {summary['total_entries']}")
        print(f"  总大小: {summary['total_size_human']}")
        print(f"  压缩条目: {summary['compressed_count']}")
        print(f"  数据类型: {', '.join(summary['data_types'])}")
    else:
        analyzer.print_summary(detailed=args.detailed)


def cmd_stats(args):
    """stats 命令处理"""
    ctx = get_context(args.storage_dir)

    from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer
    from waveform_analysis.core.storage.cache_statistics import CacheStatsCollector

    analyzer = CacheAnalyzer(ctx)
    analyzer.scan(verbose=False)

    collector = CacheStatsCollector(analyzer)
    stats = collector.collect(run_id=args.run)
    collector.print_summary(stats, detailed=args.detailed)

    if args.export:
        fmt = 'csv' if args.export.endswith('.csv') else 'json'
        collector.export_stats(stats, args.export, format=fmt)


def cmd_diagnose(args):
    """diagnose 命令处理"""
    ctx = get_context(args.storage_dir)

    from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer
    from waveform_analysis.core.storage.cache_diagnostics import CacheDiagnostics

    analyzer = CacheAnalyzer(ctx)
    analyzer.scan(verbose=False)

    diag = CacheDiagnostics(analyzer)
    issues = diag.diagnose(run_id=args.run, verbose=args.verbose)
    diag.print_report(issues)

    if args.fix and issues:
        print("\n" + "=" * 60)
        if args.dry_run:
            print("[Dry-Run 模式] 以下操作将被执行:")
        else:
            print("[执行模式] 正在修复问题:")

        result = diag.auto_fix(issues, dry_run=args.dry_run)
        print(f"\n总计: {result['total']}, 可修复: {result['fixable']}, "
              f"{'将修复' if args.dry_run else '已修复'}: {result['fixed']}")

        if args.dry_run:
            print("\n要实际执行修复，请添加 --no-dry-run 选项")


def cmd_clean(args):
    """clean 命令处理"""
    ctx = get_context(args.storage_dir)

    from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer
    from waveform_analysis.core.storage.cache_cleaner import CacheCleaner, CleanupStrategy

    analyzer = CacheAnalyzer(ctx)
    analyzer.scan(verbose=args.verbose)

    cleaner = CacheCleaner(analyzer)

    # 映射策略名称
    strategy_map = {
        'lru': CleanupStrategy.LRU,
        'oldest': CleanupStrategy.OLDEST,
        'largest': CleanupStrategy.LARGEST,
        'version': CleanupStrategy.VERSION_MISMATCH,
        'integrity': CleanupStrategy.FAILED_INTEGRITY,
    }
    strategy = strategy_map[args.strategy]

    # 创建清理计划
    cleaner.plan_cleanup(
        strategy=strategy,
        target_size_mb=args.size_mb,
        keep_recent_days=args.days,
        run_id=args.run,
        data_name=args.data_type,
        max_entries=args.max_entries,
    )

    if cleaner.plan.entry_count == 0:
        print("\n没有找到需要清理的缓存条目")
        return

    # 预览计划
    cleaner.preview_plan(detailed=args.verbose)

    # 执行清理
    if args.dry_run:
        print("\n[Dry-Run 模式] 以上条目将被删除")
        print("要实际执行清理，请添加 --no-dry-run 选项")
    else:
        print("\n正在执行清理...")
        result = cleaner.execute(dry_run=False)
        print(f"\n清理完成: 删除 {result['deleted']} 条目, "
              f"释放 {result['freed_human']}")


def cmd_list(args):
    """list 命令处理"""
    ctx = get_context(args.storage_dir)

    from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer

    analyzer = CacheAnalyzer(ctx)
    analyzer.scan(verbose=False)

    entries = analyzer.get_entries(
        run_id=args.run,
        data_name=args.data_type,
        min_size=args.min_size,
        max_size=args.max_size
    )

    if not entries:
        print("\n没有找到匹配的缓存条目")
        return

    print(f"\n找到 {len(entries)} 个缓存条目")
    if len(entries) > args.limit:
        print(f"（仅显示前 {args.limit} 个，使用 --limit 调整）")

    print("\n" + "-" * 80)
    print(f"{'Run ID':<20} {'Data Type':<20} {'Size':<12} {'Age':<10} {'Compressed'}")
    print("-" * 80)

    for entry in entries[:args.limit]:
        compressed = "Yes" if entry.compressed else "No"
        age = f"{entry.age_days:.1f}d"
        print(f"{entry.run_id:<20} {entry.data_name:<20} {entry.size_human:<12} {age:<10} {compressed}")

    print("-" * 80)

    total_size = sum(e.size_bytes for e in entries)
    print(f"\n总大小: {analyzer._format_size(total_size)}")


def main():
    """主入口函数"""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    try:
        # 检查存储目录
        storage_path = Path(args.storage_dir)
        if not storage_path.exists():
            print(f"警告: 存储目录不存在: {args.storage_dir}")
            print("将创建空的缓存目录...")
            storage_path.mkdir(parents=True, exist_ok=True)

        # 执行对应命令
        if args.command == "info":
            cmd_info(args)
        elif args.command == "stats":
            cmd_stats(args)
        elif args.command == "diagnose":
            cmd_diagnose(args)
        elif args.command == "clean":
            cmd_clean(args)
        elif args.command == "list":
            cmd_list(args)
        else:
            parser.print_help()
            return 1

        return 0

    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"\n错误: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
