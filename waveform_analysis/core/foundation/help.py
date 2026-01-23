"""
Help 系统核心实现

从 docs/ 目录实时读取文档，保持文档一致性。
文档不可用时显示友好的错误提示。
"""

from typing import TYPE_CHECKING, Dict, Optional

from waveform_analysis.core.foundation.utils import exporter

if TYPE_CHECKING:
    from waveform_analysis.core.context import Context

export, __all__ = exporter()


@export
class HelpSystem:
    """核心 help 系统（从 docs/ 读取文档）"""

    def __init__(self, ctx: 'Context'):
        """
        初始化 Help 系统

        Args:
            ctx: Context 实例
        """
        self.ctx = ctx
        self._topics = {
            'quickstart': QuickstartHelp(),
            'config': ConfigHelp(),
            'plugins': PluginHelp(),
            'performance': PerformanceHelp(),
            'examples': ExamplesHelp(),
        }
        self._cache: Dict[tuple, str] = {}
        self._doc_reader = None  # 懒加载

    @property
    def doc_reader(self):
        """懒加载文档读取器"""
        if self._doc_reader is None:
            from .doc_reader import get_doc_reader
            self._doc_reader = get_doc_reader()
        return self._doc_reader

    def show(
        self,
        topic: Optional[str] = None,
        search: Optional[str] = None,
        verbose: bool = False
    ) -> str:
        """
        显示帮助信息

        Args:
            topic: 帮助主题 ('quickstart', 'config', 'plugins', 'performance', 'examples')
            search: 搜索关键词
            verbose: 显示详细信息

        Returns:
            帮助文本
        """
        # 搜索模式
        if search:
            return self._search(search)

        # 默认快速参考
        if topic is None:
            return self._quick_reference()

        # 主题模式
        if topic in self._topics:
            cache_key = (topic, verbose)
            if cache_key not in self._cache:
                self._cache[cache_key] = self._get_topic_content(topic, verbose)
            return self._cache[cache_key]

        # 未知主题
        return self._unknown_topic(topic)

    def _get_topic_content(self, topic: str, verbose: bool) -> str:
        """获取主题内容（从 docs/ 读取）"""
        # 尝试从 docs/ 读取
        content, from_docs = self.doc_reader.read_topic(
            topic, verbose, fallback=None
        )

        if from_docs and content:
            if verbose:
                content = content + "\n\n" + self._build_verbose_footer(topic)
            # 添加来源提示
            source_hint = "\n💡 文档来源: docs/ 目录 (实时同步)\n"
            return content + source_hint

        # 文档不可用，返回错误提示
        fallback = self._topics[topic].show()
        if verbose:
            fallback = fallback + "\n\n详细模式: 文档不可用，无法显示更多内容。\n"
        return fallback

    def _quick_reference(self) -> str:
        """默认快速参考"""
        return """
╔══════════════════════════════════════════════════════════════════════════════╗
║ WaveformAnalysis Context - 快速参考                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

📚 核心概念
  • Context: 插件系统调度器，管理依赖、配置、缓存
  • Plugin: 数据处理单元（RawFiles → Waveforms → Peaks）
  • Lineage: 自动血缘追踪，确保缓存一致性

🚀 快速开始
────────────────────────────────────────────────────────────────────────────────
  from waveform_analysis.core.context import Context
  from waveform_analysis.core.plugins.builtin.cpu import standard_plugins

  ctx = Context(storage_dir='./data')
  ctx.register(standard_plugins)
  ctx.set_config({'n_channels': 2})
  data = ctx.get_data('run_001', 'peaks')
────────────────────────────────────────────────────────────────────────────────

📖 帮助主题
  ctx.help('quickstart')   - 5分钟快速上手
  ctx.help('config')       - 配置管理详解
  ctx.help('plugins')      - 插件系统指南
  ctx.help('performance')  - 性能优化技巧
  ctx.help('examples')     - 常见场景示例

🔍 搜索功能
  ctx.help(search='time_range')  - 搜索相关方法和配置

💡 提示: 使用 verbose=True 查看详细说明
  ctx.help('quickstart', verbose=True)
"""

    def _search(self, query: str) -> str:
        """搜索功能"""
        return f"""
🔍 搜索 "{query}" 的结果:

⚠️  搜索功能将在后续版本中实现。

💡 临时解决方案:
  • 使用 dir(ctx) 查看所有方法
  • 使用 help(ctx.method_name) 查看方法文档
  • 使用 ctx.list_plugin_configs() 查看配置选项
"""

    def _unknown_topic(self, topic: str) -> str:
        """未知主题提示"""
        available = ', '.join(self._topics.keys())
        return f"""
❌ 未知主题: '{topic}'

可用主题: {available}

💡 使用 ctx.help() 查看快速参考
"""

    def _build_verbose_footer(self, topic: str) -> str:
        """详细模式下追加文档来源信息，确保内容更完整"""
        available_docs = self.doc_reader.list_available_docs().get(topic, [])
        if not available_docs:
            return "详细模式: 未找到可用文档清单。"

        lines = ["详细模式: 文档来源明细"]
        for doc_path in available_docs:
            lines.append(f"- docs/{doc_path}")
        return "\n".join(lines)


