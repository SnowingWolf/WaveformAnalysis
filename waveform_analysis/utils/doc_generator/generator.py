"""
文档生成器 - 从代码自动生成文档

从 docstrings、类型提示和插件元数据中提取信息，
生成 Markdown/HTML/PDF 格式的文档。
"""

from typing import Optional, Dict, Any, List, Type
import inspect
from pathlib import Path
from datetime import datetime

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


@export
class DocGenerator:
    """从代码自动生成文档"""

    def __init__(self, ctx: Optional['Context'] = None):
        """
        初始化文档生成器

        Args:
            ctx: Context 实例（可选，用于提取插件信息）
        """
        self.ctx = ctx
        self.template_dir = Path(__file__).parent / 'templates'
        self._jinja_env = None

    @property
    def jinja_env(self):
        """延迟初始化 Jinja2 环境"""
        if self._jinja_env is None:
            try:
                from jinja2 import Environment, FileSystemLoader
                self._jinja_env = Environment(
                    loader=FileSystemLoader(str(self.template_dir)),
                    trim_blocks=True,
                    lstrip_blocks=True
                )
                # 添加自定义函数（作为全局函数而不是过滤器）
                self._jinja_env.globals['now'] = lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            except ImportError:
                raise ImportError(
                    "需要安装 jinja2 才能使用文档生成功能。\n"
                    "运行: pip install jinja2"
                )
        return self._jinja_env

    def generate_api_reference(
        self,
        output_path: str,
        format: str = 'markdown'
    ):
        """
        生成 API 参考文档

        Args:
            output_path: 输出文件路径
            format: 输出格式 ('markdown', 'html')

        Examples:
            >>> gen = DocGenerator()
            >>> gen.generate_api_reference('docs/api_reference.md')
        """
        from waveform_analysis.core.context import Context
        from waveform_analysis.core.dataset import WaveformDataset
        from .extractors import MetadataExtractor

        extractor = MetadataExtractor()

        # 提取 API 信息
        api_data = {
            'Context': extractor.extract_class_api(Context),
            'WaveformDataset': extractor.extract_class_api(WaveformDataset),
        }

        # 渲染模板
        if format == 'markdown':
            template = self.jinja_env.get_template('api_reference.md.jinja2')
            content = template.render(api_data=api_data)
        elif format == 'html':
            template = self.jinja_env.get_template('api_reference.html.jinja2')
            content = template.render(api_data=api_data)
        else:
            raise ValueError(f"不支持的格式: {format}")

        # 写入文件
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding='utf-8')

        print(f"✅ API 参考已生成: {output_path}")

    def generate_config_reference(self, output_path: str):
        """
        生成配置参考文档

        Args:
            output_path: 输出文件路径

        Examples:
            >>> gen = DocGenerator(ctx)
            >>> gen.generate_config_reference('docs/config_reference.md')
        """
        if self.ctx is None:
            from waveform_analysis.core.context import Context
            from waveform_analysis.core.plugins.builtin import standard_plugins
            self.ctx = Context()
            self.ctx.register(standard_plugins)

        from .extractors import MetadataExtractor
        extractor = MetadataExtractor()

        # 提取配置信息
        config_data = extractor.extract_plugin_configs(self.ctx)

        # 渲染模板
        template = self.jinja_env.get_template('config_reference.md.jinja2')
        content = template.render(config_data=config_data)

        # 写入文件
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding='utf-8')

        print(f"✅ 配置参考已生成: {output_path}")

    def generate_plugin_guide(self, output_path: str):
        """
        生成插件开发指南

        Args:
            output_path: 输出文件路径

        Examples:
            >>> gen = DocGenerator()
            >>> gen.generate_plugin_guide('docs/plugin_guide.md')
        """
        from waveform_analysis.core.plugins.core.base import Plugin
        from .extractors import MetadataExtractor

        extractor = MetadataExtractor()

        # 提取插件基类信息
        plugin_base_api = extractor.extract_class_api(Plugin)

        # 提取标准插件示例
        standard_plugins = []
        if self.ctx:
            for name, plugin in self.ctx._plugins.items():
                plugin_info = extractor.extract_plugin_metadata(plugin)
                plugin_info['name'] = name
                standard_plugins.append(plugin_info)

        guide_data = {
            'plugin_base': plugin_base_api,
            'standard_plugins': standard_plugins[:3],  # 只显示前 3 个作为示例
        }

        # 渲染模板
        template = self.jinja_env.get_template('plugin_guide.md.jinja2')
        content = template.render(guide_data=guide_data)

        # 写入文件
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding='utf-8')

        print(f"✅ 插件开发指南已生成: {output_path}")

    def generate_all(self, output_dir: str = 'docs'):
        """
        生成所有文档

        Args:
            output_dir: 输出目录

        Examples:
            >>> gen = DocGenerator(ctx)
            >>> gen.generate_all('docs')
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"开始生成文档到目录: {output_dir}")
        print("-" * 60)

        self.generate_api_reference(str(output_path / 'api_reference.md'))
        self.generate_config_reference(str(output_path / 'config_reference.md'))
        self.generate_plugin_guide(str(output_path / 'plugin_guide.md'))

        print("-" * 60)
        print(f"✅ 所有文档已生成到: {output_dir}")
