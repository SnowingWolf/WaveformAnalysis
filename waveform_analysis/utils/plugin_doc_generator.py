"""
插件文档生成器 - 从 PluginSpec 自动生成 Markdown 文档

本模块提供从插件元数据自动生成文档的功能：
- PluginDocInfo: 从插件提取的文档信息数据类
- PluginDocGenerator: 文档生成器，使用 Jinja2 模板渲染

用法:
    >>> from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator
    >>> generator = PluginDocGenerator()
    >>> generator.generate_all(Path("docs/plugins/reference/builtin/auto"))
"""

from dataclasses import dataclass, field, replace
import inspect
from pathlib import Path
import re
import shutil
import sys
from typing import Any

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
    units: str | None = None
    doc: str = ""
    deprecated: bool = False
    tracked: bool = True


@export
@dataclass
class OutputFieldInfo:
    """输出字段信息"""

    name: str
    dtype: str
    units: str | None = None
    doc: str = ""


@export
@dataclass
class DependencyDocumentationInfo:
    """Human-readable details for one plugin dependency."""

    name: str
    version_constraint: str = ""
    resolution: str = "declared"
    required_fields: list[str] = field(default_factory=list)
    description: str = ""


@export
@dataclass
class PluginDocumentationView:
    """从插件提取的文档信息"""

    name: str  # 类名
    provides: str  # 数据名
    version: str  # 版本
    description: str  # 描述
    category: str  # 类别 (data_loading, features, events...)
    accelerator: str  # 加速器 (cpu, jax, streaming)
    depends_on: list[str] = field(default_factory=list)  # 依赖列表
    config_options: list[ConfigOptionInfo] = field(default_factory=list)  # 配置选项
    output_fields: list[OutputFieldInfo] = field(default_factory=list)  # 输出字段
    output_kind: str = "structured_array"  # 输出类型
    supports_streaming: bool = False
    supports_parallel: bool = True
    supports_gpu: bool = False
    is_side_effect: bool = False
    module_path: str = ""  # 模块路径
    module_doc: str = ""
    dependency_details: list[DependencyDocumentationInfo] = field(default_factory=list)
    workflow_steps: list[str] = field(default_factory=list)
    execution_chain: list[str] = field(default_factory=list)
    execution_notes: list[str] = field(default_factory=list)
    output_summary: str = ""
    has_dynamic_dependencies: bool = False
    behavior_notes: list[str] = field(default_factory=list)
    field_notes: dict[str, str] = field(default_factory=dict)
    config_notes: dict[str, str] = field(default_factory=dict)
    cluster_contract: list[str] = field(default_factory=list)
    failure_modes: list[str] = field(default_factory=list)
    downstream_consumers: list[str] = field(default_factory=list)
    downstream_notes: list[str] = field(default_factory=list)
    agent_change_notes: list[str] = field(default_factory=list)
    overview: str = ""
    overview_paragraphs: list[str] = field(default_factory=list)
    usage_example: str = ""
    documentation_status: Any = None

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

    @property
    def summary(self) -> str:
        return " ".join(self.description.split())


