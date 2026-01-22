#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WaveformAnalysis 文档生成工具 CLI

用法:
  waveform-docs generate api          # 生成 API 参考
  waveform-docs generate config       # 生成配置参考
  waveform-docs generate plugins      # 生成插件指南
  waveform-docs generate all          # 生成所有文档
"""

import argparse
import sys
from pathlib import Path


def main():
    """CLI 主入口"""
    parser = argparse.ArgumentParser(
        description='WaveformAnalysis 文档生成工具',
        epilog="""
示例:
  # 生成 API 参考文档
  waveform-docs generate api --output docs/api.md

  # 生成所有文档
  waveform-docs generate all --output docs/

  # 生成 HTML 格式
  waveform-docs generate api --format html --output docs/api.html
"""
    )

    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # generate 子命令
    gen_parser = subparsers.add_parser('generate', help='生成文档')
    gen_parser.add_argument(
        'doc_type',
        choices=['api', 'config', 'plugins', 'all'],
        help='文档类型'
    )
    gen_parser.add_argument(
        '--output', '-o',
        type=str,
        help='输出路径（文件或目录）'
    )
    gen_parser.add_argument(
        '--format', '-f',
        choices=['markdown', 'html'],
        default='markdown',
        help='输出格式（默认: markdown）'
    )
    gen_parser.add_argument(
        '--with-context',
        action='store_true',
        help='使用完整 Context 上下文（注册所有标准插件）'
    )

    args = parser.parse_args()

    # 检查命令
    if not args.command:
        parser.print_help()
        return 0

    # 执行命令
    if args.command == 'generate':
        return generate_docs(args)

    return 0


def generate_docs(args):
    """生成文档"""
    try:
        from waveform_analysis.utils.doc_generator import DocGenerator

        # 初始化生成器
        ctx = None
        if args.with_context:
            from waveform_analysis.core.context import Context
            from waveform_analysis.core.plugins.builtin.cpu import standard_plugins
            ctx = Context()
            ctx.register(*standard_plugins)  # 使用解包操作符
            print("✅ 已加载 Context 和标准插件")

        generator = DocGenerator(ctx)

        # 确定输出路径
        output_path = args.output or 'docs'

        # 生成文档
        if args.doc_type == 'api':
            if not args.output:
                output_path = f'docs/api_reference.{args.format.replace("markdown", "md")}'
            generator.generate_api_reference(output_path, format=args.format)

        elif args.doc_type == 'config':
            if not args.output:
                output_path = 'docs/config_reference.md'
            generator.generate_config_reference(output_path)

        elif args.doc_type == 'plugins':
            if not args.output:
                output_path = 'docs/plugin_guide.md'
            generator.generate_plugin_guide(output_path)

        elif args.doc_type == 'all':
            if not args.output:
                output_path = 'docs'
            generator.generate_all(output_path)

        print(f"\n✅ 文档生成成功")
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


if __name__ == '__main__':
    sys.exit(main())