@export
class QuickstartHelp:
    """快速开始主题 - 文档不可用时的错误提示"""

    def show(self) -> str:
        return """
╔══════════════════════════════════════════════════════════════════╗
║ 快速开始指南                                                     ║
╚══════════════════════════════════════════════════════════════════╝

⚠️  文档文件不可用

请确保 docs/ 目录存在并包含以下文件:
  • docs/user-guide/QUICKSTART_GUIDE.md

可能的解决方案:
  1. 确认在项目根目录运行
  2. 检查 docs/ 目录是否存在
  3. 使用 pip install -e . 重新安装

🚀 快速代码模板:
  ctx.quickstart('basic')              # 基础分析流程

如需帮助，请参考 CLAUDE.md 文件。
"""


@export
class ConfigHelp:
    """配置管理主题 - 文档不可用时的错误提示"""

    def show(self) -> str:
        return """
╔══════════════════════════════════════════════════════════════════╗
║ 配置管理指南                                                     ║
╚══════════════════════════════════════════════════════════════════╝

⚠️  文档文件不可用

请确保 docs/ 目录存在并包含以下文件:
  • docs/features/context/CONFIGURATION.md

🔧 常用配置命令:
  ctx.list_plugin_configs()            # 查看所有配置选项
  ctx.show_config()                    # 查看当前配置
  ctx.set_config({'n_channels': 2})    # 设置配置

如需帮助，请参考 CLAUDE.md 文件。
"""


@export
class PluginHelp:
    """插件系统主题 - 文档不可用时的错误提示"""

    def show(self) -> str:
        return """
╔══════════════════════════════════════════════════════════════════╗
║ 插件系统指南                                                     ║
╚══════════════════════════════════════════════════════════════════╝

⚠️  文档文件不可用

请确保 docs/ 目录存在并包含以下文件:
  • docs/features/plugin/README.md
  • docs/features/plugin/SIMPLE_PLUGIN_GUIDE.md

📦 常用插件命令:
  ctx.list_provided_data()             # 查看可用数据类型
  ctx.plot_lineage('peaks')            # 可视化依赖关系
  ctx.register(plugin)                 # 注册插件

如需帮助，请参考 CLAUDE.md 文件。
"""


@export
class PerformanceHelp:
    """性能优化主题 - 文档不可用时的错误提示"""

    def show(self) -> str:
        return """
╔══════════════════════════════════════════════════════════════════╗
║ 性能优化指南                                                     ║
╚══════════════════════════════════════════════════════════════════╝

⚠️  文档文件不可用

请确保 docs/ 目录存在并包含以下文件:
  • docs/features/advanced/EXECUTOR_MANAGER_GUIDE.md
  • docs/features/advanced/CACHE.md
  • docs/features/advanced/PROGRESS_TRACKING_GUIDE.md

⚡ 常用优化技巧:
  • 跳过波形加载: load_waveforms=False (节省 70-80%)
  • 调整块大小: set_config({'chunksize': 5000})
  • 启用统计: Context(enable_stats=True)

如需帮助，请参考 CLAUDE.md 文件。
"""


@export
class ExamplesHelp:
    """常见场景示例主题 - 文档不可用时的错误提示"""

    def show(self) -> str:
        return """
╔══════════════════════════════════════════════════════════════════╗
║ 常见场景示例                                                     ║
╚══════════════════════════════════════════════════════════════════╝

⚠️  文档文件不可用

请确保 docs/ 目录存在并包含以下文件:
  • docs/user-guide/EXAMPLES_GUIDE.md
  • docs/features/context/PREVIEW_EXECUTION.md
  • docs/features/context/LINEAGE_VISUALIZATION_GUIDE.md

🎯 快速代码模板:
  ctx.quickstart('basic')              # 基础分析流程

📁 完整示例程序:
  • examples/basic_analysis.py
  • examples/config_management_example.py

如需帮助，请参考 CLAUDE.md 文件。
"""
