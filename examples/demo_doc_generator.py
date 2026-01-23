#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WaveformAnalysis 文档生成器演示

展示如何使用 Python API 生成文档。
"""

from waveform_analysis.utils.doc_generator import DocGenerator
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import standard_plugins


def demo_basic_usage():
    """基础用法：不带 Context"""
    print("=" * 80)
    print("1. 基础用法 - 生成 API 参考（不含插件信息）")
    print("=" * 80)

    gen = DocGenerator()

    # 生成 Markdown 格式
    gen.generate_api_reference('test_output/api_basic.md')

    print("\n✅ 完成！查看 test_output/api_basic.md\n")


def demo_with_context():
    """高级用法：带完整 Context（包含所有插件）"""
    print("=" * 80)
    print("2. 高级用法 - 包含所有插件信息")
    print("=" * 80)

    # 创建 Context 并注册所有标准插件
    ctx = Context()
    ctx.register(*standard_plugins)
    print(f"✅ 已注册 {len(ctx._plugins)} 个插件")

    # 创建生成器
    gen = DocGenerator(ctx)

    # 生成所有文档
    gen.generate_api_reference('test_output/api_full.md')
    gen.generate_config_reference('test_output/config.md')
    gen.generate_plugin_guide('test_output/plugin_guide.md')

    print("\n✅ 完成！查看 test_output/ 目录\n")


def demo_html_output():
    """生成 HTML 格式文档"""
    print("=" * 80)
    print("3. HTML 格式输出")
    print("=" * 80)

    gen = DocGenerator()

    # 生成 HTML
    gen.generate_api_reference('test_output/api.html', format='html')

    print("\n✅ 完成！在浏览器中打开 test_output/api.html\n")


def demo_all_at_once():
    """一键生成所有文档"""
    print("=" * 80)
    print("4. 一键生成所有文档")
    print("=" * 80)

    # 创建完整 Context
    ctx = Context()
    ctx.register(*standard_plugins)

    # 一键生成
    gen = DocGenerator(ctx)
    gen.generate_all('test_output/complete_docs')

    print("\n✅ 完成！查看 test_output/complete_docs/ 目录\n")


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "WaveformAnalysis 文档生成器演示" + " " * 26 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    # 演示 1: 基础用法
    demo_basic_usage()

    # 演示 2: 带 Context
    demo_with_context()

    # 演示 3: HTML 输出
    demo_html_output()

    # 演示 4: 一键生成所有
    demo_all_at_once()

    print("=" * 80)
    print("演示完成！")
    print("=" * 80)
    print()
    print("📚 生成的文档类型：")
    print("  • API 参考 (Markdown/HTML) - Context 完整 API")
    print("  • 配置参考 (Markdown) - 所有插件的配置选项")
    print("  • 插件开发指南 (Markdown) - Plugin 基类和示例")
    print()
    print("🔧 使用场景：")
    print("  • 发布新版本前更新文档")
    print("  • 为自定义插件生成文档")
    print("  • 集成到 CI/CD 流程")
    print()
    print("💡 提示：")
    print("  • 使用 --with-context 获取完整插件信息")
    print("  • 支持 Markdown 和 HTML 格式")
    print("  • 文档与代码自动同步，无需手动维护")
    print()


if __name__ == '__main__':
    main()
