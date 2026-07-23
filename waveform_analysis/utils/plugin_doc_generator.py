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
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any
from urllib.parse import quote
import warnings

from markupsafe import Markup
import numpy as np

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.documentation.field_notes import dtype_field_notes_for

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
    documentation_completeness: int | None = None
    dag_impact: int | None = None

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


@dataclass(frozen=True)
class _WebLineageNode:
    """One positioned node in the generated, documentation-only DAG."""

    node_id: str
    label: str
    href: str | None
    placeholder: bool
    x: int
    y: int
    width: int
    height: int
    documentation_completeness: int | None
    dag_impact: int | None
    tooltip: str
    aria_label: str


@dataclass(frozen=True)
class _WebLineageEdge:
    """A rendered dependency wire between two web-lineage nodes."""

    source_id: str
    target_id: str
    path: str


@dataclass(frozen=True)
class _WebLineageGraph:
    """Template-ready static SVG graph for the plugin reference website."""

    title: str
    description: str
    view_box: str
    width: int
    height: int
    nodes: list[_WebLineageNode]
    edges: list[_WebLineageEdge]
    isolated_nodes: list[_WebLineageNode]
    global_focus_href: str | None = None


@dataclass(frozen=True)
class _WebPluginSet:
    """A canonical execution plugin set rendered on the static index."""

    name: str
    label: str
    plugins: list[PluginDocumentationView]


