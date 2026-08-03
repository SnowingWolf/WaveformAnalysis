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
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any
from urllib.parse import quote
import warnings

from markupsafe import Markup, escape
import numpy as np

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.documentation.field_notes import dtype_field_notes_for

export, __all__ = exporter()


def _inline_code(value: str) -> Markup:
    """Escape prose first, then render restricted emphasis and code notation."""
    escaped = str(escape(value))
    emphasized = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return Markup(re.sub(r"`([^`]+)`", r"<code>\1</code>", emphasized))


def _highlight_python(source: str) -> Markup:
    """Return trusted offline Pygments markup for registry-controlled Python examples."""
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import PythonLexer
    except ImportError as exc:
        raise RuntimeError(
            "site-web plugin examples require Pygments. Install the documentation extra: "
            'pip install -e ".[docgen]"'
        ) from exc
    return Markup(highlight(source, PythonLexer(), HtmlFormatter(nowrap=True)))


# 插件类别映射规则
CATEGORY_KEYWORDS = {
    "data_loading": ["raw", "files", "loader", "reader"],
    "peaks": ["peaklet"],
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
    "peaks": "峰构建",
    "feature_extraction": "特征提取",
    "event_analysis": "事件分析",
    "data_export": "数据导出",
    "signal_processing": "信号处理",
    "cache_analysis": "缓存分析",
    "records": "记录处理",
    "other": "其他",
}

# 插件集合描述：每个 plugin_set 的职责与组成
PLUGIN_SET_DESCRIPTIONS = {
    "io": "扫描数据目录并按通道号分组原始文件，是处理链路的输入入口。",
    "waveform": "波形结构化、可选滤波与 records/wave_pool 构建；波形与记录插件必须同集合注册，依赖关系随 adapter 自动调整。",
    "hit": "Hit 检测与合并：阈值检测、记录掩码（不对称/探测器/veto）、hit 合并与聚类、hit_merged 特征。",
    "peaks": "Peaklet 构建与 peak 分类：peaklet 组件、peaklets、波形、pool、特征、通道、peaks、波形宽度、S1/S2 分类与 peak 分类。",
    "basic_features": "基础特征提取：从波形计算高度、面积、最大绝对差等特征。",
    "tabular": "表格输出（DataFrame、表）：构建单通道事件 DataFrame 与分组/配对事件表。",
    "events": "事件级处理：S1-S2 配对候选与最终选择、位置重建、完整事件重建与按时间窗口分组的事件。",
}

PLUGIN_SET_COLORS = {
    "io": ("#e8f1fb", "#3b78b8", "#c9dff5"),
    "waveform": ("#e5f5ee", "#278a5b", "#c8ead9"),
    "hit": ("#fff0df", "#c76b20", "#f8d5ab"),
    "peaks": ("#f1e9fb", "#8054b5", "#dfcdf4"),
    "basic_features": ("#fdf5d8", "#a98219", "#f2e3a6"),
    "tabular": ("#e6f4f6", "#287e88", "#c8e8eb"),
    "events": ("#fae8ed", "#bb4666", "#f3cad5"),
    "other": ("#eef1f2", "#63727b", "#d9e0e3"),
}

DOCUMENTATION_DEFAULT_PROFILE = {
    "wave_source": "records",
    "use_filtered": False,
    "daq_adapter": "vx2730",
}
DOCUMENTATION_PLUGIN_DEFAULTS = {
    "hit_threshold": {"asymmetry_cut_enabled": True},
}
STANDALONE_PLUGIN_OUTPUTS = frozenset({"cache_analysis"})
CORE_TERMINAL_OUTPUT = "events"
MAIN_LINEAGE_PATH = (
    "raw_files",
    "records",
    "hit_threshold",
    "hit_merged",
    "peaklets",
    "peaks",
    "peak_classification",
    "s1_s2_pair_candidates",
    "s1_s2_pairs",
    "position_reconstruction",
    "events",
)
MAIN_LINEAGE_EDGES = frozenset(zip(MAIN_LINEAGE_PATH, MAIN_LINEAGE_PATH[1:], strict=False))


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
    has_input: bool = False
    has_output: bool = False
    is_focus: bool = False


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
    is_local: bool = False


@dataclass(frozen=True)
class _WebPluginSet:
    """A canonical execution plugin set rendered on the static index."""

    name: str
    label: str
    plugins: list[PluginDocumentationView]
    description: str = ""


