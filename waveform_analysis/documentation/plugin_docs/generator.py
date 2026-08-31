"""
插件文档生成器 - 从 PluginSpec 自动生成 Markdown 文档

本模块提供从插件元数据自动生成文档的功能：
- PluginDocInfo: 从插件提取的文档信息数据类
- PluginDocGenerator: 文档生成器，使用 Jinja2 模板渲染

用法:
    >>> from waveform_analysis.documentation import PluginDocGenerator
    >>> generator = PluginDocGenerator()
    >>> generator.generate_all(Path("docs/plugins/reference/builtin/auto"))
"""

import ast
from dataclasses import replace
import inspect
from pathlib import Path
import re
import sys
import textwrap
from typing import Any
from urllib.parse import quote
import warnings

import numpy as np

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.documentation.field_notes import dtype_field_notes_for
from waveform_analysis.documentation.plugin_docs.catalog import (
    CATEGORY_DISPLAY_NAMES,
    CATEGORY_KEYWORDS,
    CORE_TERMINAL_OUTPUT,
    DOCUMENTATION_DEFAULT_PROFILE,
    DOCUMENTATION_DEFAULT_PROFILE_NAME,
    DOCUMENTATION_PLUGIN_DEFAULTS,
    MAIN_LINEAGE_EDGES,
    MAIN_LINEAGE_PATH,
    PLUGIN_SET_COLORS,
    PLUGIN_SET_DESCRIPTIONS,
    STANDALONE_PLUGIN_OUTPUTS,
)
from waveform_analysis.documentation.plugin_docs.models import (
    ConfigOptionInfo,
    DependencyDocumentationInfo,
    OutputFieldInfo,
    PluginDocInfo,
    PluginDocumentationView,
    _DefaultDocumentationContext,
    _PluginSetDocumentation,
)
from waveform_analysis.documentation.plugin_docs.validation import (
    _escape_markdown_cell,
    check_plugin_document,
    check_plugin_document_structure,
)
from waveform_analysis.documentation.resources import template_directory

export, __all__ = exporter()