# Compatibility import for callers that used the old internal data-class name.
PluginDocInfo = PluginDocumentationView


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
        >>> generator.generate_all(Path("docs/plugins/reference/builtin/auto"))
    """

    def __init__(self, template_dir: Path | None = None, *, published_agent_docs: Any = None):
        """初始化文档生成器

        Args:
            template_dir: 自定义模板目录，默认使用内置模板
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        self.template_dir = template_dir
        self._plugins: list[tuple[type, Any]] = []  # (plugin_class, instance)
        self._jinja_env = None
        self._web_jinja_env = None
        if published_agent_docs is None:
            from waveform_analysis.documentation import PublishedAgentDocRegistry

            published_agent_docs = PublishedAgentDocRegistry()
        self._published_agent_docs = published_agent_docs

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
                keep_trailing_newline=True,
            )
            self._jinja_env.filters["markdown_cell"] = _escape_markdown_cell
        return self._jinja_env

    def _get_web_jinja_env(self):
        """Return an isolated, autoescaping environment for HTML output."""
        if self._web_jinja_env is None:
            try:
                from jinja2 import Environment, FileSystemLoader, select_autoescape
            except ImportError as exc:
                raise ImportError(
                    "jinja2 is required for documentation generation. "
                    "Install it with: pip install jinja2"
                ) from exc
            self._web_jinja_env = Environment(
                loader=FileSystemLoader(str(self.template_dir)),
                autoescape=select_autoescape(enabled_extensions=("html", "xml"), default=True),
                trim_blocks=True,
                lstrip_blocks=True,
                keep_trailing_newline=True,
            )
        return self._web_jinja_env

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

    def register_plugin(self, plugin_class: type, instance: Any | None = None):
        """注册单个插件

        Args:
            plugin_class: 插件类
            instance: 插件实例（可选，如果不提供则自动创建）
        """
        if instance is None:
            instance = plugin_class()
        self._plugins.append((plugin_class, instance))

    def extract_doc_info(self, plugin_class: type, plugin: Any) -> PluginDocumentationView:
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
        module_doc = self._extract_module_doc(module_path)

        # Structured documentation extensions shared by Help, Markdown, and HTML.
        agent_doc = self._extract_agent_doc(plugin_class, plugin)
        compute_notes = self._extract_compute_notes(plugin)
        behavior_notes = agent_doc["behavior_notes"] or compute_notes
        has_dynamic_dependencies = self._has_dynamic_dependencies(plugin)
        dependency_details = self._build_dependency_details(
            depends_on,
            resolution="dynamic" if has_dynamic_dependencies else "declared",
            dependency_notes=agent_doc["dependency_notes"],
            dependency_fields=agent_doc["dependency_fields"],
        )
        output_summary = self._output_summary(plugin, output_kind, output_fields, description)
        workflow_steps = agent_doc["workflow_steps"]
        execution_chain = self._build_execution_chain(
            depends_on,
            provides,
            has_dynamic_dependencies=has_dynamic_dependencies,
        )
        raw_usage_example = getattr(plugin, "doc_usage_example", "") or ""
        usage_example = inspect.cleandoc(str(raw_usage_example)) if raw_usage_example else ""

        return PluginDocumentationView(
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
            module_doc=module_doc,
            dependency_details=dependency_details,
            workflow_steps=workflow_steps,
            execution_chain=execution_chain,
            execution_notes=agent_doc["execution_notes"],
            output_summary=output_summary,
            has_dynamic_dependencies=has_dynamic_dependencies,
            behavior_notes=behavior_notes,
            field_notes=agent_doc["field_notes"],
            config_notes=agent_doc["config_notes"],
            cluster_contract=agent_doc["cluster_contract"],
            failure_modes=agent_doc["failure_modes"],
            downstream_consumers=agent_doc["downstream_consumers"],
            downstream_notes=agent_doc["downstream_notes"],
            agent_change_notes=agent_doc["agent_change_notes"],
            overview=agent_doc["overview"],
            overview_paragraphs=agent_doc["overview_paragraphs"],
            usage_example=usage_example,
            documentation_status=agent_doc["documentation_status"],
        )

    @staticmethod
    def _extract_module_doc(module_path: str) -> str:
        """Extract the plugin module docstring for generated reference pages."""
        module = sys.modules.get(module_path)
        if module is None:
            return ""
        return inspect.getdoc(module) or ""

    def _extract_agent_doc(self, plugin_class: type, plugin: Any) -> dict[str, Any]:
        """Extract published narrative metadata, falling back to source agent_doc."""
        resolution = self._published_agent_docs.resolve_for_plugin(plugin_class, plugin)
        raw_doc = resolution.narrative.as_generator_fields()
        if not isinstance(raw_doc, dict):
            raw_doc = {}

        def list_value(key: str) -> list[str]:
            value = raw_doc.get(key, [])
            if value is None:
                return []
            if isinstance(value, str):
                return [value]
            if isinstance(value, list | tuple):
                return [str(item) for item in value]
            return [str(value)]

        def dict_value(key: str) -> dict[str, str]:
            value = raw_doc.get(key, {})
            if not isinstance(value, dict):
                return {}
            return {str(k): str(v) for k, v in value.items()}

        def str_value(key: str) -> str:
            value = raw_doc.get(key, "")
            if value is None:
                return ""
            return str(value)

        overview_value = str_value("overview")
        if overview_value.strip():
            overview_paragraphs = [p.strip() for p in overview_value.split("\n\n") if p.strip()]
        else:
            overview_paragraphs = []

        return {
            "overview": overview_value,
            "overview_paragraphs": overview_paragraphs,
            "behavior_notes": list_value("behavior_notes"),
            "workflow_steps": list_value("workflow_steps"),
            "execution_notes": list_value("execution_notes"),
            "dependency_notes": dict_value("dependency_notes"),
            "dependency_fields": (
                {
                    key: (
                        [str(item) for item in value]
                        if isinstance(value, list | tuple)
                        else [str(value)]
                    )
                    for key, value in (raw_doc.get("dependency_fields", {}) or {}).items()
                }
                if isinstance(raw_doc.get("dependency_fields", {}), dict)
                else {}
            ),
            "field_notes": dict_value("field_notes"),
            "config_notes": dict_value("config_notes"),
            "cluster_contract": list_value("cluster_contract"),
            "failure_modes": list_value("failure_modes"),
            "downstream_consumers": list_value("downstream_consumers"),
            "downstream_notes": list_value("downstream_notes"),
            "agent_change_notes": list_value("agent_change_notes"),
            "documentation_status": resolution.status,
        }

    @staticmethod
    def _extract_compute_notes(plugin: Any) -> list[str]:
        """Extract authored narrative paragraphs from the plugin compute docstring."""
        compute = type(plugin).__dict__.get("compute")
        doc = inspect.cleandoc(compute.__doc__) if compute is not None and compute.__doc__ else ""
        if not doc:
            return []
        section_header = re.compile(
            r"^(Args|Arguments|Parameters|Returns|Raises|Examples|Yields|Notes):\s*$",
            re.IGNORECASE,
        )
        narrative: list[str] = []
        paragraph: list[str] = []
        for raw_line in doc.splitlines():
            line = raw_line.strip()
            if section_header.match(line):
                break
            if not line:
                if paragraph:
                    narrative.append(" ".join(paragraph))
                    paragraph = []
                continue
            paragraph.append(line)
        if paragraph:
            narrative.append(" ".join(paragraph))
        return [note for note in narrative if note][:3]

    @staticmethod
    def _has_dynamic_dependencies(plugin: Any) -> bool:
        from waveform_analysis.core.plugins.core.base import Plugin

        return type(plugin).resolve_depends_on is not Plugin.resolve_depends_on

    @staticmethod
    def _dependency_parts(dependency: Any) -> tuple[str, str]:
        if isinstance(dependency, tuple):
            return str(dependency[0]), str(dependency[1]) if len(dependency) > 1 else ""
        return str(dependency), ""

    @classmethod
    def _build_dependency_details(
        cls,
        depends_on: list[Any],
        *,
        resolution: str,
        dependency_notes: dict[str, str] | None = None,
        dependency_fields: dict[str, list[str]] | None = None,
        producer_descriptions: dict[str, str] | None = None,
    ) -> list[DependencyDocumentationInfo]:
        dependency_notes = dependency_notes or {}
        dependency_fields = dependency_fields or {}
        producer_descriptions = producer_descriptions or {}
        return [
            DependencyDocumentationInfo(
                name=name,
                version_constraint=version,
                resolution=resolution,
                required_fields=list(dependency_fields.get(name, [])),
                description=dependency_notes.get(name) or producer_descriptions.get(name, ""),
            )
            for name, version in (cls._dependency_parts(dep) for dep in depends_on)
        ]

    @staticmethod
    def _build_execution_chain(
        depends_on: list[Any],
        provides: str,
        *,
        has_dynamic_dependencies: bool,
    ) -> list[str]:
        names = [str(dep[0] if isinstance(dep, tuple) else dep) for dep in depends_on]
        if not names and has_dynamic_dependencies:
            names = ["<runtime-resolved inputs>"]
        return [*names, provides]

    @staticmethod
    def _output_summary(
        plugin: Any,
        output_kind: str,
        output_fields: list[OutputFieldInfo],
        description: str,
    ) -> str:
        output_schema = getattr(plugin, "output_schema", None)
        schema_doc = getattr(output_schema, "doc", "") if output_schema is not None else ""
        if schema_doc:
            return str(schema_doc)
        if output_fields:
            names = ", ".join(field.name for field in output_fields[:8])
            suffix = ", ..." if len(output_fields) > 8 else ""
            return f"{output_kind} output with fields: {names}{suffix}."
        return description or f"{output_kind} plugin output."

    def enrich_documentation_views(
        self, views: list[PluginDocumentationView]
    ) -> list[PluginDocumentationView]:
        """Add producer descriptions and direct consumers from a plugin graph."""
        by_provides = {view.provides: view for view in views}
        consumers: dict[str, set[str]] = {name: set() for name in by_provides}
        for consumer in views:
            for dep in consumer.depends_on:
                dep_name, _ = self._dependency_parts(dep)
                if dep_name in consumers:
                    consumers[dep_name].add(consumer.provides)

        enriched: list[PluginDocumentationView] = []
        descriptions = {name: view.summary for name, view in by_provides.items()}
        for view in views:
            details = [
                replace(
                    detail,
                    description=detail.description or descriptions.get(detail.name, ""),
                )
                for detail in view.dependency_details
            ]
            downstream = sorted(
                set(view.downstream_consumers) | consumers.get(view.provides, set())
            )
            enriched.append(
                replace(view, dependency_details=details, downstream_consumers=downstream)
            )
        return enriched

    def apply_dependency_resolution(
        self,
        view: PluginDocumentationView,
        dependencies: list[Any],
        *,
        resolution: str,
        available_views: list[PluginDocumentationView] | None = None,
    ) -> PluginDocumentationView:
        """Return a view with run-specific dependencies without executing plugin data."""
        descriptions = {item.provides: item.summary for item in (available_views or [])}
        details = self._build_dependency_details(
            dependencies,
            resolution=resolution,
            producer_descriptions=descriptions,
        )
        return replace(
            view,
            depends_on=list(dependencies),
            dependency_details=details,
            execution_chain=self._build_execution_chain(
                list(dependencies), view.provides, has_dynamic_dependencies=False
            ),
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

    def _detect_accelerator(self, plugin_class: type) -> str:
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

    def _extract_config_options(self, plugin: Any) -> list[ConfigOptionInfo]:
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
                    tracked=getattr(opt, "track", True),
                )
            )

        return config_options

    def _extract_output_fields(self, plugin: Any) -> tuple[list[OutputFieldInfo], str]:
        """提取输出字段信息

        Args:
            plugin: 插件实例

        Returns:
            (输出字段列表, 输出类型)
        """
        output_schema = getattr(plugin, "output_schema", None)
        output_dtype = getattr(plugin, "output_dtype", None)
        output_fields = []
        output_kind = "unknown"

        if output_schema is not None:
            output_kind = output_schema.kind
            output_fields = [
                OutputFieldInfo(
                    name=field.name,
                    dtype=field.dtype,
                    units=field.units,
                    doc=field.doc,
                )
                for field in output_schema.fields
            ]
            return output_fields, output_kind

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

    def get_all_doc_info(self) -> list[PluginDocumentationView]:
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
        return self.enrich_documentation_views(doc_infos)

    def render_plugin_page(self, doc_info: PluginDocumentationView, profile: str = "auto") -> str:
        """渲染单个插件页面

        Args:
            doc_info: 插件文档信息
            profile: 文档画像（auto/agent）

        Returns:
            渲染后的 Markdown 内容
        """
        env = self._get_jinja_env()
        if profile == "agent":
            template_name = "plugin_page_agent.md.j2"
        else:
            template_name = "plugin_page.md.j2"
        template = env.get_template(template_name)
        return template.render(plugin=doc_info)

    def render_index_page(
        self, plugins: list[PluginDocumentationView], profile: str = "auto"
    ) -> str:
        """渲染插件索引页面

        Args:
            plugins: 插件文档信息列表
            profile: 文档画像（auto/agent）

        Returns:
            渲染后的 Markdown 内容
        """
        env = self._get_jinja_env()
        if profile == "agent":
            template_name = "plugin_index_agent.md.j2"
        else:
            template_name = "plugin_index.md.j2"
        template = env.get_template(template_name)

        # 按类别分组
        by_category: dict[str, list[PluginDocInfo]] = {}
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

    def render_plugin_html(self, doc_info: PluginDocumentationView) -> str:
        """Render one standalone plugin HTML page with escaped metadata."""
        return self._get_web_jinja_env().get_template("web/plugin.html.j2").render(plugin=doc_info)

    def render_index_html(self, plugins: list[PluginDocumentationView]) -> str:
        """Render the searchable static-site index."""
        return (
            self._get_web_jinja_env()
            .get_template("web/index.html.j2")
            .render(plugins=sorted(plugins, key=lambda item: item.provides))
        )

    def generate_web(self, output_dir: Path) -> dict[str, Path]:
        """Generate an offline HTML plugin reference site."""
        output_dir = Path(output_dir)
        plugin_dir = output_dir / "plugins"
        asset_dir = output_dir / "assets"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        asset_dir.mkdir(parents=True, exist_ok=True)
        plugins = self.get_all_doc_info()
        generated: dict[str, Path] = {}
        for plugin in plugins:
            path = plugin_dir / f"{plugin.provides}.html"
            path.write_text(self.render_plugin_html(plugin), encoding="utf-8")
            generated[plugin.provides] = path
        index_path = output_dir / "index.html"
        index_path.write_text(self.render_index_html(plugins), encoding="utf-8")
        generated["INDEX"] = index_path
        source_assets = self.template_dir / "web" / "assets"
        for name in ("site.css", "site.js"):
            target = asset_dir / name
            shutil.copyfile(source_assets / name, target)
            generated[f"asset:{name}"] = target
        return generated

    def generate_all(self, output_dir: Path, profile: str = "auto") -> dict[str, Path]:
        """生成所有文档

        Args:
            output_dir: 输出目录
            profile: 文档画像（auto/agent）

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
            content = self.render_plugin_page(doc_info, profile=profile)
            structure_errors = check_plugin_document_structure(content, profile)
            if structure_errors:
                raise ValueError(
                    f"Generated {doc_info.provides} documentation is invalid: "
                    + "; ".join(structure_errors)
                )
            file_path = output_dir / f"{doc_info.provides}.md"
            file_path.write_text(content, encoding="utf-8")
            generated_files[doc_info.provides] = file_path

        # 生成索引页面
        index_content = self.render_index_page(doc_infos, profile=profile)
        index_path = output_dir / "INDEX.md"
        index_path.write_text(index_content, encoding="utf-8")
        generated_files["INDEX"] = index_path

        return generated_files

    def generate_single(self, plugin_name: str, output_path: Path, profile: str = "auto") -> Path:
        """生成单个插件文档

        Args:
            plugin_name: 插件类名或 provides 名称
            output_path: 输出文件路径
            profile: 文档画像（auto/agent）

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
                content = self.render_plugin_page(doc_info, profile=profile)
                structure_errors = check_plugin_document_structure(content, profile)
                if structure_errors:
                    raise ValueError(
                        f"Generated {doc_info.provides} documentation is invalid: "
                        + "; ".join(structure_errors)
                    )
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(content, encoding="utf-8")
                return output_path

        raise ValueError(f"Plugin not found: {plugin_name}")