class _DefaultDocumentationContext:
    """Restricted context for resolving documentation-only default dependencies."""

    def __init__(self, plugins: dict[str, Any], *, shared_profile=None, plugin_profile=None):
        self._plugins = plugins
        self._shared_profile = dict(shared_profile or DOCUMENTATION_DEFAULT_PROFILE)
        self._plugin_profile = {
            name: dict(values)
            for name, values in (plugin_profile or DOCUMENTATION_PLUGIN_DEFAULTS).items()
        }
        self.config = {**self._shared_profile, **self._plugin_profile}

    def get_config(self, plugin: Any, key: str) -> Any:
        provides = str(getattr(plugin, "provides", ""))
        if key in self._plugin_profile.get(provides, {}):
            return self._plugin_profile[provides][key]
        if key in self._shared_profile:
            return self._shared_profile[key]
        option = getattr(plugin, "options", {}).get(key)
        if option is None:
            raise KeyError(f"Unknown documentation config option {provides}.{key}")
        return option.default


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
            self._web_jinja_env.filters["inline_code"] = _inline_code
            self._web_jinja_env.filters["highlight_python"] = _highlight_python
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
        workflow_steps = agent_doc["workflow_steps"] or self._derive_workflow_steps(plugin)
        derived_overview, derived_overview_paragraphs = self._derive_overview(plugin)
        overview = agent_doc["overview"] or derived_overview
        overview_paragraphs = agent_doc["overview_paragraphs"] or (
            [overview] if overview else derived_overview_paragraphs
        )
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
            overview=overview,
            overview_paragraphs=overview_paragraphs,
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
    def _compute_docstring(plugin: Any) -> str:
        """Return the cleaned compute docstring, or "" when absent."""
        compute = type(plugin).__dict__.get("compute")
        if compute is None or compute.__doc__ is None:
            return ""
        return inspect.cleandoc(compute.__doc__)

    @staticmethod
    def _docstring_narrative(doc: str) -> list[str]:
        """Split cleaned docstring prose (before any section marker) into paragraphs."""
        section_header = re.compile(
            r"^(Args|Arguments|Parameters|Returns|Raises|Examples|Yields|Notes):\s*$",
            re.IGNORECASE,
        )
        steps: list[str] = []
        paragraph: list[str] = []
        for raw_line in doc.splitlines():
            line = raw_line.strip()
            if section_header.match(line):
                break
            if not line:
                if paragraph:
                    steps.append(" ".join(paragraph))
                    paragraph = []
                continue
            paragraph.append(line)
        if paragraph:
            steps.append(" ".join(paragraph))
        return [step for step in steps if step]

    @staticmethod
    def _derive_workflow_steps(plugin: Any) -> list[str]:
        """Derive ordered "How It Works" steps from the compute docstring prose.

        Only the narrative preceding section markers (Args/Returns/...) is used; each
        narrative clause becomes a distinct, ordered step. A missing compute docstring
        yields no steps, so plugins whose narrative is authored elsewhere (agent_doc /
        published YAML) are never disturbed.
        """
        compute_doc = PluginDocGenerator._compute_docstring(plugin)
        if not compute_doc:
            return []
        return PluginDocGenerator._docstring_narrative(compute_doc)[:5]

    @staticmethod
    def _derive_overview(plugin: Any) -> tuple[str, list[str]]:
        """Derive an overview from the plugin class docstring when none is published.

        Returns ``(overview, overview_paragraphs)``. The first non-empty paragraph of
        the class docstring becomes the overview sentence; multi-paragraph docstrings
        are additionally exposed as separate overview paragraphs. Returns empty values
        when the class has no docstring so authored narrative always wins.
        """
        doc = inspect.cleandoc(type(plugin).__doc__ or "")
        if not doc:
            return "", []
        paragraphs = [p.strip() for p in doc.split("\n\n") if p.strip()]
        if not paragraphs:
            return "", []
        overview = paragraphs[0].replace("\n", " ")
        return overview, [paragraph.replace("\n", " ") for paragraph in paragraphs]

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
                    units=field.units or dtype_notes.get(field.name, {}).get("units", "None"),
                    doc=field.doc or dtype_notes.get(field.name, {}).get("doc", ""),
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
                    note = dtype_notes.get(name, {})
                    doc = note.get("doc", "") if isinstance(note, dict) else str(note)
                    units = note.get("units", "None") if isinstance(note, dict) else "None"
                    output_fields.append(
                        OutputFieldInfo(
                            name=name,
                            dtype=str(field_dtype),
                            units=units,
                            doc=doc,
                        )
                    )
            else:
                # 简单数组
                output_kind = "array"
                note = dtype_notes.get("value", {})
                doc = note.get("doc", "") if isinstance(note, dict) else str(note)
                units = note.get("units", "-") if isinstance(note, dict) else "-"
                output_fields.append(
                    OutputFieldInfo(
                        name="value",
                        dtype=str(dtype),
                        units=units,
                        doc=doc,
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
            "peaks",
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
                        label=f"插件集合：{name.replace('_', ' ').title()}",
                        plugins=members,
                        description=PLUGIN_SET_DESCRIPTIONS.get(name, ""),
                    )
                )

        remaining = sorted(
            (
                plugin
                for plugin in plugins
                if plugin.provides not in assigned
                and plugin.provides not in STANDALONE_PLUGIN_OUTPUTS
            ),
            key=lambda plugin: plugin.provides,
        )
        if remaining:
            groups.append(
                _WebPluginSet(
                    name="other",
                    label="其他插件",
                    plugins=remaining,
                    description="未归入上述集合的补充插件。",
                )
            )
        return groups

    @staticmethod
    def _standalone_plugins(plugins):
        return sorted(
            (p for p in plugins if p.provides in STANDALONE_PLUGIN_OUTPUTS),
            key=lambda p: p.provides,
        )

    @classmethod
    def _terminal_outputs(cls, plugins, dependencies_by_provides):
        names = {p.provides for p in plugins if p.provides not in STANDALONE_PLUGIN_OUTPUTS}
        consumed = {
            dep
            for plugin in plugins
            if plugin.provides in names
            for dep in dependencies_by_provides.get(plugin.provides, [])
            if dep in names
        }
        return names - consumed - {CORE_TERMINAL_OUTPUT}

    @staticmethod
    def _filter_lineage_graph(graph, hidden_outputs, *, title):
        hidden_ids = {f"plugin:{name}" for name in hidden_outputs}
        return replace(
            graph,
            title=title,
            nodes=[n for n in graph.nodes if n.node_id not in hidden_ids],
            edges=[
                e
                for e in graph.edges
                if e.source_id not in hidden_ids and e.target_id not in hidden_ids
            ],
            isolated_nodes=[n for n in graph.isolated_nodes if n.node_id not in hidden_ids],
        )

    @staticmethod
    def _place_terminal_outputs(graph, terminal_outputs):
        terminal_ids = {f"plugin:{name}" for name in terminal_outputs}
        by_id = {node.node_id: node for node in graph.nodes}
        core = [node for node in graph.nodes if node.node_id not in terminal_ids]
        track_y = max((node.y + node.height for node in core), default=0) + 140
        positioned = {}
        for track, node_id in enumerate(sorted(terminal_ids)):
            node = by_id.get(node_id)
            if node is None:
                continue
            positioned[node_id] = replace(
                node,
                x=36 + track * (node.width + 56),
                y=track_y,
            )
        nodes = [positioned.get(node.node_id, node) for node in graph.nodes]
        width = max((node.x + node.width for node in nodes), default=graph.width) + 36
        height = max((node.y + node.height for node in nodes), default=graph.height) + 36
        return replace(
            graph, nodes=nodes, width=width, height=height, view_box=f"0 0 {width} {height}"
        )

    def _global_lineage_views(self, plugins, *, link_prefix, dependencies_by_provides):
        graph_plugins = [p for p in plugins if p.provides not in STANDALONE_PLUGIN_OUTPUTS]
        full = self._build_web_lineage_graph(
            graph_plugins,
            link_prefix=link_prefix,
            dependencies_by_provides=dependencies_by_provides,
        )
        terminals = self._terminal_outputs(graph_plugins, dependencies_by_provides)
        available = {plugin.provides for plugin in graph_plugins}
        overview_outputs: set[str] = set()

        def include_ancestors(output: str) -> None:
            if output in overview_outputs or output not in available:
                return
            overview_outputs.add(output)
            for dependency in dependencies_by_provides.get(output, []):
                include_ancestors(dependency)

        include_ancestors(CORE_TERMINAL_OUTPUT)
        if not overview_outputs:
            overview_outputs = available - terminals or available
        hidden = available - overview_outputs
        overview = self._filter_lineage_graph(full, hidden, title="处理概览")
        return {"overview": overview, "full": replace(full, title="完整插件 DAG")}, terminals

    @staticmethod
    def _lineage_node_kind(provides: str) -> str:
        if provides == "raw_files":
            return "input"
        if "wave" in provides or provides in {"records", "st_waveforms"}:
            return "waveform"
        if provides.startswith("hit") or provides.startswith("records_"):
            return "hit"
        if provides.startswith("peaklet"):
            return "peaklet"
        if provides in {"events", "df", "df_events", "df_paired"}:
            return "output"
        if provides.startswith("peak") or provides.startswith("s1_s2"):
            return "peak"
        return "default"

    @staticmethod
    def _lineage_edge_kind(source: str, target: str) -> str:
        if (source, target) in MAIN_LINEAGE_EDGES:
            return "main"
        if "wave" in source or "wave" in target or source.endswith("_pool"):
            return "auxiliary"
        return "dependency"

    def _build_cytoscape_lineage_payload(
        self,
        plugins: list[PluginDocumentationView],
        dependencies_by_provides: dict[str, list[str]],
        *,
        plugin_href_prefix: str,
    ) -> dict[str, Any]:
        """Return the runtime lineage model as an offline React Flow payload."""
        from waveform_analysis.core.foundation.utils import LineageStyle
        from waveform_analysis.utils.visualization.lineage_visualizer import (
            _classify_edge_category,
            _classify_node_type,
            _resolve_wire_style,
        )

        graph_plugins = sorted(
            (plugin for plugin in plugins if plugin.provides not in STANDALONE_PLUGIN_OUTPUTS),
            key=lambda plugin: plugin.provides,
        )
        names = {plugin.provides for plugin in graph_plugins}
        relations = self._build_detail_lineage_relations(graph_plugins, dependencies_by_provides)
        overview_names: set[str] = set()

        def include_ancestors(output: str) -> None:
            if output in overview_names or output not in names:
                return
            overview_names.add(output)
            for dependency in dependencies_by_provides.get(output, []):
                include_ancestors(dependency)

        include_ancestors(CORE_TERMINAL_OUTPUT)
        if not overview_names:
            terminals = self._terminal_outputs(graph_plugins, dependencies_by_provides)
            overview_names = names - terminals or names
        model = self._build_default_lineage_model(graph_plugins, dependencies_by_provides)
        style = LineageStyle()
        plugin_by_name = {plugin.provides: plugin for plugin in graph_plugins}
        plugin_sets = {
            member.provides: group.name
            for group in self._web_plugin_sets(graph_plugins)
            for member in group.plugins
        }
        nodes = []
        for node_id, node in sorted(model.nodes.items()):
            plugin = plugin_by_name[node_id]
            node_kind = _classify_node_type(node)
            background, border, header = PLUGIN_SET_COLORS.get(
                plugin_sets.get(node_id, "other"), PLUGIN_SET_COLORS["other"]
            )

            def port_payload(port: Any) -> dict[str, Any]:
                return {
                    "id": port.id,
                    "name": port.name,
                    "kind": port.kind,
                    "dtype": port.dtype,
                    "index": port.index,
                    "color": style.type_colors.get(
                        port.dtype, style.type_colors.get("Unknown", "#95a5a6")
                    ),
                }

            in_ports = [port_payload(port) for port in node.in_ports]
            out_ports = [port_payload(port) for port in node.out_ports]
            nodes.append(
                {
                    "data": {
                        "id": node_id,
                        "label": node.title or node.key,
                        "pluginClass": plugin.name,
                        "summary": plugin.summary,
                        "href": f"{plugin_href_prefix}{plugin.provides}.html",
                        "kind": node_kind,
                        "isLineageVirtual": node.is_lineage_virtual,
                        "pluginSet": plugin_sets.get(node_id, "other"),
                        "colors": {
                            "background": background,
                            "border": border,
                            "header": header,
                        },
                        "in_ports": in_ports,
                        "out_ports": out_ports,
                        "width": 248,
                        "height": 78 + max(len(in_ports), len(out_ports), 1) * 28,
                        "documentationCompleteness": plugin.documentation_completeness,
                        "dagImpact": plugin.dag_impact,
                    }
                }
            )
        edges = []
        for index, edge in enumerate(model.edges):
            wire_style = _resolve_wire_style(edge, style)
            edges.append(
                {
                    "data": {
                        "id": (f"edge::{index}::{edge.source_port_id}::{edge.target_port_id}"),
                        "source_node_id": edge.source_node_id,
                        "source_port_id": edge.source_port_id,
                        "target_node_id": edge.target_node_id,
                        "target_port_id": edge.target_port_id,
                        "dtype": edge.dtype,
                        "category": _classify_edge_category(edge.dtype),
                        "kind": self._lineage_edge_kind(edge.source_node_id, edge.target_node_id),
                        "style": wire_style,
                    }
                }
            )
        payload = {
            "nodes": nodes,
            "edges": edges,
            "views": {
                "overview": sorted(overview_names),
                "full": sorted(names),
            },
            "relations": relations,
            "focusDepth": 2,
        }
        self._validate_lineage_payload(payload)
        return payload

    def build_lineage_payload_for_context(
        self, context: Any, *, plugin_href_prefix: str = "/plugins/"
    ) -> dict[str, Any]:
        """Build a read-only web lineage payload from a configured Context.

        This intentionally reuses the same model-to-payload conversion as the
        offline documentation generator.  ``Context.get_lineage`` resolves
        configuration and dependency metadata but does not execute plugin
        compute methods or read run data.
        """
        context_plugins = getattr(context, "_plugins", None)
        if not isinstance(context_plugins, dict) or not context_plugins:
            raise ValueError("Context factory must return a Context with registered plugins")

        self._plugins = [
            (plugin.__class__, plugin) for _provides, plugin in sorted(context_plugins.items())
        ]
        dependencies: dict[str, list[str]] = {}
        for provides in context_plugins:
            lineage = context.get_lineage(provides)
            direct_dependencies = (lineage or {}).get("depends_on", {})
            dependencies[provides] = list(direct_dependencies)

        plugins = self._with_web_scores(
            self.get_all_doc_info(), dependencies_by_provides=dependencies
        )
        return self._build_cytoscape_lineage_payload(
            plugins,
            dependencies,
            plugin_href_prefix=plugin_href_prefix,
        )

    @staticmethod
    def _validate_lineage_payload(payload: dict[str, Any]) -> None:
        """Fail generation with the exact dangling node or port reference."""
        nodes = {entry["data"]["id"]: entry["data"] for entry in payload["nodes"]}
        ports: dict[str, tuple[str, str]] = {}
        for node_id, node in nodes.items():
            for key, expected_kind in (("in_ports", "in"), ("out_ports", "out")):
                for port in node[key]:
                    port_id = port["id"]
                    if port_id in ports:
                        raise ValueError(f"Duplicate lineage port id {port_id!r}")
                    if port["kind"] != expected_kind:
                        raise ValueError(
                            f"Lineage port {port_id!r} on {node_id!r} has kind "
                            f"{port['kind']!r}, expected {expected_kind!r}"
                        )
                    ports[port_id] = (node_id, expected_kind)

        for entry in payload["edges"]:
            edge = entry["data"]
            edge_id = edge["id"]
            for node_key in ("source_node_id", "target_node_id"):
                if edge[node_key] not in nodes:
                    raise ValueError(
                        f"Lineage edge {edge_id!r} references missing {node_key} "
                        f"{edge[node_key]!r}"
                    )
            for port_key, node_key, expected_kind in (
                ("source_port_id", "source_node_id", "out"),
                ("target_port_id", "target_node_id", "in"),
            ):
                port_id = edge[port_key]
                if port_id not in ports:
                    raise ValueError(
                        f"Lineage edge {edge_id!r} references missing {port_key} {port_id!r}"
                    )
                owner, kind = ports[port_id]
                if owner != edge[node_key] or kind != expected_kind:
                    raise ValueError(
                        f"Lineage edge {edge_id!r} maps {port_key} {port_id!r} to "
                        f"{edge[node_key]!r}, but the port belongs to {owner!r} as {kind!r}"
                    )

    def _build_web_lineage_graph(
        self,
        plugins: list[PluginDocumentationView],
        *,
        link_prefix: str,
        focus: str | None = None,
        global_focus_prefix: str = "../index.html?focus=",
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
            title = "插件谱系"
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
            title = "局部谱系"
            description = "直接声明的插件输入与消费者。"

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

        source_ids = {source for source, _ in known_edges}
        target_ids = {target for _, target in known_edges}

        if focus is not None:
            # Plugin detail pages use the same left-to-right LabVIEW-style
            # presentation as the analysis notebook: inputs, selected plugin,
            # then consumers.  The global index keeps its compact top-down DAG.
            inputs = sorted(
                name for name in visible_names if (node_ids[name], node_ids[focus]) in known_edges
            )
            consumers_for_focus = sorted(
                name for name in visible_names if (node_ids[focus], node_ids[name]) in known_edges
            )
            columns = (inputs, [focus], consumers_for_focus)
            node_width = 224
            node_height = 132
            x_gap = 104
            y_gap = 30
            margin = 44
            max_rows = max((len(column) for column in columns), default=1)
            canvas_width = margin * 2 + 3 * node_width + 2 * x_gap
            canvas_height = margin * 2 + max_rows * node_height + max(0, max_rows - 1) * y_gap
            positions: dict[str, tuple[int, int]] = {}
            nodes: list[_WebLineageNode] = []
            for column_index, names in enumerate(columns):
                column_height = len(names) * node_height + max(0, len(names) - 1) * y_gap
                start_y = margin + (canvas_height - 2 * margin - column_height) // 2
                for name in names:
                    node_id = node_ids[name]
                    x = margin + column_index * (node_width + x_gap)
                    y = start_y
                    start_y += node_height + y_gap
                    positions[node_id] = (x, y)
                    plugin = by_provides[name]
                    documentation_completeness = plugin.documentation_completeness
                    dag_impact = plugin.dag_impact
                    tooltip = (
                        f"{plugin.provides}. Documentation completeness "
                        f"{documentation_completeness}/100; DAG impact {dag_impact}/100."
                    )
                    nodes.append(
                        _WebLineageNode(
                            node_id=node_id,
                            label=name,
                            href=f"{link_prefix}{plugin.provides}.html",
                            placeholder=False,
                            x=x,
                            y=y,
                            width=node_width,
                            height=node_height,
                            documentation_completeness=documentation_completeness,
                            dag_impact=dag_impact,
                            tooltip=tooltip,
                            aria_label=tooltip + " Open plugin documentation.",
                            has_input=node_id in target_ids,
                            has_output=node_id in source_ids,
                            is_focus=name == focus,
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
                edges.append(
                    _WebLineageEdge(
                        source,
                        target,
                        f"M {start_x} {start_y} L {end_x} {end_y}",
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
                isolated_nodes=[],
                global_focus_href=f"{global_focus_prefix}{quote(focus)}",
                is_local=True,
            )

        layers: dict[int, list[str]] = {}
        for name, node_id in node_ids.items():
            layers.setdefault(depths[node_id], []).append(name)
        for names in layers.values():
            names.sort(key=lambda name: (name not in by_provides, name))

        # Keep names legible in both the static SVG used by plugin pages and the
        # interactive Plotly overview.  Width is data-dependent so long output
        # names are not truncated into indistinguishable labels.
        node_widths = {name: min(240, max(140, 32 + len(name) * 7)) for name in by_provides}
        node_height = 64
        x_gap = 48
        y_gap = 28
        margin = 36
        max_depth = max(layers, default=0)
        canvas_width = margin * 2 + max(
            (
                sum(node_widths[name] for name in names) + max(0, len(names) - 1) * x_gap
                for names in layers.values()
            ),
            default=140,
        )
        canvas_height = margin * 2 + (max_depth + 1) * node_height + max_depth * y_gap

        nodes: list[_WebLineageNode] = []
        positions: dict[str, tuple[int, int]] = {}
        for depth, names in sorted(layers.items()):
            layer_width = sum(node_widths[name] for name in names) + max(0, len(names) - 1) * x_gap
            start_x = margin + (canvas_width - 2 * margin - layer_width) // 2
            for name in names:
                node_id = node_ids[name]
                node_width = node_widths[name]
                x = start_x
                y = margin + depth * (node_height + y_gap)
                positions[node_id] = (x, y)
                start_x += node_width + x_gap
                plugin = by_provides[name]
                placeholder = False
                label = name
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
                        has_input=node_id in target_ids,
                        has_output=node_id in source_ids,
                    )
                )

        edges = []
        for source, target in known_edges:
            source_x, source_y = positions[source]
            target_x, target_y = positions[target]
            source_width = next(node.width for node in nodes if node.node_id == source)
            target_width = next(node.width for node in nodes if node.node_id == target)
            start_x = source_x + source_width // 2
            start_y = source_y + node_height
            end_x = target_x + target_width // 2
            end_y = target_y
            bend = max(32, (end_y - start_y) // 2)
            path = (
                f"M {start_x} {start_y} C {start_x} {start_y + bend}, "
                f"{end_x} {end_y - bend}, {end_x} {end_y}"
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
                f"{global_focus_prefix}{quote(focus)}" if focus is not None else None
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

    def _build_global_plotly_figure(self, lineage_graph: _WebLineageGraph) -> Any:
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
        node_meta = []
        edge_meta = []
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
                    "y": y,
                    "text": f"<b>{self._lineage_display_label(node.label)}</b>",
                    "showarrow": False,
                    "align": "center",
                    "font": {"size": 13, "color": "#17201d"},
                }
            )
            node_meta.append(
                {
                    "id": node.node_id.removeprefix("plugin:"),
                    "label": self._lineage_display_label(node.label),
                    "row": node.y,
                    "shape_index": len(node_shapes) - 1,
                    "annotation_index": len(annotations) - 1,
                }
            )

        for edge in lineage_graph.edges:
            start = positions[edge.source_id]
            end = positions[edge.target_id]
            source_node = next(
                node for node in lineage_graph.nodes if node.node_id == edge.source_id
            )
            target_node = next(
                node for node in lineage_graph.nodes if node.node_id == edge.target_id
            )
            start_x, start_y = start[0], start[1] + source_node.height / 2
            end_x, end_y = end[0], end[1] - target_node.height / 2
            curve_offset = min(24, max(8, abs(end_x - start_x) * 0.12))
            if end_x < start_x:
                curve_offset = -curve_offset
            midpoint = (
                (start_x + end_x) / 2 + curve_offset,
                (start_y + end_y) / 2,
            )
            trace_index = len(edge_traces)
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
            arrow_index = len(annotations)
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
            edge_meta.append(
                {
                    "source": edge.source_id.removeprefix("plugin:"),
                    "target": edge.target_id.removeprefix("plugin:"),
                    "trace_index": trace_index,
                    "arrow_index": arrow_index,
                }
            )

        x_values = [positions[node.node_id][0] for node in lineage_graph.nodes]
        y_values = [positions[node.node_id][1] for node in lineage_graph.nodes]
        bounds_padding = 44
        x_min = min((shape["x0"] for shape in node_shapes), default=0) - bounds_padding
        x_max = (
            max((shape["x1"] for shape in node_shapes), default=lineage_graph.width)
            + bounds_padding
        )
        y_min = min((shape["y0"] for shape in node_shapes), default=0) - bounds_padding
        y_max = (
            max((shape["y1"] for shape in node_shapes), default=lineage_graph.height)
            + bounds_padding
        )
        customdata = [node.node_id.removeprefix("plugin:") for node in lineage_graph.nodes]
        hovertext = [node.tooltip for node in lineage_graph.nodes]
        figure = go.Figure(
            data=edge_traces
            + [
                go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="markers",
                    marker={"size": 210, "opacity": 0},
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
            meta={
                "node_shape_indices": {name: index for index, name in enumerate(customdata)},
                "nodes": node_meta,
                "edges": edge_meta,
            },
            autosize=True,
            uirevision="plugin-doc-lineage",
            margin={"l": 20, "r": 20, "t": 24, "b": 20},
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
            # The client refines these bounds to the live container; the static first
            # frame must still fit the current Core/All node set rather than the full DAG.
            xaxis={"visible": False, "range": [x_min, x_max]},
            yaxis={
                "visible": False,
                "range": [y_max, y_min],
            },
        )
        return figure

    @staticmethod
    def _lineage_display_label(name: str) -> str:
        """Wrap long output names at an underscore without changing their identity."""
        if len(name) <= 16 or "_" not in name:
            return name
        parts = name.split("_")
        prefix = ""
        for part in parts[:-1]:
            candidate = f"{prefix}{part}_"
            if len(candidate) > 14:
                break
            prefix = candidate
        if prefix:
            return f"{prefix}<br>{name[len(prefix):]}"
        return name

    def _render_global_plotly_html(self, lineage_graph: _WebLineageGraph) -> str:
        return self._build_global_plotly_figure(lineage_graph).to_html(
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

    def _build_detail_lineage_relations(
        self,
        plugins: list[PluginDocumentationView],
        dependencies_by_provides: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Return direct plugin relationships for the interactive detail panel.

        A small port-level Plotly graph is unreadable in a 380px sidebar.  The
        panel intentionally presents just the direct relationships as navigable
        lists while the main Plotly graph remains the spatial overview.
        """
        names = {plugin.provides for plugin in plugins}
        consumers: dict[str, list[str]] = {name: [] for name in names}
        relations: dict[str, dict[str, list[str]]] = {}
        for plugin in plugins:
            inputs = sorted(
                dependency
                for dependency in self._dependency_names(plugin, dependencies_by_provides)
                if dependency in names
            )
            relations[plugin.provides] = {"inputs": inputs, "consumers": []}
            for dependency in inputs:
                consumers[dependency].append(plugin.provides)
        for provides, direct_consumers in consumers.items():
            relations[provides]["consumers"] = sorted(direct_consumers)
        return relations

    def render_plugin_html(
        self,
        doc_info: PluginDocumentationView,
        *,
        lineage_graph: _WebLineageGraph | None = None,
        asset_prefix: str = "../assets/",
        site_home_href: str = "../index.html",
        plugin_index_href: str = "../index.html",
        accessor_index_href: str | None = None,
        context_index_href: str | None = None,
        adapter_index_href: str | None = None,
        visualization_index_href: str | None = None,
        visualization_detail_prefix: str | None = None,
        site_root_prefix: str = "../",
        react_asset_version: str = "",
    ) -> str:
        """Render one standalone plugin HTML page with escaped metadata."""
        return (
            self._get_web_jinja_env()
            .get_template("web/plugin.html.j2")
            .render(
                plugin=doc_info,
                lineage_graph=lineage_graph,
                asset_prefix=asset_prefix,
                site_home_href=site_home_href,
                plugin_index_href=plugin_index_href,
                accessor_index_href=accessor_index_href,
                context_index_href=context_index_href,
                adapter_index_href=adapter_index_href,
                visualization_index_href=visualization_index_href,
                visualization_detail_prefix=visualization_detail_prefix,
                site_root_prefix=site_root_prefix,
                react_asset_version=react_asset_version,
            )
        )

    def render_index_html(
        self,
        plugins: list[PluginDocumentationView],
        *,
        lineage_graph: _WebLineageGraph | None = None,
        dependencies_by_provides: dict[str, list[str]] | None = None,
        global_lineage_html: str | None = None,
        asset_prefix: str = "assets/",
        site_home_href: str = "index.html",
        plugin_href_prefix: str = "plugins/",
        plugin_index_href: str = "index.html",
        accessor_index_href: str | None = None,
        context_index_href: str | None = None,
        adapter_index_href: str | None = None,
        visualization_index_href: str | None = None,
        visualization_detail_prefix: str | None = None,
        lineage_details_json: str | None = None,
        global_lineage_json: str | None = None,
        terminal_outputs: set[str] | None = None,
        lineage_href: str = "lineage.html",
        site_root_prefix: str = "",
        react_asset_version: str = "",
    ) -> str:
        """Render the searchable static-site index."""
        scored_plugins = self._with_web_scores(plugins, dependencies_by_provides)
        lineage_graph = lineage_graph or self._build_web_lineage_graph(
            scored_plugins,
            link_prefix="plugins/",
            dependencies_by_provides=dependencies_by_provides,
        )
        plugin_sets = self._web_plugin_sets(scored_plugins)
        standalone_plugins = self._standalone_plugins(scored_plugins)
        return (
            self._get_web_jinja_env()
            .get_template("web/index.html.j2")
            .render(
                plugins=sorted(scored_plugins, key=lambda item: item.provides),
                plugin_sets=plugin_sets,
                lineage_graph=lineage_graph,
                global_lineage_html=Markup(global_lineage_html),
                asset_prefix=asset_prefix,
                site_home_href=site_home_href,
                plugin_href_prefix=plugin_href_prefix,
                plugin_index_href=plugin_index_href,
                accessor_index_href=accessor_index_href,
                context_index_href=context_index_href,
                adapter_index_href=adapter_index_href,
                visualization_index_href=visualization_index_href,
                visualization_detail_prefix=visualization_detail_prefix,
                standalone_plugins=standalone_plugins,
                terminal_outputs=sorted(terminal_outputs or set()),
                lineage_href=lineage_href,
                lineage_details_json=(
                    Markup(lineage_details_json) if lineage_details_json is not None else None
                ),
                global_lineage_json=(
                    Markup(global_lineage_json) if global_lineage_json is not None else None
                ),
                site_root_prefix=site_root_prefix,
                react_asset_version=react_asset_version,
            )
        )

    def render_lineage_html(
        self,
        *,
        lineage_json: str,
        asset_prefix: str,
        site_home_href: str,
        plugin_index_href: str,
        plugin_href_prefix: str,
        accessor_index_href: str | None,
        context_index_href: str | None,
        adapter_index_href: str | None,
        visualization_index_href: str | None,
        visualization_detail_prefix: str | None,
        site_root_prefix: str,
        react_asset_version: str = "",
        lineage_index_href: str | None = None,
    ) -> str:
        return (
            self._get_web_jinja_env()
            .get_template("web/lineage.html.j2")
            .render(
                lineage_json=Markup(lineage_json),
                asset_prefix=asset_prefix,
                site_home_href=site_home_href,
                plugin_index_href=plugin_index_href,
                plugin_href_prefix=plugin_href_prefix,
                accessor_index_href=accessor_index_href,
                context_index_href=context_index_href,
                adapter_index_href=adapter_index_href,
                visualization_index_href=visualization_index_href,
                visualization_detail_prefix=visualization_detail_prefix,
                site_root_prefix=site_root_prefix,
                react_asset_version=react_asset_version,
                lineage_index_href=lineage_index_href,
            )
        )

    def generate_web(
        self,
        output_dir: Path,
        *,
        index_relative_path: str = "index.html",
        plugin_relative_dir: str = "plugins",
        asset_relative_dir: str = "assets",
        site_home_href: str = "index.html",
        accessor_relative_path: str | None = None,
        context_relative_path: str | None = None,
        adapter_relative_path: str | None = None,
        visualization_relative_path: str | None = None,
        extra_search_entries: list[dict[str, str]] | None = None,
    ) -> dict[str, Path]:
        """Generate an offline HTML plugin reference site."""
        output_dir = Path(output_dir)
        index_path = output_dir / index_relative_path
        lineage_path = index_path.with_name("lineage.html")
        plugin_dir = output_dir / plugin_relative_dir
        asset_dir = output_dir / asset_relative_dir
        index_dir = index_path.parent
        plugin_dir.mkdir(parents=True, exist_ok=True)
        asset_dir.mkdir(parents=True, exist_ok=True)
        index_dir.mkdir(parents=True, exist_ok=True)
        source_assets = self.template_dir / "web" / "assets"
        react_asset_version = hashlib.sha256(
            (source_assets / "react" / "waveform-docs.js").read_bytes()
            + (source_assets / "react" / "waveform-docs.css").read_bytes()
        ).hexdigest()[:12]
        index_asset_prefix = Path(os.path.relpath(asset_dir, index_dir)).as_posix() + "/"
        index_site_root_prefix = Path(os.path.relpath(output_dir, index_dir)).as_posix()
        if index_site_root_prefix == ".":
            index_site_root_prefix = ""
        elif not index_site_root_prefix.endswith("/"):
            index_site_root_prefix += "/"
        detail_asset_prefix = Path(os.path.relpath(asset_dir, plugin_dir)).as_posix() + "/"
        index_plugin_prefix = Path(os.path.relpath(plugin_dir, index_dir)).as_posix()
        if index_plugin_prefix == ".":
            index_plugin_prefix = ""
        else:
            index_plugin_prefix += "/"
        detail_home_href = Path(os.path.relpath(output_dir / site_home_href, plugin_dir)).as_posix()
        detail_site_root_prefix = Path(os.path.relpath(output_dir, plugin_dir)).as_posix()
        if detail_site_root_prefix == ".":
            detail_site_root_prefix = ""
        elif not detail_site_root_prefix.endswith("/"):
            detail_site_root_prefix += "/"
        plugin_index_href = Path(os.path.relpath(index_path, plugin_dir)).as_posix()
        detail_lineage_href = Path(os.path.relpath(lineage_path, plugin_dir)).as_posix()
        detail_accessor_href = (
            Path(os.path.relpath(output_dir / accessor_relative_path, plugin_dir)).as_posix()
            if accessor_relative_path
            else None
        )
        index_accessor_href = (
            Path(os.path.relpath(output_dir / accessor_relative_path, index_dir)).as_posix()
            if accessor_relative_path
            else None
        )
        detail_context_href = (
            Path(os.path.relpath(output_dir / context_relative_path, plugin_dir)).as_posix()
            if context_relative_path
            else None
        )
        index_context_href = (
            Path(os.path.relpath(output_dir / context_relative_path, index_dir)).as_posix()
            if context_relative_path
            else None
        )
        detail_adapter_href = (
            Path(os.path.relpath(output_dir / adapter_relative_path, plugin_dir)).as_posix()
            if adapter_relative_path
            else None
        )
        index_adapter_href = (
            Path(os.path.relpath(output_dir / adapter_relative_path, index_dir)).as_posix()
            if adapter_relative_path
            else None
        )
        detail_visualization_href = (
            Path(os.path.relpath(output_dir / visualization_relative_path, plugin_dir)).as_posix()
            if visualization_relative_path
            else None
        )
        index_visualization_href = (
            Path(os.path.relpath(output_dir / visualization_relative_path, index_dir)).as_posix()
            if visualization_relative_path
            else None
        )
        visualization_dir = (
            output_dir / visualization_relative_path if visualization_relative_path else None
        )
        if visualization_dir is not None:
            visualization_dir = visualization_dir.parent
        detail_visualization_prefix = (
            Path(os.path.relpath(visualization_dir, plugin_dir)).as_posix() + "/"
            if visualization_dir is not None
            else None
        )
        index_visualization_prefix = (
            Path(os.path.relpath(visualization_dir, index_dir)).as_posix() + "/"
            if visualization_dir is not None
            else None
        )
        default_dependencies = self._default_dependency_map()
        plugins = self._with_web_scores(
            self.get_all_doc_info(), dependencies_by_provides=default_dependencies
        )
        global_views, terminal_outputs = self._global_lineage_views(
            plugins,
            link_prefix=index_plugin_prefix,
            dependencies_by_provides=default_dependencies,
        )
        global_graph = global_views["overview"]
        generated: dict[str, Path] = {}
        for plugin in plugins:
            path = plugin_dir / f"{plugin.provides}.html"
            path.write_text(
                self.render_plugin_html(
                    plugin,
                    lineage_graph=(
                        None
                        if plugin.provides in STANDALONE_PLUGIN_OUTPUTS
                        else self._build_web_lineage_graph(
                            [p for p in plugins if p.provides not in STANDALONE_PLUGIN_OUTPUTS],
                            link_prefix="",
                            focus=plugin.provides,
                            global_focus_prefix=f"{detail_lineage_href}?view=focus&focus=",
                            dependencies_by_provides=default_dependencies,
                        )
                    ),
                    asset_prefix=detail_asset_prefix,
                    site_home_href=detail_home_href,
                    plugin_index_href=plugin_index_href,
                    accessor_index_href=detail_accessor_href,
                    context_index_href=detail_context_href,
                    adapter_index_href=detail_adapter_href,
                    visualization_index_href=detail_visualization_href,
                    visualization_detail_prefix=detail_visualization_prefix,
                    site_root_prefix=detail_site_root_prefix,
                    react_asset_version=react_asset_version,
                ),
                encoding="utf-8",
            )
            generated[plugin.provides] = path
        lineage_payload = self._build_cytoscape_lineage_payload(
            plugins,
            default_dependencies,
            plugin_href_prefix=index_plugin_prefix,
        )
        lineage_json = json.dumps(lineage_payload, ensure_ascii=True, separators=(",", ":"))
        lineage_json = (
            lineage_json.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        )
        index_path.write_text(
            self.render_index_html(
                plugins,
                lineage_graph=global_graph,
                dependencies_by_provides=default_dependencies,
                asset_prefix=index_asset_prefix,
                site_home_href=Path(
                    os.path.relpath(output_dir / site_home_href, index_dir)
                ).as_posix(),
                plugin_href_prefix=index_plugin_prefix,
                plugin_index_href=Path(os.path.relpath(index_path, index_dir)).as_posix(),
                accessor_index_href=index_accessor_href,
                context_index_href=index_context_href,
                adapter_index_href=index_adapter_href,
                visualization_index_href=index_visualization_href,
                visualization_detail_prefix=index_visualization_prefix,
                global_lineage_json=lineage_json,
                terminal_outputs=terminal_outputs,
                lineage_href=Path(os.path.relpath(lineage_path, index_dir)).as_posix(),
                site_root_prefix=index_site_root_prefix,
                react_asset_version=react_asset_version,
            ),
            encoding="utf-8",
        )
        generated["INDEX"] = index_path
        lineage_path.write_text(
            self.render_lineage_html(
                lineage_json=lineage_json,
                asset_prefix=index_asset_prefix,
                site_home_href=Path(
                    os.path.relpath(output_dir / site_home_href, index_dir)
                ).as_posix(),
                plugin_index_href=Path(os.path.relpath(index_path, index_dir)).as_posix(),
                plugin_href_prefix=index_plugin_prefix,
                accessor_index_href=index_accessor_href,
                context_index_href=index_context_href,
                adapter_index_href=index_adapter_href,
                visualization_index_href=index_visualization_href,
                visualization_detail_prefix=index_visualization_prefix,
                site_root_prefix=index_site_root_prefix,
                react_asset_version=react_asset_version,
            ),
            encoding="utf-8",
        )
        generated["LINEAGE_INDEX"] = lineage_path
        for name in ("site.css", "site.js"):
            target = asset_dir / name
            shutil.copyfile(source_assets / name, target)
            generated[f"asset:{name}"] = target
        search_entries = []
        for plugin in plugins:
            base_url = f"{plugin_relative_dir}/{plugin.provides}.html"
            search_entries.extend(
                {
                    "title": plugin.provides,
                    "summary": plugin.summary or plugin.description or "暂无说明。",
                    "kind": "插件",
                    "url": f"{base_url}{anchor}",
                    "keywords": " ".join(
                        [plugin.provides, plugin.name, plugin.category, plugin.output_kind, heading]
                    ),
                }
                for heading, anchor in (
                    ("概览", "#overview"),
                    ("配置", "#configuration"),
                    ("输出", "#output"),
                )
            )
        search_entries.extend(extra_search_entries or [])
        search_asset = asset_dir / "search-index.js"
        search_asset.write_text(
            "window.WAVEFORM_DOCS_SEARCH="
            + json.dumps(search_entries, ensure_ascii=True, separators=(",", ":"))
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
            + ";\n",
            encoding="utf-8",
        )
        generated["asset:search-index.js"] = search_asset
        for name in ("waveform-docs.js", "waveform-docs.css"):
            target = asset_dir / "react" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_assets / "react" / name, target)
            generated[f"asset:react/{name}"] = target
        graph_asset = asset_dir / "lineage-graph.json"
        graph_asset.write_text(
            json.dumps(lineage_payload, ensure_ascii=True, separators=(",", ":")),
            encoding="utf-8",
        )
        generated["asset:lineage-graph.json"] = graph_asset
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