ConfigOptionInfo = export(ConfigOptionInfo)
OutputFieldInfo = export(OutputFieldInfo)
DependencyDocumentationInfo = export(DependencyDocumentationInfo)
PluginDocumentationView = export(PluginDocumentationView)


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
            template_dir = template_directory()
        self.template_dir = template_dir
        self._plugins: list[tuple[type, Any]] = []  # (plugin_class, instance)
        self._load_errors: list[tuple[str, str]] = []
        self._jinja_env = None
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
        self._load_errors = []
        for cls in plugin_classes:
            try:
                instance = cls()
                provides = getattr(instance, "provides", None)
                if provides and provides not in seen_provides:
                    self._plugins.append((cls, instance))
                    seen_provides.add(provides)
            except Exception as exc:
                # Keep the failure visible to strict generation/coverage checks.
                self._load_errors.append((cls.__name__, repr(exc)))

        if self._load_errors:
            details = "; ".join(f"{name}: {error}" for name, error in self._load_errors)
            raise RuntimeError(f"无法实例化内置插件，文档生成已中止: {details}")
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

        # 依赖
        depends_on = list(getattr(plugin, "depends_on", []))

        # 配置选项
        config_options = self._extract_config_options(plugin)

        # 输出字段
        output_fields, output_kind = self._extract_output_fields(plugin)

        # 执行契约
        execution_kind = str(getattr(plugin, "output_kind", "static"))
        supports_streaming = execution_kind == "stream"
        is_side_effect = getattr(plugin, "is_side_effect", False)
        input_requirements = self._extract_input_requirements(plugin)

        # 模块路径
        module_path = plugin_class.__module__
        module_doc = self._extract_module_doc(module_path)

        # Structured documentation extensions shared by Help, Markdown, and HTML.
        agent_doc = self._extract_agent_doc(plugin_class, plugin)
        compute_notes = self._extract_compute_notes(plugin)
        behavior_notes = agent_doc["behavior_notes"] or self._derive_behavior_notes(
            plugin, module_doc, compute_notes
        )
        has_dynamic_dependencies = self._has_dynamic_dependencies(plugin)
        dependency_config_keys = self._extract_dependency_config_keys(plugin_class, plugin)
        dependency_fields = dict(input_requirements)
        dependency_fields.update(agent_doc["dependency_fields"])
        dependency_details = self._build_dependency_details(
            depends_on,
            resolution="dynamic" if has_dynamic_dependencies else "declared",
            dependency_notes=agent_doc["dependency_notes"],
            dependency_fields=dependency_fields,
        )
        output_summary = self._output_summary(plugin, output_kind, output_fields, description)
        workflow_steps = agent_doc["workflow_steps"] or self._derive_workflow_steps(
            plugin, provides, output_kind, depends_on
        )
        failure_modes = agent_doc["failure_modes"] or self._derive_failure_modes(
            plugin, provides, depends_on, has_dynamic_dependencies
        )
        derived_overview, derived_overview_paragraphs = self._derive_overview(plugin)
        overview = agent_doc["overview"] or derived_overview
        overview_paragraphs = agent_doc["overview_paragraphs"] or derived_overview_paragraphs
        overview_paragraphs = self._remove_duplicate_prose(overview_paragraphs, description)
        if overview and not overview_paragraphs:
            overview_paragraphs = [overview]
        execution_chain = self._build_execution_chain(
            depends_on,
            provides,
            has_dynamic_dependencies=has_dynamic_dependencies,
        )
        raw_usage_example = getattr(plugin, "doc_usage_example", "") or ""
        usage_example = (
            inspect.cleandoc(str(raw_usage_example))
            if raw_usage_example
            else self._derive_usage_example(plugin_class, plugin)
        )
        workflow_diagram = agent_doc["workflow_diagram"]
        source_fingerprint = self._source_fingerprint(plugin_class)
        resolved_details = [
            replace(
                detail,
                resolution="dynamic-default" if has_dynamic_dependencies else detail.resolution,
            )
            for detail in dependency_details
        ]

        return PluginDocumentationView(
            name=name,
            provides=provides,
            version=version,
            description=description,
            category=category,
            depends_on=depends_on,
            resolved_depends_on=list(depends_on),
            dependency_profile="declared" if not has_dynamic_dependencies else "runtime",
            dependency_config_keys=dependency_config_keys,
            config_options=config_options,
            output_fields=output_fields,
            output_kind=output_kind,
            execution_kind=execution_kind,
            save_when=str(getattr(plugin, "save_when", "never")),
            uses_run_config=bool(getattr(plugin, "uses_run_config", False)),
            timeout=getattr(plugin, "timeout", None),
            input_requirements=input_requirements,
            supports_streaming=supports_streaming,
            is_side_effect=is_side_effect,
            module_path=module_path,
            module_doc=module_doc,
            dependency_details=dependency_details,
            resolved_dependency_details=resolved_details,
            workflow_steps=workflow_steps,
            execution_chain=execution_chain,
            execution_notes=agent_doc["execution_notes"],
            output_summary=output_summary,
            has_dynamic_dependencies=has_dynamic_dependencies,
            behavior_notes=behavior_notes,
            field_notes=agent_doc["field_notes"],
            config_notes=agent_doc["config_notes"],
            cluster_contract=agent_doc["cluster_contract"],
            failure_modes=failure_modes,
            downstream_consumers=agent_doc["downstream_consumers"],
            downstream_notes=agent_doc["downstream_notes"],
            agent_change_notes=agent_doc["agent_change_notes"],
            overview=overview,
            overview_paragraphs=overview_paragraphs,
            usage_example=usage_example,
            documentation_status=agent_doc["documentation_status"],
            source_fingerprint=source_fingerprint,
            workflow_diagram=workflow_diagram,
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
            "workflow_diagram": str_value("workflow_diagram"),
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
    def _remove_duplicate_prose(paragraphs: list[str], description: str) -> list[str]:
        """Keep the overview readable when class and plugin descriptions repeat."""
        normalized_description = " ".join(str(description).split()).casefold()
        result: list[str] = []
        seen: set[str] = set()
        for paragraph in paragraphs:
            cleaned = " ".join(str(paragraph).split())
            normalized = cleaned.casefold()
            if not cleaned or normalized == normalized_description or normalized in seen:
                continue
            result.append(cleaned)
            seen.add(normalized)
        return result

    @staticmethod
    def _source_fingerprint(plugin_class: type) -> str | None:
        """Return the defining source fingerprint used by published AgentDocs."""
        from waveform_analysis.documentation.published_agent_docs import fingerprint_plugin_source

        return fingerprint_plugin_source(plugin_class)

    @staticmethod
    def _extract_input_requirements(plugin: Any) -> dict[str, list[str]]:
        """Extract structured input fields when a plugin declares input dtypes."""
        requirements: dict[str, list[str]] = {}
        for dependency, dtype in (getattr(plugin, "input_dtype", {}) or {}).items():
            try:
                names = list(np.dtype(dtype).names or ())
            except (TypeError, ValueError):
                names = []
            if names:
                requirements[str(dependency)] = names
        return requirements

    @staticmethod
    def _extract_dependency_config_keys(plugin_class: type, plugin: Any) -> list[str]:
        """Find configuration keys visibly consulted by ``resolve_depends_on``.

        This deliberately reports only literal keys present in the resolver source or
        declared options. It never infers a dependency branch from arbitrary code.
        """
        from waveform_analysis.core.plugins.core.base import Plugin

        resolver = type(plugin).resolve_depends_on
        if resolver is Plugin.resolve_depends_on:
            return []
        try:
            source = inspect.getsource(resolver)
            tree = ast.parse(textwrap.dedent(source))
        except (OSError, TypeError, SyntaxError):
            return []

        keys: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            attribute = function.attr if isinstance(function, ast.Attribute) else ""
            if attribute == "get_config" and len(node.args) >= 2:
                candidate = node.args[1]
                if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
                    keys.add(candidate.value)
            elif attribute == "get" and node.args:
                candidate = node.args[0]
                if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
                    keys.add(candidate.value)

        source_lower = source.casefold()
        for name in getattr(plugin, "options", {}) or {}:
            if re.search(rf"\b{re.escape(str(name))}\b", source_lower):
                keys.add(str(name))
        for name in DOCUMENTATION_DEFAULT_PROFILE:
            if re.search(rf"\b{re.escape(name)}\b", source_lower):
                keys.add(name)
        dependency_selector_keys = {
            "wave_source",
            "use_filtered",
            "daq_adapter",
            "input_source",
            "asymmetry_cut_enabled",
            "channel_role_cut_enabled",
            "clip_negative_signal",
        }
        keys.update(
            str(name)
            for name in getattr(plugin, "options", {}) or {}
            if str(name) in dependency_selector_keys
        )
        return sorted(keys)

    @classmethod
    def _derive_behavior_notes(
        cls, plugin: Any, module_doc: str, compute_notes: list[str]
    ) -> list[str]:
        """Build source-backed behavior notes when no authored narrative exists."""
        candidates = cls._docstring_narrative(module_doc)
        if not candidates:
            candidates = cls._docstring_narrative(inspect.cleandoc(type(plugin).__doc__ or ""))
        if candidates:
            return cls._remove_duplicate_prose(candidates, getattr(plugin, "description", ""))[:2]
        if compute_notes:
            return compute_notes[:2]
        provides = str(getattr(plugin, "provides", "output"))
        output_kind = str(getattr(getattr(plugin, "output_schema", None), "kind", "output"))
        return [
            f"通过 `compute(context, run_id)` 生成 `{provides}`；输出容器类型为 `{output_kind}`。"
        ]

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

    @classmethod
    def _derive_workflow_steps(
        cls, plugin: Any, provides: str, output_kind: str, depends_on: list[Any]
    ) -> list[str]:
        """Derive ordered "How It Works" steps from the compute docstring prose.

        Only the narrative preceding section markers (Args/Returns/...) is used; each
        narrative clause becomes a distinct, ordered step. A missing compute docstring
        yields no steps, so plugins whose narrative is authored elsewhere (agent_doc /
        published YAML) are never disturbed.
        """
        candidates = cls._docstring_narrative(cls._compute_docstring(plugin))
        if not candidates:
            candidates = cls._docstring_narrative(inspect.cleandoc(type(plugin).__doc__ or ""))
        if candidates:
            return candidates[:5]
        dependency_names = [cls._dependency_parts(dep)[0] for dep in depends_on]
        input_text = ", ".join(f"`{name}`" for name in dependency_names) or "插件配置和运行上下文"
        return [
            f"读取上游输入（{input_text}）。",
            f"调用 `compute(context, run_id)` 执行 `{provides}` 的处理逻辑。",
            f"返回 `{output_kind}` 形式的 `{provides}` 结果。",
        ]

    @staticmethod
    def _derive_failure_modes(
        plugin: Any,
        provides: str,
        depends_on: list[Any],
        has_dynamic_dependencies: bool,
    ) -> list[str]:
        """Describe only contract-level failure conditions when no authored list exists."""
        dependency_names = [PluginDocGenerator._dependency_parts(dep)[0] for dep in depends_on]
        if has_dynamic_dependencies:
            return [
                f"`{provides}` 的实际输入由 `resolve_depends_on(context, run_id)` 决定；默认画像之外的配置需要重新确认依赖是否可用。",
                "动态依赖无法解析、所需配置不合法或上游产物缺失时，插件不会生成有效输出。",
            ]
        if dependency_names:
            return [
                f"任一声明依赖（{', '.join(f'`{name}`' for name in dependency_names)}）缺失或字段不符合输入契约时，执行会失败。",
                "配置校验或输出 schema 校验失败时，结果不会被视为有效插件产物。",
            ]
        return [
            "配置校验失败或输入数据不满足插件实现的前置条件时，执行会失败。",
            "输出不符合声明的 dtype/schema 时，结果不会被视为有效插件产物。",
        ]

    @staticmethod
    def _derive_usage_example(plugin_class: type, plugin: Any) -> str:
        """Return a registration example based on the canonical CPU profile."""
        provides = str(getattr(plugin, "provides", "output"))
        if provides == "cache_analysis":
            module = plugin_class.__module__
            if module.startswith("waveform_analysis.core.plugins.builtin"):
                plugin_import = f"from waveform_analysis.plugins import {plugin_class.__name__}"
            else:
                plugin_import = f"from {module} import {plugin_class.__name__}"
            return inspect.cleandoc(
                f"""
                from waveform_analysis import Context
                {plugin_import}

                ctx = Context(config={{"data_root": "DAQ"}})
                ctx.register({plugin_class.__name__}())
                result = ctx.get_data("run_001", "{provides}")
                """
            )
        return inspect.cleandoc(
            f"""
            from waveform_analysis import Context
            from waveform_analysis.plugins import profiles

            ctx = Context(config={{"data_root": "DAQ", "daq_adapter": "vx2730"}})
            ctx.register(*profiles.cpu_default())
            result = ctx.get_data("run_001", "{provides}")
            """
        )

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
            for dep in consumer.resolved_depends_on or consumer.depends_on:
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
            resolved_details = [
                replace(
                    detail,
                    description=detail.description or descriptions.get(detail.name, ""),
                )
                for detail in view.resolved_dependency_details
            ]
            downstream = sorted(
                set(view.downstream_consumers) | consumers.get(view.provides, set())
            )
            enriched.append(
                replace(
                    view,
                    dependency_details=details,
                    resolved_dependency_details=resolved_details,
                    downstream_consumers=downstream,
                )
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
        declared_by_name = {detail.name: detail for detail in view.dependency_details}
        details = []
        for dependency in dependencies:
            name, version = self._dependency_parts(dependency)
            declared = declared_by_name.get(name)
            details.append(
                DependencyDocumentationInfo(
                    name=name,
                    version_constraint=version or (declared.version_constraint if declared else ""),
                    resolution=resolution,
                    required_fields=(
                        list(declared.required_fields)
                        if declared is not None
                        else list(view.input_requirements.get(name, []))
                    ),
                    description=(
                        declared.description
                        if declared is not None and declared.description
                        else descriptions.get(name, "")
                    ),
                )
            )
        default_values = dict(DOCUMENTATION_DEFAULT_PROFILE)
        default_values.update(DOCUMENTATION_PLUGIN_DEFAULTS.get(view.provides, {}))
        return replace(
            view,
            resolved_depends_on=list(dependencies),
            dependency_profile=(
                DOCUMENTATION_DEFAULT_PROFILE_NAME if resolution != "declared" else "declared"
            ),
            dependency_profile_values=(default_values if resolution != "declared" else {}),
            resolved_dependency_details=details,
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
                    internal_units=getattr(opt, "internal_unit", None),
                    choices=list(getattr(opt, "choices", None) or []),
                    min_value=getattr(opt, "min_value", None),
                    max_value=getattr(opt, "max_value", None),
                    deprecated_message=str(getattr(opt, "deprecated_message", "") or ""),
                    alias=getattr(opt, "alias", None),
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

    def get_all_doc_info(
        self, *, resolve_default_dependencies: bool = True
    ) -> list[PluginDocumentationView]:
        """获取所有插件的文档信息

        Returns:
            PluginDocInfo 列表
        """
        doc_infos = []
        for plugin_class, instance in self._plugins:
            try:
                doc_info = self.extract_doc_info(plugin_class, instance)
                doc_infos.append(doc_info)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to extract documentation for {getattr(instance, 'provides', plugin_class.__name__)!r}"
                ) from exc
        enriched = self.enrich_documentation_views(doc_infos)
        if not resolve_default_dependencies or not enriched:
            return enriched
        default_dependencies = self._default_dependency_map()
        resolved = []
        for view in enriched:
            dependencies = default_dependencies.get(view.provides, view.depends_on)
            resolution = "dynamic-default" if view.has_dynamic_dependencies else "declared"
            resolved.append(
                self.apply_dependency_resolution(
                    view,
                    dependencies,
                    resolution=resolution,
                    available_views=enriched,
                )
            )
        return self.enrich_documentation_views(resolved)

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
            default_profile_name=DOCUMENTATION_DEFAULT_PROFILE_NAME,
            default_profile_values=DOCUMENTATION_DEFAULT_PROFILE,
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
            else plugin.resolved_depends_on or plugin.depends_on
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

    def _with_lineage_scores(
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
    def _plugin_sets(plugins: list[PluginDocumentationView]) -> list[_PluginSetDocumentation]:
        """Group documentation views by the canonical execution plugin sets."""
        from waveform_analysis.core.plugins.plugin_sets import PLUGIN_SETS

        by_provides = {plugin.provides: plugin for plugin in plugins}
        assigned: set[str] = set()
        groups: list[_PluginSetDocumentation] = []
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
                    _PluginSetDocumentation(
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
                _PluginSetDocumentation(
                    name="other",
                    label="其他插件",
                    plugins=remaining,
                    description="未归入上述集合的补充插件。",
                )
            )
        return groups

    @classmethod
    def _terminal_outputs(cls, plugins, dependencies_by_provides):
        names = {
            plugin.provides
            for plugin in plugins
            if plugin.provides not in STANDALONE_PLUGIN_OUTPUTS
        }
        consumed = {
            dependency
            for plugin in plugins
            if plugin.provides in names
            for dependency in dependencies_by_provides.get(plugin.provides, [])
            if dependency in names
        }
        return names - consumed - {CORE_TERMINAL_OUTPUT}

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
        from waveform_analysis.visualization.lineage_visualizer import (
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
            for group in self._plugin_sets(graph_plugins)
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
                        "href": (f"{plugin_href_prefix.rstrip('/')}/{plugin.provides}/"),
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

        plugins = self._with_lineage_scores(
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
                # Use the same default dependency profile as full generation so a
                # single-page refresh cannot silently regress to an unresolved
                # runtime-only dependency view.
                doc_info = next(
                    (
                        item
                        for item in self.get_all_doc_info()
                        if item.provides == getattr(instance, "provides", None)
                    ),
                    self.extract_doc_info(plugin_class, instance),
                )
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


check_plugin_document_structure = export(check_plugin_document_structure)
check_plugin_document = export(check_plugin_document)