EXPECTED_SECTIONS = {
    "auto": ["Overview", "Configuration", "Output", "Usage"],
    "agent": [
        "Overview",
        "Configuration",
        "Output",
        "Usage",
        "Operational Notes",
        "Maintenance",
    ],
}

FRONTMATTER_FIELDS = (
    "schema_version",
    "document_type",
    "profile",
    "provides",
    "plugin_class",
    "module",
    "version",
    "summary",
    "depends_on",
    "output_kind",
    "generated",
)


def _escape_markdown_cell(value: Any) -> str:
    return str(value).replace("|", r"\|").replace("\n", "<br>")


@export
def check_plugin_document_structure(content: str, profile: str) -> list[str]:
    """Validate generated plugin Markdown section and Overview table structure."""
    errors: list[str] = []
    expected = EXPECTED_SECTIONS.get(profile)
    if expected is None:
        return [f"Unknown profile: {profile}"]
    if not content.startswith("---\n") or "\n---\n" not in content[4:]:
        errors.append("Missing YAML frontmatter")
    else:
        frontmatter = content.split("\n---\n", 1)[0][4:]
        keys = [line.split(":", 1)[0] for line in frontmatter.splitlines() if ":" in line]
        missing = [field for field in FRONTMATTER_FIELDS if field not in keys]
        extra = [key for key in keys if key not in FRONTMATTER_FIELDS]
        if missing:
            errors.append(f"Missing frontmatter fields: {missing!r}")
        if extra:
            errors.append(f"Unexpected frontmatter fields: {extra!r}")
        if f'profile: "{profile}"' not in frontmatter:
            errors.append(f"Frontmatter profile does not match {profile!r}")
    sections = re.findall(r"^## ([^#].*)$", content, flags=re.MULTILINE)
    if sections != expected:
        errors.append(f"Expected H2 sections {expected!r}, got {sections!r}")
    overview_start = content.find("## Overview")
    config_start = content.find("## Configuration")
    if overview_start < 0 or config_start < 0:
        return errors
    overview = content[overview_start:config_start]
    contract = overview.find("| Item | Value |")
    dependencies = overview.find(
        "| Dependency | Version Constraint | Resolution | Required Fields | Description |"
    )
    if contract < 0:
        errors.append("Overview is missing the Contract table")
    if dependencies < 0:
        errors.append("Overview is missing the Dependencies table")
    if contract >= 0 and dependencies >= 0 and contract > dependencies:
        errors.append("Contract table must precede Dependencies table")
    summary = overview[len("## Overview") : contract if contract >= 0 else len(overview)].strip()
    if not summary:
        errors.append("Overview summary must precede the Contract table")
    if "| Name | Type | Default | Unit | Tracked | Deprecated | Description |" not in content:
        errors.append("Configuration table header is missing")
    if "| Field | DType | Unit | Meaning |" not in content:
        errors.append("Output table header is missing")
    return errors


@export
def check_plugin_document(path: Path, profile: str) -> list[str]:
    """Validate a generated page; INDEX.md intentionally follows separate rules."""
    path = Path(path)
    if path.name == "INDEX.md":
        return []
    return check_plugin_document_structure(path.read_text(encoding="utf-8"), profile)
