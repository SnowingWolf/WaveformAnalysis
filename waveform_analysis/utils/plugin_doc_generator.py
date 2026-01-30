"""
插件文档生成器 - 从 PluginSpec 自动生成 Markdown 文档

本模块提供从插件元数据自动生成文档的功能：
- PluginDocInfo: 从插件提取的文档信息数据类
- PluginDocGenerator: 文档生成器，使用 Jinja2 模板渲染

用法:
    >>> from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator
    >>> generator = PluginDocGenerator()
    >>> generator.generate_all(Path("docs/plugins/builtin/auto"))
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

import numpy as np

from waveform_analysis.core.foundation.utils import exporter

export, __all__ = exporter()


# 插件类别映射规则
CATEGORY_KEYWORDS = {
    "data_loading": ["raw", "files", "loader", "reader"],
    "waveform_processing": ["waveform", "st_waveform", "filtered", "wave"],
    "feature_extraction": ["feature", "peak", "hit", "charge", "height", "width"],
    "event_analysis": ["event", "group", "pair", "coincidence"],
    "data_export": ["dataframe", "df", "export", "frame"],
    "signal_processing": ["filter", "signal", "fft", "smooth"],
    "cache_analysis": ["cache", "storage", "analysis"],
    "records": ["record"],
}

# 类别显示名称
CATEGORY_DISPLAY_NAMES = {
    "data_loading": "数据加载",
    "waveform_processing": "波形处理",
    "feature_extraction": "特征提取",
    "event_analysis": "事件分析",
    "data_export": "数据导出",
    "signal_processing": "信号处理",
    "cache_analysis": "缓存分析",
    "records": "记录处理",
    "other": "其他",
}


@export
@dataclass
class ConfigOptionInfo:
    """配置选项信息"""

    name: str
    type: str
    default: Any
    units: Optional[str] = None
    doc: str = ""
    deprecated: bool = False


@export
@dataclass
class OutputFieldInfo:
    """输出字段信息"""

    name: str
    dtype: str
    units: Optional[str] = None
    doc: str = ""


@export
@dataclass
class PluginDocInfo:
    """从插件提取的文档信息"""

    name: str  # 类名
    provides: str  # 数据名
    version: str  # 版本
    description: str  # 描述
    category: str  # 类别 (data_loading, features, events...)
    accelerator: str  # 加速器 (cpu, jax, streaming)
    depends_on: List[str] = field(default_factory=list)  # 依赖列表
    config_options: List[ConfigOptionInfo] = field(default_factory=list)  # 配置选项
    output_fields: List[OutputFieldInfo] = field(default_factory=list)  # 输出字段
    output_kind: str = "structured_array"  # 输出类型
    supports_streaming: bool = False
    supports_parallel: bool = True
    supports_gpu: bool = False
    is_side_effect: bool = False
    module_path: str = ""  # 模块路径

    @property
    def category_display(self) -> str:
        """获取类别显示名称"""
        return CATEGORY_DISPLAY_NAMES.get(self.category, self.category)

    @property
    def accelerator_display(self) -> str:
        """获取加速器显示名称"""
        mapping = {
            "cpu": "CPU (NumPy/SciPy)",
            "jax": "JAX (GPU)",
            "streaming": "Streaming",
        }
        return mapping.get(self.accelerator, self.accelerator)


@export
class PluginDocGenerator:
    """从 PluginSpec 生成文档

    使用 Jinja2 模板从插件元数据生成 Markdown 文档。

    Attributes:
        template_dir: 模板目录路径
        plugins: 已加载的插件列表

    Examples:
        >>> generator = PluginDocGenerator()
        >>> generator.load_builtin_plugins()
        >>> generator.generate_all(Path("docs/plugins/builtin/auto"))
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """初始化文档生成器

        Args:
            template_dir: 自定义模板目录，默认使用内置模板
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        self.template_dir = template_dir
        self._plugins: List[Tuple[Type, Any]] = []  # (plugin_class, instance)
        self._jinja_env = None

    def _get_jinja_env(self):
        """获取 Jinja2 环境（延迟加载）"""
        if self._jinja_env is None:
            try:
                from jinja2 import Environment, FileSystemLoader
            except ImportError:
                raise ImportError(
                    "jinja2 is required for documentation generation. "
                    "Install it with: pip install jinja2"
                )

            self._jinja_env = Environment(
                loader=FileSystemLoader(str(self.template_dir)),
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._jinja_env

    def load_builtin_plugins(self) -> int:
        """加载所有内置插件

        Returns:
            加载的插件数量
        """
        from waveform_analysis.core.plugins.builtin import cpu

        # 获取所有导出的插件类
        plugin_classes = []
        seen_provides: set = set()

        for name in cpu.__all__:
            obj = getattr(cpu, name, None)
            if obj is None:
                continue
            # 检查是否是 Plugin 子类
            if isinstance(obj, type) and hasattr(obj, "provides") and hasattr(obj, "compute"):
                plugin_classes.append(obj)

        # 实例化插件（去重）
        self._plugins = []
        for cls in plugin_classes:
            try:
                instance = cls()
                provides = getattr(instance, "provides", None)
                if provides and provides not in seen_provides:
                    self._plugins.append((cls, instance))
                    seen_provides.add(provides)
            except Exception:
                # 跳过无法实例化的插件
                pass

        return len(self._plugins)

    def register_plugin(self, plugin_class: Type, instance: Optional[Any] = None):
        """注册单个插件

        Args:
            plugin_class: 插件类
            instance: 插件实例（可选，如果不提供则自动创建）
        """
        if instance is None:
            instance = plugin_class()
        self._plugins.append((plugin_class, instance))

    def extract_doc_info(self, plugin_class: Type, plugin: Any) -> PluginDocInfo:
        """从插件提取文档信息

        Args:
            plugin_class: 插件类
            plugin: 插件实例

        Returns:
            PluginDocInfo 实例
        """
        # 基本信息
        name = plugin_class.__name__
        provides = getattr(plugin, "provides", "unknown")
        version = getattr(plugin, "version", "0.0.0")

        # 描述：优先使用 description 属性，其次使用 docstring
        description = getattr(plugin, "description", "")
        if not description and plugin_class.__doc__:
            # 提取 docstring 的第一段
            doc_lines = plugin_class.__doc__.strip().split("\n\n")
            description = doc_lines[0].strip()

        # 检测类别
        category = self._detect_category(provides, name)

        # 检测加速器
        accelerator = self._detect_accelerator(plugin_class)

        # 依赖
        depends_on = list(getattr(plugin, "depends_on", []))

        # 配置选项
        config_options = self._extract_config_options(plugin)

        # 输出字段
        output_fields, output_kind = self._extract_output_fields(plugin)

        # 能力
        supports_streaming = getattr(plugin, "output_kind", "static") == "stream"
        is_side_effect = getattr(plugin, "is_side_effect", False)

        # 模块路径
        module_path = plugin_class.__module__

        return PluginDocInfo(
            name=name,
            provides=provides,
            version=version,
            description=description,
            category=category,
            accelerator=accelerator,
            depends_on=depends_on,
            config_options=config_options,
            output_fields=output_fields,
            output_kind=output_kind,
            supports_streaming=supports_streaming,
            is_side_effect=is_side_effect,
            module_path=module_path,
        )

    def _detect_category(self, provides: str, class_name: str) -> str:
        """检测插件类别

        Args:
            provides: 插件提供的数据名
            class_name: 插件类名

        Returns:
            类别名称
        """
        search_text = f"{provides} {class_name}".lower()

        for category, keywords in CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in search_text:
                    return category

        return "other"

    def _detect_accelerator(self, plugin_class: Type) -> str:
        """检测插件加速器类型

        Args:
            plugin_class: 插件类

        Returns:
            加速器类型 (cpu, jax, streaming)
        """
        module = plugin_class.__module__

        if ".streaming." in module or ".streaming" in module:
            return "streaming"
        elif ".jax." in module or ".jax" in module:
            return "jax"
        else:
            return "cpu"

    def _extract_config_options(self, plugin: Any) -> List[ConfigOptionInfo]:
        """提取配置选项信息

        Args:
            plugin: 插件实例

        Returns:
            配置选项列表
        """
        options = getattr(plugin, "options", {})
        config_options = []

        for name, opt in options.items():
            # 获取类型名称
            opt_type = getattr(opt, "type", None)
            if opt_type is not None:
                type_name = opt_type.__name__ if hasattr(opt_type, "__name__") else str(opt_type)
            else:
                type_name = "any"

            # 获取默认值
            default = getattr(opt, "default", None)

            # 获取文档
            doc = getattr(opt, "help", "") or ""

            # 获取单位
            units = getattr(opt, "unit", None)

            # 检查是否弃用
            deprecated = getattr(opt, "deprecated", False)

            config_options.append(
                ConfigOptionInfo(
                    name=name,
                    type=type_name,
                    default=default,
                    units=units,
                    doc=doc,
                    deprecated=deprecated,
                )
            )

        return config_options

    def _extract_output_fields(self, plugin: Any) -> Tuple[List[OutputFieldInfo], str]:
        """提取输出字段信息

        Args:
            plugin: 插件实例

        Returns:
            (输出字段列表, 输出类型)
        """
        output_dtype = getattr(plugin, "output_dtype", None)
        output_fields = []
        output_kind = "unknown"

        if output_dtype is None:
            return output_fields, output_kind

        # 处理字符串类型注解
        if isinstance(output_dtype, str):
            output_kind = output_dtype
            return output_fields, output_kind

        # 处理 NumPy dtype
        try:
            dtype = np.dtype(output_dtype)
            if dtype.names is not None:
                # 结构化数组
                output_kind = "structured_array"
                for name in dtype.names:
                    field_dtype = dtype.fields[name][0]
                    output_fields.append(
                        OutputFieldInfo(
                            name=name,
                            dtype=str(field_dtype),
                        )
                    )
            else:
                # 简单数组
                output_kind = "array"
                output_fields.append(
                    OutputFieldInfo(
                        name="value",
                        dtype=str(dtype),
                    )
                )
        except Exception:
            output_kind = str(output_dtype)

        return output_fields, output_kind

    def get_all_doc_info(self) -> List[PluginDocInfo]:
        """获取所有插件的文档信息

        Returns:
            PluginDocInfo 列表
        """
        doc_infos = []
        for plugin_class, instance in self._plugins:
            try:
                doc_info = self.extract_doc_info(plugin_class, instance)
                doc_infos.append(doc_info)
            except Exception:
                # 跳过提取失败的插件
                pass
        return doc_infos

    def render_plugin_page(self, doc_info: PluginDocInfo) -> str:
        """渲染单个插件页面

        Args:
            doc_info: 插件文档信息

        Returns:
            渲染后的 Markdown 内容
        """
        env = self._get_jinja_env()
        template = env.get_template("plugin_page.md.j2")
        return template.render(plugin=doc_info)

    def render_index_page(self, plugins: List[PluginDocInfo]) -> str:
        """渲染插件索引页面

        Args:
            plugins: 插件文档信息列表

        Returns:
            渲染后的 Markdown 内容
        """
        env = self._get_jinja_env()
        template = env.get_template("plugin_index.md.j2")

        # 按类别分组
        by_category: Dict[str, List[PluginDocInfo]] = {}
        for plugin in plugins:
            category = plugin.category
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(plugin)

        # 排序类别
        category_order = [
            "data_loading",
            "waveform_processing",
            "feature_extraction",
            "signal_processing",
            "event_analysis",
            "data_export",
            "cache_analysis",
            "records",
            "other",
        ]
        sorted_categories = []
        for cat in category_order:
            if cat in by_category:
                sorted_categories.append((cat, by_category[cat]))
        # 添加未知类别
        for cat, plugins_list in by_category.items():
            if cat not in category_order:
                sorted_categories.append((cat, plugins_list))

        return template.render(
            plugins=plugins,
            by_category=sorted_categories,
            category_names=CATEGORY_DISPLAY_NAMES,
        )

    def generate_all(self, output_dir: Path) -> Dict[str, Path]:
        """生成所有文档

        Args:
            output_dir: 输出目录

        Returns:
            生成的文件路径字典 {provides: path}
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 获取所有插件信息
        doc_infos = self.get_all_doc_info()

        generated_files = {}

        # 生成各插件页面
        for doc_info in doc_infos:
            content = self.render_plugin_page(doc_info)
            file_path = output_dir / f"{doc_info.provides}.md"
            file_path.write_text(content, encoding="utf-8")
            generated_files[doc_info.provides] = file_path

        # 生成索引页面
        index_content = self.render_index_page(doc_infos)
        index_path = output_dir / "INDEX.md"
        index_path.write_text(index_content, encoding="utf-8")
        generated_files["INDEX"] = index_path

        return generated_files

    def generate_single(self, plugin_name: str, output_path: Path) -> Path:
        """生成单个插件文档

        Args:
            plugin_name: 插件类名或 provides 名称
            output_path: 输出文件路径

        Returns:
            生成的文件路径

        Raises:
            ValueError: 如果找不到指定插件
        """
        # 查找插件
        for plugin_class, instance in self._plugins:
            if (
                plugin_class.__name__ == plugin_name
                or getattr(instance, "provides", None) == plugin_name
            ):
                doc_info = self.extract_doc_info(plugin_class, instance)
                content = self.render_plugin_page(doc_info)
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(content, encoding="utf-8")
                return output_path

        raise ValueError(f"Plugin not found: {plugin_name}")
