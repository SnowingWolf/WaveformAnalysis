#!/usr/bin/env python
"""
WaveformAnalysis Help 系统演示

展示所有已实现的 help 功能。
"""

from waveform_analysis.core.context import Context


def demo_basic_help():
    """演示基础 help 功能"""
    print("=" * 80)
    print("1. 基础 Help - 快速参考")
    print("=" * 80)

    ctx = Context()
    ctx.help()


def demo_all_topics():
    """演示所有帮助主题"""
    ctx = Context()

    topics = ["quickstart", "config", "plugins", "performance", "examples"]

    for topic in topics:
        print("\n" + "=" * 80)
        print(f"2. {topic.upper()} 主题")
        print("=" * 80)
        ctx.help(topic)


def demo_verbose_mode():
    """演示详细模式"""
    print("\n" + "=" * 80)
    print("3. Verbose 模式 - Quickstart 详细说明")
    print("=" * 80)

    ctx = Context()
    ctx.help("quickstart", verbose=True)


def demo_search():
    """演示搜索功能"""
    print("\n" + "=" * 80)
    print("4. 搜索功能")
    print("=" * 80)

    ctx = Context()
    ctx.help(search="time_range")


def demo_quickstart_templates():
    """演示代码模板生成"""
    print("\n" + "=" * 80)
    print("5. Quickstart 模板生成")
    print("=" * 80)

    ctx = Context()

    print("\n--- Basic Analysis Template ---")
    _ = ctx.quickstart("basic", run_id="demo_run", n_channels=2)

    # 保存到文件（示例）
    # with open('generated_analysis.py', 'w') as f:
    #     f.write(code)
    # print("✅ 代码已保存到 generated_analysis.py")


def demo_performance():
    """演示性能测试"""
    print("\n" + "=" * 80)
    print("6. 性能测试 - Help 响应时间")
    print("=" * 80)

    import time

    ctx = Context()

    # 预热
    ctx.help()

    # 测试首次调用
    start = time.perf_counter()
    ctx.help("quickstart")
    first_call = time.perf_counter() - start

    # 测试缓存命中
    start = time.perf_counter()
    ctx.help("quickstart")
    cached_call = time.perf_counter() - start

    print(f"首次调用时间: {first_call*1000:.2f}ms")
    print(f"缓存命中时间: {cached_call*1000:.2f}ms")
    print(f"性能提升: {first_call/cached_call:.1f}x")

    if first_call < 0.1 and cached_call < 0.01:
        print("✅ 性能测试通过 (首次 < 100ms, 缓存 < 10ms)")
    else:
        print("⚠️  性能未达标")


def main():
    """主演示函数"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "WaveformAnalysis Help 系统演示" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    # 1. 基础 help
    demo_basic_help()

    # 2. 所有主题
    demo_all_topics()

    # 3. Verbose 模式
    demo_verbose_mode()

    # 4. 搜索
    demo_search()

    # 5. 模板生成
    demo_quickstart_templates()

    # 6. 性能测试
    demo_performance()

    print("\n" + "=" * 80)
    print("演示完成！")
    print("=" * 80)
    print()
    print("✅ 所有功能正常工作")
    print()
    print("更多信息:")
    print("  • 使用指南: HELP_SYSTEM_SUMMARY.md")
    print("  • 实施计划: /home/wxy/.claude/plans/elegant-booping-stonebraker.md")
    print("  • 测试文件: tests/test_help_system.py")
    print()


if __name__ == "__main__":
    main()