class _DefaultDocumentationContext:
    """Restricted context for resolving documentation-only default dependencies."""

    def __init__(self, plugins: dict[str, Any]):
        self._plugins = plugins
        self.config: dict[str, Any] = {}

    def get_config(self, plugin: Any, key: str) -> Any:
        option = getattr(plugin, "options", {}).get(key)
        return getattr(option, "default", self.config.get(key))


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
        dtype_notes = dtype_field_notes_for(str(getattr(plugin, "provides", "")))
        output_fields = []
        output_kind = "unknown"

        if output_schema is not None:
            output_kind = output_schema.kind
            output_fields = [
                OutputFieldInfo(
                    name=field.name,
                    dtype=field.dtype,
                    units=field.units,
                    doc=field.doc or dtype_notes.get(field.name, ""),
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
                            doc=dtype_notes.get(name, ""),
                        )
                    )
            else:
                # 简单数组
                output_kind = "array"
                output_fields.append(
                    OutputFieldInfo(
                        name="value",
                        dtype=str(dtype),
                        doc=dtype_notes.get("value", ""),
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

    @classmethod
    def _dependency_names(
        cls,
        plugin: PluginDocumentationView,
        dependencies_by_provides: dict[str, list[str]] | None = None,
    ) -> list[str]:
        dependencies = (
            dependencies_by_provides.get(plugin.provides, plugin.depends_on)
            if dependencies_by_provides is not None
            else plugin.depends_on
        )
        return [cls._dependency_parts(dependency)[0] for dependency in dependencies]

    def _default_dependency_map(self) -> dict[str, list[str]]:
        """Resolve dynamic dependencies with plugin defaults and no data access."""
        plugins = {str(instance.provides): instance for _, instance in self._plugins}
        context = _DefaultDocumentationContext(plugins)
        dependencies: dict[str, list[str]] = {}
        for _, plugin in self._plugins:
            provides = str(plugin.provides)
            try:
                resolved = plugin.resolve_depends_on(context, run_id=None)
            except TypeError:
                resolved = plugin.resolve_depends_on(context)
            except Exception as exc:
                raise ValueError(
                    f"Could not resolve default documentation dependencies for {provides!r}"
                ) from exc
            dependencies[provides] = [self._dependency_parts(item)[0] for item in resolved]
        return dependencies

    @staticmethod
    def _coverage(items: list[Any], documented) -> float:
        if not items:
            return 1.0
        return sum(bool(documented(item)) for item in items) / len(items)

    def _documentation_completeness(
        self,
        plugin: PluginDocumentationView,
        dependencies_by_provides: dict[str, list[str]] | None = None,
    ) -> int:
        """Score authored documentation fields without inspecting runtime data."""
        weighted_scores: list[tuple[float, float]] = [
            (10.0, float(bool(plugin.summary))),
            (10.0, float(bool(plugin.overview_paragraphs or plugin.overview))),
            (20.0, float(bool(plugin.workflow_steps))),
            (15.0, float(bool(plugin.usage_example))),
        ]

        if plugin.config_options:
            weighted_scores.append(
                (
                    15.0,
                    self._coverage(
                        plugin.config_options,
                        lambda option: plugin.config_notes.get(option.name) or option.doc,
                    ),
                )
            )

        if plugin.output_fields:
            weighted_scores.extend(
                [
                    (10.0, float(bool(plugin.output_summary))),
                    (
                        10.0,
                        self._coverage(
                            plugin.output_fields,
                            lambda field: plugin.field_notes.get(field.name) or field.doc,
                        ),
                    ),
                ]
            )
        else:
            weighted_scores.append((20.0, float(bool(plugin.output_summary))))

        dependency_names = self._dependency_names(plugin, dependencies_by_provides)
        if dependency_names:
            descriptions = {detail.name: detail.description for detail in plugin.dependency_details}
            weighted_scores.append(
                (10.0, self._coverage(dependency_names, lambda name: descriptions.get(name)))
            )

        total_weight = sum(weight for weight, _ in weighted_scores)
        earned = sum(weight * fraction for weight, fraction in weighted_scores)
        return round(100 * earned / total_weight) if total_weight else 0

    def _with_web_scores(
        self,
        plugins: list[PluginDocumentationView],
        dependencies_by_provides: dict[str, list[str]] | None = None,
    ) -> list[PluginDocumentationView]:
        """Attach independent documentation and graph-impact scores for web output."""
        by_provides = {plugin.provides: plugin for plugin in plugins}
        consumers: dict[str, set[str]] = {name: set() for name in by_provides}
        for plugin in plugins:
            for dependency in self._dependency_names(plugin, dependencies_by_provides):
                if dependency in consumers:
                    consumers[dependency].add(plugin.provides)

        def downstream_count(provides: str) -> int:
            seen: set[str] = set()
            pending = list(consumers[provides])
            while pending:
                consumer = pending.pop()
                if consumer in seen:
                    continue
                seen.add(consumer)
                pending.extend(consumers.get(consumer, ()))
            return len(seen)

        direct_counts = {name: len(names) for name, names in consumers.items()}
        transitive_counts = {name: downstream_count(name) for name in consumers}
        max_direct = max(direct_counts.values(), default=0)
        max_transitive = max(transitive_counts.values(), default=0)

        scored = []
        for plugin in plugins:
            direct_component = direct_counts[plugin.provides] / max_direct if max_direct else 0.0
            transitive_component = (
                transitive_counts[plugin.provides] / max_transitive if max_transitive else 0.0
            )
            impact = round(100 * (0.4 * direct_component + 0.6 * transitive_component))
            scored.append(
                replace(
                    plugin,
                    documentation_completeness=self._documentation_completeness(
                        plugin, dependencies_by_provides
                    ),
                    dag_impact=impact,
                )
            )
        return scored

    @staticmethod
    def _web_plugin_sets(plugins: list[PluginDocumentationView]) -> list[_WebPluginSet]:
        """Group documentation views by the canonical execution plugin sets."""
        from waveform_analysis.core.plugins.plugin_sets import PLUGIN_SETS

        by_provides = {plugin.provides: plugin for plugin in plugins}
        assigned: set[str] = set()
        groups: list[_WebPluginSet] = []
        for name, factory in PLUGIN_SETS.items():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                provides = [str(plugin.provides) for plugin in factory()]
            duplicates = assigned.intersection(provides)
            if duplicates:
                raise ValueError(f"Plugin set membership is ambiguous for {sorted(duplicates)!r}")
            assigned.update(provides)
            members = [
                by_provides[provides_name]
                for provides_name in provides
                if provides_name in by_provides
            ]
            if members:
                groups.append(
                    _WebPluginSet(
                        name=name,
                        label=f"Plugin Set: {name.replace('_', ' ').title()}",
                        plugins=members,
                    )
                )

        remaining = sorted(
            (plugin for plugin in plugins if plugin.provides not in assigned),
            key=lambda plugin: plugin.provides,
        )
        if remaining:
            groups.append(_WebPluginSet(name="other", label="Other Plugins", plugins=remaining))
        return groups

    def _build_web_lineage_graph(
        self,
        plugins: list[PluginDocumentationView],
        *,
        link_prefix: str,
        focus: str | None = None,
        dependencies_by_provides: dict[str, list[str]] | None = None,
    ) -> _WebLineageGraph:
        """Build an escaped-template-ready dependency graph from static doc views."""
        by_provides = {plugin.provides: plugin for plugin in plugins}
        consumers: dict[str, set[str]] = {name: set() for name in by_provides}
        for plugin in plugins:
            for dependency in self._dependency_names(plugin, dependencies_by_provides):
                if dependency in consumers:
                    consumers[dependency].add(plugin.provides)

        edge_names: list[tuple[str, str]] = []
        isolated_names: set[str] = set()
        if focus is None:
            edge_names = [
                (dependency, plugin.provides)
                for plugin in plugins
                for dependency in self._dependency_names(plugin, dependencies_by_provides)
                if dependency in by_provides
            ]
            visible_names = {name for edge in edge_names for name in edge}
            isolated_names = set(by_provides) - visible_names
            title = "Plugin Lineage"
            description = (
                "Declared builtin plugin dependencies. Isolated plugins and runtime-resolved "
                "inputs are listed outside the graph."
            )
        else:
            target = by_provides[focus]
            visible_names = {focus}
            dependencies = self._dependency_names(target, dependencies_by_provides)
            for dependency in dependencies:
                if dependency in by_provides:
                    visible_names.add(dependency)
                    edge_names.append((dependency, focus))
            for consumer in sorted(consumers[focus]):
                visible_names.add(consumer)
                edge_names.append((focus, consumer))
            title = "Local Lineage"
            description = "Direct declared plugin inputs and consumers."

        node_ids = {name: f"plugin:{name}" for name in visible_names}
        known_edges = [
            (node_ids[source], node_ids[target])
            for source, target in edge_names
            if source in node_ids and target in node_ids
        ]
        incoming: dict[str, set[str]] = {node_id: set() for node_id in node_ids.values()}
        for source, target in known_edges:
            incoming[target].add(source)

        depths = {node_id: 0 for node_id, sources in incoming.items() if not sources}
        for _ in range(len(node_ids)):
            changed = False
            for source, target in known_edges:
                if source not in depths:
                    continue
                next_depth = depths[source] + 1
                if next_depth > depths.get(target, -1):
                    depths[target] = next_depth
                    changed = True
            if not changed:
                break
        for node_id in node_ids.values():
            depths.setdefault(node_id, 0)

        layers: dict[int, list[str]] = {}
        for name, node_id in node_ids.items():
            layers.setdefault(depths[node_id], []).append(name)
        for names in layers.values():
            names.sort(key=lambda name: (name not in by_provides, name))

        node_width = 220
        node_height = 76
        x_gap = 92
        y_gap = 108
        margin = 36
        max_layer_size = max((len(names) for names in layers.values()), default=1)
        max_depth = max(layers, default=0)
        canvas_width = margin * 2 + (max_depth + 1) * node_width + max_depth * x_gap
        canvas_height = margin * 2 + max_layer_size * node_height + (max_layer_size - 1) * y_gap

        nodes: list[_WebLineageNode] = []
        positions: dict[str, tuple[int, int]] = {}
        for depth, names in sorted(layers.items()):
            layer_height = len(names) * node_height + max(0, len(names) - 1) * y_gap
            start_y = margin + (canvas_height - 2 * margin - layer_height) // 2
            for index, name in enumerate(names):
                node_id = node_ids[name]
                x = margin + depth * (node_width + x_gap)
                y = start_y + index * (node_height + y_gap)
                positions[node_id] = (x, y)
                plugin = by_provides[name]
                placeholder = False
                label = name
                if len(label) > 28:
                    label = label[:25] + "..."
                documentation_completeness = plugin.documentation_completeness
                dag_impact = plugin.dag_impact
                tooltip = (
                    f"{plugin.provides}. Documentation completeness "
                    f"{documentation_completeness}/100; DAG impact {dag_impact}/100."
                )
                aria_label = tooltip + " Open plugin documentation."
                href = f"{link_prefix}{plugin.provides}.html"
                nodes.append(
                    _WebLineageNode(
                        node_id=node_id,
                        label=label,
                        href=href,
                        placeholder=placeholder,
                        x=x,
                        y=y,
                        width=node_width,
                        height=node_height,
                        documentation_completeness=documentation_completeness,
                        dag_impact=dag_impact,
                        tooltip=tooltip,
                        aria_label=aria_label,
                    )
                )

        edges = []
        for source, target in known_edges:
            source_x, source_y = positions[source]
            target_x, target_y = positions[target]
            start_x = source_x + node_width
            start_y = source_y + node_height // 2
            end_x = target_x
            end_y = target_y + node_height // 2
            bend = max(32, (end_x - start_x) // 2)
            path = (
                f"M {start_x} {start_y} C {start_x + bend} {start_y}, "
                f"{end_x - bend} {end_y}, {end_x} {end_y}"
            )
            edges.append(_WebLineageEdge(source, target, path))

        isolated_nodes = []
        for name in sorted(isolated_names):
            plugin = by_provides[name]
            documentation_completeness = plugin.documentation_completeness
            dag_impact = plugin.dag_impact
            tooltip = (
                f"{plugin.provides}. No declared builtin dependencies or consumers. "
                f"Documentation completeness {documentation_completeness}/100; "
                f"DAG impact {dag_impact}/100."
            )
            isolated_nodes.append(
                _WebLineageNode(
                    node_id=f"plugin:{name}",
                    label=name,
                    href=f"{link_prefix}{plugin.provides}.html",
                    placeholder=False,
                    x=0,
                    y=0,
                    width=0,
                    height=0,
                    documentation_completeness=documentation_completeness,
                    dag_impact=dag_impact,
                    tooltip=tooltip,
                    aria_label=tooltip + " Open plugin documentation.",
                )
            )

        return _WebLineageGraph(
            title=title,
            description=description,
            view_box=f"0 0 {canvas_width} {canvas_height}",
            width=canvas_width,
            height=canvas_height,
            nodes=nodes,
            edges=edges,
            isolated_nodes=isolated_nodes,
            global_focus_href=(
                f"../index.html?focus={quote(focus)}" if focus is not None else None
            ),
        )

    def _build_default_lineage_model(
        self,
        plugins: list[PluginDocumentationView],
        dependencies_by_provides: dict[str, list[str]],
    ) -> Any:
        """Build the same port-level model used by runtime Plotly lineage views."""
        from waveform_analysis.core.foundation.model import build_lineage_graph

        root_name = "__plugin_docs_root__"
        views_by_provides = {plugin.provides: plugin for plugin in plugins}
        instances = {str(instance.provides): instance for _, instance in self._plugins}

        def lineage_for(provides: str, visiting: set[str]) -> dict[str, Any]:
            view = views_by_provides[provides]
            if provides in visiting:
                return {"plugin_class": "CircularDependency", "depends_on": {}}
            dependencies = {
                dependency: lineage_for(dependency, visiting | {provides})
                for dependency in dependencies_by_provides.get(provides, [])
                if dependency in views_by_provides
            }
            return {
                "plugin_class": view.name,
                "description": view.description,
                "provides": provides,
                "config": {},
                "depends_on": dependencies,
            }

        lineage = {
            "plugin_class": "DocumentationRoot",
            "description": "Synthetic root for the default builtin plugin graph.",
            "depends_on": {
                provides: lineage_for(provides, set()) for provides in views_by_provides
            },
        }
        model = build_lineage_graph(lineage, root_name, instances)
        model.nodes.pop(root_name, None)
        model.edges = [
            edge
            for edge in model.edges
            if edge.source_node_id != root_name and edge.target_node_id != root_name
        ]
        return model

    def _render_global_plotly_html(self, lineage_graph: _WebLineageGraph) -> str:
        """Render a compact, clickable plugin-only overview with Plotly.

        The port-level renderer is intentionally reserved for the selected plugin's
        direct neighborhood. Rendering every port on the overview makes even the
        default builtin graph hard to scan.
        """
        try:
            import plotly.graph_objects as go
        except ImportError as exc:
            raise ImportError("plotly is required for the plugins-web lineage view.") from exc

        positions = {
            node.node_id: (node.x + node.width / 2, node.y + node.height / 2)
            for node in lineage_graph.nodes
        }
        node_shapes = []
        edge_traces = []
        annotations = []
        for node in lineage_graph.nodes:
            x, y = positions[node.node_id]
            node_shapes.append(
                {
                    "type": "rect",
                    "x0": node.x,
                    "y0": node.y,
                    "x1": node.x + node.width,
                    "y1": node.y + node.height,
                    "fillcolor": "#ffffff",
                    "line": {"color": "#087f5b", "width": 1.5},
                    "layer": "below",
                }
            )
            annotations.append(
                {
                    "x": x,
                    "y": y + 13,
                    "text": f"<b>{node.label}</b><br><span style='font-size:11px'>Docs {node.documentation_completeness} · Impact {node.dag_impact}</span>",
                    "showarrow": False,
                    "align": "center",
                    "font": {"size": 13, "color": "#17201d"},
                }
            )

        for edge in lineage_graph.edges:
            start = positions[edge.source_id]
            end = positions[edge.target_id]
            start_x, start_y = start[0] + 110, start[1]
            end_x, end_y = end[0] - 110, end[1]
            curve_offset = min(16, max(8, abs(end_y - start_y) * 0.08))
            if end_y < start_y:
                curve_offset = -curve_offset
            midpoint = (
                (start_x + end_x) / 2,
                (start_y + end_y) / 2 + curve_offset,
            )
            edge_traces.append(
                go.Scatter(
                    x=[start_x, midpoint[0], end_x],
                    y=[start_y, midpoint[1], end_y],
                    mode="lines",
                    line={
                        "color": "#80908a",
                        "width": 1.25,
                        "shape": "spline",
                        "smoothing": 0.35,
                    },
                    hoverinfo="skip",
                    showlegend=False,
                    name="plugin-overview-spline",
                )
            )
            tangent_x, tangent_y = end_x - midpoint[0], end_y - midpoint[1]
            tangent_length = max((tangent_x**2 + tangent_y**2) ** 0.5, 1.0)
            annotations.append(
                {
                    # Keep the arrowhead aligned with the final spline segment.
                    "ax": end_x - tangent_x / tangent_length * 8,
                    "ay": end_y - tangent_y / tangent_length * 8,
                    "x": end_x,
                    "y": end_y,
                    "xref": "x",
                    "yref": "y",
                    "axref": "x",
                    "ayref": "y",
                    "showarrow": True,
                    "arrowhead": 2,
                    "arrowsize": 0.8,
                    "arrowwidth": 1.25,
                    "arrowcolor": "#80908a",
                }
            )

        x_values = [positions[node.node_id][0] for node in lineage_graph.nodes]
        y_values = [positions[node.node_id][1] for node in lineage_graph.nodes]
        customdata = [node.node_id.removeprefix("plugin:") for node in lineage_graph.nodes]
        hovertext = [node.tooltip for node in lineage_graph.nodes]
        figure = go.Figure(
            data=edge_traces
            + [
                go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="markers",
                    marker={"size": 86, "opacity": 0},
                    customdata=customdata,
                    hoverinfo="text",
                    hovertext=hovertext,
                    showlegend=False,
                    name="plugin-overview-nodes",
                )
            ]
        )
        figure.update_layout(
            shapes=node_shapes,
            annotations=annotations,
            meta={"node_shape_indices": {name: index for index, name in enumerate(customdata)}},
            margin={"l": 22, "r": 22, "t": 22, "b": 22},
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            # Start at a readable scale; Plotly pan and zoom expose the remaining
            # default-resolved topology without shrinking every plugin card.
            xaxis={"visible": False, "range": [0, min(lineage_graph.width, 1500)]},
            yaxis={
                "visible": False,
                "range": [lineage_graph.height, 0],
                "scaleanchor": "x",
                "scaleratio": 1,
            },
            height=max(560, min(900, lineage_graph.height + 44)),
        )
        return figure.to_html(
            full_html=False,
            include_plotlyjs=False,
            config={"scrollZoom": True, "displaylogo": False, "responsive": True},
            div_id="plugin-global-lineage",
        )

    @staticmethod
    def _direct_lineage_model(model: Any, provides: str) -> Any:
        """Return the selected plugin and only its direct port-level neighbors."""
        from waveform_analysis.core.foundation.model import LineageGraphModel

        included_edges = [
            edge
            for edge in model.edges
            if edge.source_node_id == provides or edge.target_node_id == provides
        ]
        included_nodes = {provides}
        for edge in included_edges:
            included_nodes.add(edge.source_node_id)
            included_nodes.add(edge.target_node_id)
        port_ids = {
            port_id
            for edge in included_edges
            for port_id in (edge.source_port_id, edge.target_port_id)
        }
        incoming = {node_id: set() for node_id in included_nodes}
        for edge in included_edges:
            incoming.setdefault(edge.target_node_id, set()).add(edge.source_node_id)
        depths = {node_id: 0 for node_id, sources in incoming.items() if not sources}
        for _ in range(len(included_nodes)):
            changed = False
            for edge in included_edges:
                if edge.source_node_id not in depths:
                    continue
                depth = depths[edge.source_node_id] + 1
                if depth > depths.get(edge.target_node_id, -1):
                    depths[edge.target_node_id] = depth
                    changed = True
            if not changed:
                break
        nodes = {
            node_id: replace(
                model.nodes[node_id],
                in_ports=[port for port in model.nodes[node_id].in_ports if port.id in port_ids],
                out_ports=[port for port in model.nodes[node_id].out_ports if port.id in port_ids],
                depth=depths.get(node_id, 0),
            )
            for node_id in included_nodes
            if node_id in model.nodes
        }
        return LineageGraphModel(
            nodes=nodes,
            edges=included_edges,
            metadata=dict(model.metadata),
        )

    def _render_detail_lineage_figures(
        self,
        plugins: list[PluginDocumentationView],
        dependencies_by_provides: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Render direct-neighborhood port figures using the runtime renderer."""
        from waveform_analysis.utils.visualization.lineage_visualizer import plot_lineage_plotly

        model = self._build_default_lineage_model(plugins, dependencies_by_provides)
        return {
            plugin.provides: json.loads(
                plot_lineage_plotly(
                    self._direct_lineage_model(model, plugin.provides),
                    f"{plugin.provides} direct lineage",
                    show=False,
                    data_wires=False,
                ).to_json()
            )
            for plugin in plugins
        }

    def render_plugin_html(
        self,
        doc_info: PluginDocumentationView,
        *,
        lineage_graph: _WebLineageGraph | None = None,
    ) -> str:
        """Render one standalone plugin HTML page with escaped metadata."""
        return (
            self._get_web_jinja_env()
            .get_template("web/plugin.html.j2")
            .render(
                plugin=doc_info,
                lineage_graph=lineage_graph,
            )
        )

    def render_index_html(
        self,
        plugins: list[PluginDocumentationView],
        *,
        lineage_graph: _WebLineageGraph | None = None,
        dependencies_by_provides: dict[str, list[str]] | None = None,
        global_lineage_html: str | None = None,
    ) -> str:
        """Render the searchable static-site index."""
        scored_plugins = self._with_web_scores(plugins, dependencies_by_provides)
        lineage_graph = lineage_graph or self._build_web_lineage_graph(
            scored_plugins,
            link_prefix="plugins/",
            dependencies_by_provides=dependencies_by_provides,
        )
        if global_lineage_html is None:
            global_lineage_html = self._render_global_plotly_html(lineage_graph)
        plugin_sets = self._web_plugin_sets(scored_plugins)
        return (
            self._get_web_jinja_env()
            .get_template("web/index.html.j2")
            .render(
                plugins=sorted(scored_plugins, key=lambda item: item.provides),
                plugin_sets=plugin_sets,
                lineage_graph=lineage_graph,
                global_lineage_html=Markup(global_lineage_html),
            )
        )

    def generate_web(self, output_dir: Path) -> dict[str, Path]:
        """Generate an offline HTML plugin reference site."""
        output_dir = Path(output_dir)
        plugin_dir = output_dir / "plugins"
        asset_dir = output_dir / "assets"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        asset_dir.mkdir(parents=True, exist_ok=True)
        default_dependencies = self._default_dependency_map()
        plugins = self._with_web_scores(
            self.get_all_doc_info(), dependencies_by_provides=default_dependencies
        )
        global_graph = self._build_web_lineage_graph(
            plugins,
            link_prefix="plugins/",
            dependencies_by_provides=default_dependencies,
        )
        generated: dict[str, Path] = {}
        for plugin in plugins:
            path = plugin_dir / f"{plugin.provides}.html"
            path.write_text(
                self.render_plugin_html(
                    plugin,
                    lineage_graph=self._build_web_lineage_graph(
                        plugins,
                        link_prefix="",
                        focus=plugin.provides,
                        dependencies_by_provides=default_dependencies,
                    ),
                ),
                encoding="utf-8",
            )
            generated[plugin.provides] = path
        index_path = output_dir / "index.html"
        index_path.write_text(
            self.render_index_html(
                plugins,
                lineage_graph=global_graph,
                dependencies_by_provides=default_dependencies,
                global_lineage_html=self._render_global_plotly_html(global_graph),
            ),
            encoding="utf-8",
        )
        generated["INDEX"] = index_path
        source_assets = self.template_dir / "web" / "assets"
        for name in ("site.css", "site.js"):
            target = asset_dir / name
            shutil.copyfile(source_assets / name, target)
            generated[f"asset:{name}"] = target
        try:
            from plotly.offline import get_plotlyjs
        except ImportError as exc:
            raise ImportError(
                "plotly is required for the global plugins-web lineage view."
            ) from exc
        plotly_asset = asset_dir / "plotly.min.js"
        plotly_asset.write_text(get_plotlyjs(), encoding="utf-8")
        generated["asset:plotly.min.js"] = plotly_asset
        detail_asset = asset_dir / "lineage-details.json"
        detail_asset.write_text(
            json.dumps(
                self._render_detail_lineage_figures(plugins, default_dependencies),
                ensure_ascii=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        generated["asset:lineage-details.json"] = detail_asset
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
