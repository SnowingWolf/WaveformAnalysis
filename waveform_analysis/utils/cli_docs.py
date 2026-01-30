#!/usr/bin/env python
"""
WaveformAnalysis 文档生成工具 CLI

用法:
  waveform-docs generate plugins-auto     # 自动生成 builtin 插件文档
  waveform-docs check coverage            # 检查文档覆盖率
"""

import argparse
from pathlib import Path
import sys


def main():
    """CLI 主入口"""
    parser = argparse.ArgumentParser(
        description="WaveformAnalysis 文档生成工具",
        epilog="""
示例:
  # 自动生成 builtin 插件文档
  waveform-docs generate plugins-auto -o docs/plugins/builtin/auto/

  # 检查文档覆盖率
  waveform-docs check coverage --strict
""",
    )

    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # generate 子命令
    gen_parser = subparsers.add_parser("generate", help="生成文档")
    gen_parser.add_argument(
        "doc_type",
        choices=["plugins-auto"],
        help="文档类型",
    )
    gen_parser.add_argument("--output", "-o", type=str, help="输出路径（文件或目录）")
    gen_parser.add_argument(
        "--plugin",
        "-p",
        type=str,
        help="生成单个插件文档",
    )

    # check 子命令
    check_parser = subparsers.add_parser("check", help="检查文档")
    check_parser.add_argument(
        "check_type",
        choices=["coverage"],
        help="检查类型",
    )
    check_parser.add_argument(
        "--docs-dir",
        "-d",
        type=str,
        help="文档目录路径",
    )
    check_parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式（也检查 spec 质量）",
    )
    check_parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="有警告时也失败",
    )

    args = parser.parse_args()

    # 检查命令
    if not args.command:
        parser.print_help()
        return 0

    # 执行命令
    if args.command == "generate":
        return cmd_generate(args)
    elif args.command == "check":
        return cmd_check(args)

    return 0


def cmd_generate(args):
    """处理 generate 命令"""
    return generate_plugins_auto(args)


def generate_plugins_auto(args):
    """自动生成 builtin 插件文档"""
    try:
        from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator

        # 确定输出目录
        output_dir = args.output or "docs/plugins/builtin/auto"
        output_path = Path(output_dir)

        # 初始化生成器
        generator = PluginDocGenerator()

        # 加载内置插件
        count = generator.load_builtin_plugins()
        print(f"✅ 已加载 {count} 个内置插件")

        # 生成单个插件或所有插件
        if args.plugin:
            # 生成单个插件
            file_path = output_path / f"{args.plugin}.md"
            try:
                result = generator.generate_single(args.plugin, file_path)
                print(f"✅ 已生成: {result}")
            except ValueError as e:
                print(f"❌ 错误: {e}")
                return 1
        else:
            # 生成所有插件
            results = generator.generate_all(output_path)
            print(f"✅ 已生成 {len(results)} 个文档文件")
            print(f"   输出目录: {output_path}")

            # 列出生成的文件
            for _provides, path in sorted(results.items()):
                print(f"   - {path.name}")

        return 0

    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("提示: 运行 'pip install jinja2' 安装依赖")
        return 1

    except Exception as e:
        print(f"❌ 生成文档时出错: {e}")
        import traceback

        traceback.print_exc()
        return 1


def generate_docs(args):
    """生成文档（原有功能）"""
    try:
        from waveform_analysis.utils.doc_generator import DocGenerator

        # 初始化生成器
        ctx = None
        if args.with_context:
            from waveform_analysis.core.context import Context
            from waveform_analysis.core.plugins import profiles

            ctx = Context()
            ctx.register(*profiles.cpu_default())
            print("✅ 已加载 Context 和标准插件")

        generator = DocGenerator(ctx)

        # 确定输出路径
        output_path = args.output or "docs"

        # 生成文档
        if args.doc_type == "api":
            if not args.output:
                output_path = f"docs/api_reference.{args.format.replace('markdown', 'md')}"
            generator.generate_api_reference(output_path, format=args.format)

        elif args.doc_type == "config":
            if not args.output:
                output_path = "docs/config_reference.md"
            generator.generate_config_reference(output_path)

        elif args.doc_type == "plugins":
            if not args.output:
                output_path = "docs/plugin_guide.md"
            generator.generate_plugin_guide(output_path)

        elif args.doc_type == "all":
            if not args.output:
                output_path = "docs"
            generator.generate_all(output_path)

        print("\n✅ 文档生成成功")
        return 0

    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("提示: 运行 'pip install jinja2' 安装依赖")
        return 1

    except Exception as e:
        print(f"❌ 生成文档时出错: {e}")
        import traceback

        traceback.print_exc()
        return 1


def cmd_check(args):
    """处理 check 命令"""
    if args.check_type == "coverage":
        return check_coverage(args)
    return 0


def check_coverage(args):
    """检查文档覆盖率"""
    try:
        from waveform_analysis.utils.doc_coverage import DocCoverageChecker

        # 确定文档目录
        docs_dir = Path(args.docs_dir) if args.docs_dir else None

        # 如果指定了 docs_dir，auto_docs_dir 默认为 docs_dir/plugins/builtin/auto
        auto_docs_dir = None
        if docs_dir:
            auto_docs_dir = docs_dir / "plugins" / "builtin" / "auto"

        # 初始化检查器
        checker = DocCoverageChecker(docs_dir=docs_dir, auto_docs_dir=auto_docs_dir)

        # 执行检查
        report = checker.check_coverage(require_spec_quality=args.strict)

        # 打印报告
        checker.print_report(report)

        # 确定退出码
        if args.fail_on_warning:
            return 0 if len(report.issues) == 0 else 1
        return 0 if report.passed else 1

    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        return 1

    except Exception as e:
        print(f"❌ 检查覆盖率时出错: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
