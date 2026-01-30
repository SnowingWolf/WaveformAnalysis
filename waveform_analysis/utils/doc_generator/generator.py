"""
文档生成器 - 从代码自动生成文档

从 docstrings、类型提示和插件元数据中提取信息，
生成 Markdown/HTML/PDF 格式的文档。
"""

from datetime import datetime
import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from waveform_analysis.core.foundation.utils import exporter

if TYPE_CHECKING:
    from waveform_analysis.core.context import Context

export, __all__ = exporter()


@export
class DocGenerator:
    """从代码自动生成文档"""

    def __init__(self, ctx: Optional["Context"] = None):
        """
        初始化文档生成器

        Args:
            ctx: Context 实例（可选，用于提取插件信息）
        """
        self.ctx = ctx
        self.template_dir = Path(__file__).parent / "templates"
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
                    lstrip_blocks=True,
                )
                # 添加自定义函数（作为全局函数而不是过滤器）
                self._jinja_env.globals["now"] = lambda: datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except ImportError:
                raise ImportError(
                    "需要安装 jinja2 才能使用文档生成功能。\n" "运行: pip install jinja2"
                )
        return self._jinja_env

    def generate_api_reference(self, output_path: str, format: str = "markdown"):
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

        from .extractors import MetadataExtractor

        extractor = MetadataExtractor()

        # 提取 API 信息
        api_data = {
            "Context": extractor.extract_class_api(Context),
        }

        # 渲染模板
        if format == "markdown":
            template = self.jinja_env.get_template("api_reference.md.jinja2")
            content = template.render(api_data=api_data)
        elif format == "html":
            template = self.jinja_env.get_template("api_reference.html.jinja2")
            content = template.render(api_data=api_data)
        else:
            raise ValueError(f"不支持的格式: {format}")

        # 写入文件
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")

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
            from waveform_analysis.core.plugins import profiles

            self.ctx = Context()
            self.ctx.register(*profiles.cpu_default())

        from .extractors import MetadataExtractor

        extractor = MetadataExtractor()

        # 提取配置信息
        config_data = extractor.extract_plugin_configs(self.ctx)

        # 渲染模板
        template = self.jinja_env.get_template("config_reference.md.jinja2")
        content = template.render(config_data=config_data)

        # 写入文件
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")

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
                plugin_info["name"] = name
                standard_plugins.append(plugin_info)

        guide_data = {
            "plugin_base": plugin_base_api,
            "standard_plugins": standard_plugins[:3],  # 只显示前 3 个作为示例
        }

        # 渲染模板
        template = self.jinja_env.get_template("plugin_guide.md.jinja2")
        content = template.render(guide_data=guide_data)

        # 写入文件
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")

        print(f"✅ 插件开发指南已生成: {output_path}")

    def generate_all(self, output_dir: str = "docs"):
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

        self.generate_api_reference(str(output_path / "api_reference.md"))
        self.generate_config_reference(str(output_path / "config_reference.md"))
        self.generate_plugin_guide(str(output_path / "plugin_guide.md"))

        print("-" * 60)
        print(f"✅ 所有文档已生成到: {output_dir}")

    def _parse_dtype(self, dtype) -> str:
        """
        解析 dtype 为可读字符串

        Args:
            dtype: numpy dtype 或类型对象

        Returns:
            dtype 的字符串表示
        """
        if dtype is None:
            return "N/A"
        try:
            import numpy as np

            if isinstance(dtype, np.dtype):
                # 结构化 dtype，格式化字段
                if dtype.names:
                    fields = []
                    for name in dtype.names:
                        field_dtype = dtype.fields[name][0]
                        fields.append(f"('{name}', {field_dtype})")
                    return f"[{', '.join(fields)}]"
                return str(dtype)
            return str(dtype)
        except Exception:
            return str(dtype)

    def _parse_options(self, plugin) -> List[Dict[str, Any]]:
        """
        解析插件的配置选项，包含单位信息

        Args:
            plugin: 插件实例

        Returns:
            选项信息列表
        """
        options = []
        if not hasattr(plugin, "options"):
            return options

        for opt_name, opt in plugin.options.items():
            opt_info = {
                "name": opt_name,
                "default": getattr(opt, "default", None),
                "type": self._format_type(getattr(opt, "type", None)),
                "help": getattr(opt, "help", ""),
                "track": getattr(opt, "track", True),
                # 新增字段
                "unit": getattr(opt, "unit", None),
                "internal_unit": getattr(opt, "internal_unit", None),
                "choices": getattr(opt, "choices", None),
                "min_value": getattr(opt, "min_value", None),
                "max_value": getattr(opt, "max_value", None),
                "deprecated": getattr(opt, "deprecated", False),
                "deprecated_message": getattr(opt, "deprecated_message", ""),
                "alias": getattr(opt, "alias", None),
            }
            options.append(opt_info)

        return options

    def _format_type(self, type_obj) -> str:
        """
        格式化类型对象为字符串

        Args:
            type_obj: 类型对象

        Returns:
            类型的字符串表示
        """
        if type_obj is None:
            return "Any"
        if isinstance(type_obj, tuple):
            return " | ".join(t.__name__ if hasattr(t, "__name__") else str(t) for t in type_obj)
        if hasattr(type_obj, "__name__"):
            return type_obj.__name__
        return str(type_obj)

    def generate_plugin_doc(self, plugin, output_path: str):
        """
        使用统一模板为单个插件生成文档

        Args:
            plugin: 插件实例
            output_path: 输出文件路径

        Examples:
            >>> gen = DocGenerator(ctx)
            >>> plugin = ctx.get_plugin('waveforms')
            >>> gen.generate_plugin_doc(plugin, 'docs/plugins/waveforms.md')
        """
        template = self.jinja_env.get_template("plugin_doc.md.j2")

        # 构建插件数据
        plugin_data = {
            "provides": plugin.provides,
            "version": getattr(plugin, "version", "0.0.0"),
            "class_name": plugin.__class__.__name__,
            "description": getattr(plugin, "description", "")
            or inspect.getdoc(plugin.__class__)
            or "",
            "depends_on": [
                dep if isinstance(dep, str) else dep[0] for dep in (plugin.depends_on or [])
            ],
            "output_dtype": self._parse_dtype(getattr(plugin, "output_dtype", None)),
            "input_dtype": getattr(plugin, "input_dtype", {}),
            "save_when": getattr(plugin, "save_when", "never"),
            "output_kind": getattr(plugin, "output_kind", "static"),
            "options": self._parse_options(plugin),
        }

        content = template.render(plugin=plugin_data)

        # 写入文件
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")

        print(f"✅ 插件文档已生成: {output_path}")

    def generate_all_plugins(self, output_dir: str = "docs/plugins"):
        """
        为所有注册插件生成文档

        Args:
            output_dir: 输出目录

        Examples:
            >>> gen = DocGenerator(ctx)
            >>> gen.generate_all_plugins('docs/plugins/')
        """
        if self.ctx is None:
            from waveform_analysis.core.context import Context
            from waveform_analysis.core.plugins import profiles

            self.ctx = Context()
            self.ctx.register(*profiles.cpu_default())

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"开始生成插件文档到目录: {output_dir}")
        print("-" * 60)

        generated = 0
        for name, plugin in self.ctx._plugins.items():
            try:
                plugin_file = output_path / f"{name}.md"
                self.generate_plugin_doc(plugin, str(plugin_file))
                generated += 1
            except Exception as e:
                print(f"⚠️ 生成 {name} 文档失败: {e}")

        print("-" * 60)
        print(f"✅ 已生成 {generated}/{len(self.ctx._plugins)} 个插件文档到: {output_dir}")

        # 生成索引文件
        self._generate_plugin_index(output_path)

    def _generate_plugin_index(self, output_dir: Path):
        """
        生成插件索引文件

        Args:
            output_dir: 输出目录
        """
        if self.ctx is None:
            return

        index_content = ["# 插件索引\n"]
        index_content.append(f"> 共 {len(self.ctx._plugins)} 个插件\n\n")

        # 按类别分组（如果有的话）
        index_content.append("| 插件名 | 版本 | 描述 |\n")
        index_content.append("|--------|------|------|\n")

        for name, plugin in sorted(self.ctx._plugins.items()):
            version = getattr(plugin, "version", "0.0.0")
            desc = getattr(plugin, "description", "") or ""
            # 截断过长的描述
            if len(desc) > 50:
                desc = desc[:47] + "..."
            index_content.append(f"| [{name}]({name}.md) | {version} | {desc} |\n")

        index_file = output_dir / "index.md"
        index_file.write_text("".join(index_content), encoding="utf-8")
        print(f"✅ 插件索引已生成: {index_file}")
