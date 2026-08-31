"""Compose plugin and curated documentation into one offline site."""

from dataclasses import replace
import hashlib
import inspect
import json
from pathlib import Path, PurePosixPath
import posixpath
import shutil
from typing import Any

from markupsafe import Markup
import numpy as np

from waveform_analysis.documentation.plugin_doc_generator import PluginDocGenerator
from waveform_analysis.documentation.site_guides import (
    RenderedGuideSection,
    RenderedGuideSite,
    load_guide_manifest,
    render_guide_manifest,
)

from .catalog import (
    ACCESSOR_DOCUMENTATION_REGISTRY,
    ACCESSOR_SELECTION_GUIDE,
    ADAPTER_DOCUMENTATION_PAGE,
    CONTEXT_DOCUMENTATION_PAGE,
    RECORDS_VIEW_DOCUMENTATION_PAGE,
    VISUALIZATION_DOCUMENTATION_PAGES,
)
from .models import (
    AccessorDocumentationSpec,
    AccessorDocumentationView,
    AccessorMemberSpec,
    AccessorMemberView,
    AccessorNarrativeSection,
    AccessorParameterSpec,
    AccessorSelectionGuideItem,
    CallableDocumentationGroup,
    CallableDocumentationPageSpec,
    CallableDocumentationPageView,
    CallableDocumentationSpec,
    CallableDocumentationView,
    ContentDocumentationSection,
    DocumentationContentBlock,
)
from .rendering import _highlight_python, _inline_code, _safe_mathml

__all__ = [
    "ACCESSOR_DOCUMENTATION_REGISTRY",
    "ACCESSOR_SELECTION_GUIDE",
    "ADAPTER_DOCUMENTATION_PAGE",
    "CONTEXT_DOCUMENTATION_PAGE",
    "RECORDS_VIEW_DOCUMENTATION_PAGE",
    "VISUALIZATION_DOCUMENTATION_PAGES",
    "AccessorDocumentationSpec",
    "AccessorDocumentationView",
    "AccessorMemberSpec",
    "AccessorMemberView",
    "AccessorNarrativeSection",
    "AccessorParameterSpec",
    "AccessorSelectionGuideItem",
    "CallableDocumentationGroup",
    "CallableDocumentationPageSpec",
    "CallableDocumentationPageView",
    "CallableDocumentationSpec",
    "CallableDocumentationView",
    "ContentDocumentationSection",
    "DocumentationContentBlock",
    "DocumentationSiteGenerator",
]


class DocumentationSiteGenerator:
    """Compose plugin and curated Accessor documentation into one offline site."""

    def __init__(
        self,
        plugin_generator: PluginDocGenerator | None = None,
        accessor_registry: tuple[AccessorDocumentationSpec, ...] = ACCESSOR_DOCUMENTATION_REGISTRY,
        guide_manifest_path: Path | None = None,
    ):
        self.plugin_generator = plugin_generator or PluginDocGenerator()
        self.accessor_registry = accessor_registry
        self.guide_manifest_path = (
            Path(guide_manifest_path)
            if guide_manifest_path is not None
            else Path.cwd() / "docs" / "site-guides.yaml"
        )
        self.guide_warnings: tuple[str, ...] = ()

    @staticmethod
    def _route_href(current_route: str, target_route: str) -> str:
        return posixpath.relpath(target_route, PurePosixPath(current_route).parent.as_posix())

    @staticmethod
    def _route_context(output_dir: Path, route: str) -> dict[str, str]:
        page_dir = (output_dir / route).parent
        root_prefix = Path(posixpath.relpath(output_dir, page_dir)).as_posix()
        root_prefix = "" if root_prefix == "." else f"{root_prefix}/"
        return {
            "asset_prefix": f"{root_prefix}assets/",
            "site_root_prefix": root_prefix,
            "site_home_href": f"{root_prefix}index.html",
            "plugin_index_href": f"{root_prefix}plugins/index.html",
            "plugin_system_href": f"{root_prefix}plugins/overview.html",
            "accessor_index_href": f"{root_prefix}accessors/index.html",
            "accessor_detail_prefix": f"{root_prefix}accessors/",
            "context_index_href": f"{root_prefix}contexts/context.html",
            "adapter_index_href": f"{root_prefix}adapters/adapter.html",
            "visualization_index_href": f"{root_prefix}visualizations/index.html",
            "visualization_detail_prefix": f"{root_prefix}visualizations/",
        }

    def _rendered_guides(self) -> RenderedGuideSite:
        if not self.guide_manifest_path.is_file():
            self.guide_warnings = ()
            return RenderedGuideSite(sections=(), warnings=())
        rendered = render_guide_manifest(load_guide_manifest(self.guide_manifest_path))
        self.guide_warnings = rendered.warnings
        return rendered

    def _publish_guides(
        self,
        *,
        output_dir: Path,
        rendered: RenderedGuideSite,
        generated: dict[str, Path],
        env: Any,
    ) -> None:
        occupied = {path.resolve() for path in generated.values()}
        copied_assets: set[str] = set()
        if any(page.has_mermaid for section in rendered.sections for page in section.pages):
            mermaid_dir = self.plugin_generator.template_dir / "web" / "assets" / "mermaid"
            for name in ("mermaid.min.js", "MERMAID-LICENSE.txt"):
                source = mermaid_dir / name
                if not source.is_file():
                    raise ValueError(f"Mermaid asset is missing: {source}")
                target = output_dir / "assets" / "mermaid" / name
                if target.resolve() in occupied:
                    raise ValueError(f"Mermaid asset collides with generated site output: {name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                generated[f"asset:mermaid/{name}"] = target
                occupied.add(target.resolve())
        for section in rendered.sections:
            index_path = output_dir / section.index_route
            if index_path.resolve() in occupied:
                # Provider-only sections can use a richer index generated by the
                # site generator (for example contexts/index.html).  Keep that
                # canonical route instead of replacing it with an empty guide index.
                if not all(page.html is None for page in section.pages):
                    raise ValueError(
                        f"Guide route collides with generated site page: {section.index_route}"
                    )
            else:
                index_path.parent.mkdir(parents=True, exist_ok=True)
                index_path.write_text(
                    env.get_template("web/guide_index.html.j2").render(
                        section=section,
                        **self._route_context(output_dir, section.index_route),
                    ),
                    encoding="utf-8",
                )
            generated[f"guide-index:{section.section_id}"] = index_path
            occupied.add(index_path.resolve())
            for page in section.pages:
                if page.html is None:
                    continue
                page_path = output_dir / page.route
                if page_path.resolve() in occupied:
                    raise ValueError(f"Guide route collides with generated site page: {page.route}")
                page_path.parent.mkdir(parents=True, exist_ok=True)
                page_path.write_text(
                    env.get_template("web/guide.html.j2").render(
                        page=replace(page, html=Markup(page.html)),
                        section=section,
                        section_index_href=self._route_href(page.route, section.index_route),
                        **self._route_context(output_dir, page.route),
                    ),
                    encoding="utf-8",
                )
                generated[f"guide:{page.source_label}"] = page_path
                occupied.add(page_path.resolve())
                for asset in page.assets:
                    if asset.route in copied_assets:
                        continue
                    target = output_dir / asset.route
                    if target.resolve() in occupied:
                        raise ValueError(
                            f"Guide asset collides with generated site output: {asset.route}"
                        )
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(asset.source, target)
                    generated[f"guide-asset:{asset.route}"] = target
                    copied_assets.add(asset.route)
                    occupied.add(target.resolve())

    def build_accessor_views(self) -> list[AccessorDocumentationView]:
        views = []
        slugs: set[str] = set()
        for spec in self.accessor_registry:
            if spec.slug in slugs:
                raise ValueError(f"Duplicate Accessor documentation slug: {spec.slug}")
            slugs.add(spec.slug)
            members = []
            for member_spec in spec.members:
                try:
                    raw_member = inspect.getattr_static(spec.accessor_class, member_spec.name)
                except AttributeError as exc:
                    raise ValueError(
                        f"Registered member {spec.accessor_class.__name__}.{member_spec.name} does not exist"
                    ) from exc
                is_property = isinstance(raw_member, property)
                expected_property = member_spec.kind == "property"
                if is_property != expected_property:
                    raise ValueError(
                        f"Registered member kind mismatch for {spec.accessor_class.__name__}.{member_spec.name}"
                    )
                target: Any = raw_member.fget if is_property else raw_member
                if target is None or not callable(target):
                    raise ValueError(
                        f"Registered member {spec.accessor_class.__name__}.{member_spec.name} is not callable"
                    )
                signature = inspect.signature(target)
                rendered_signature = self._format_signature(signature)
                members.append(
                    AccessorMemberView(
                        name=member_spec.name,
                        kind=member_spec.kind,
                        signature=rendered_signature,
                        signature_html=_highlight_python(
                            f"def {member_spec.name}{rendered_signature}:"
                        ),
                        description=member_spec.description,
                        parameters=self._validated_parameters(
                            signature,
                            member_spec.parameters,
                            f"{spec.accessor_class.__name__}.{member_spec.name}",
                        ),
                        returns=member_spec.returns,
                        notes=member_spec.notes,
                        example_html=(
                            _highlight_python(member_spec.example)
                            if member_spec.example
                            else Markup("")
                        ),
                    )
                )
            constructor_signature = inspect.signature(spec.accessor_class)
            views.append(
                AccessorDocumentationView(
                    name=spec.accessor_class.__name__,
                    slug=spec.slug,
                    module_path=spec.accessor_class.__module__,
                    summary=spec.summary,
                    introduction=spec.introduction,
                    purpose=spec.purpose,
                    example_html=_highlight_python(spec.example),
                    constructor_signature=str(constructor_signature),
                    constructor_parameters=self._validated_parameters(
                        constructor_signature,
                        spec.constructor_parameters,
                        spec.accessor_class.__name__,
                    ),
                    members=tuple(members),
                    narrative_sections=spec.narrative_sections,
                    overview_title=spec.overview_title,
                    overview_blocks=spec.overview_blocks,
                )
            )
        return views

    def build_callable_page_view(
        self, spec: CallableDocumentationPageSpec
    ) -> CallableDocumentationPageView:
        groups = []
        for group in spec.groups:
            members = tuple(
                CallableDocumentationView(
                    name=item.name,
                    signature_html=_highlight_python(
                        f"{'class' if item.kind == 'class' else 'def'} {item.name}"
                        f"{self._format_signature(inspect.signature(item.callable))}:"
                    ),
                    description=item.description,
                    parameters=self._validated_parameters(
                        inspect.signature(item.callable), item.parameters, item.name
                    ),
                    returns=item.returns,
                    notes=item.notes,
                    example_html=_highlight_python(item.example) if item.example else Markup(""),
                    kind=item.kind,
                )
                for item in group.members
            )
            groups.append((group, members))
        has_mermaid = any(
            block.kind == "mermaid"
            for section in spec.narrative_sections
            for block in section.blocks
        )
        return CallableDocumentationPageView(
            slug=spec.slug,
            title=spec.title,
            eyebrow=spec.eyebrow,
            summary=spec.summary,
            introduction=spec.introduction,
            groups=tuple(groups),
            narrative_sections=spec.narrative_sections,
            has_mermaid=has_mermaid,
        )

    @staticmethod
    def _format_signature(signature: inspect.Signature, max_width: int = 96) -> str:
        """Render long callable signatures one parameter per line for the HTML reference."""
        rendered = str(signature)
        if len(rendered) <= max_width:
            return rendered

        parameters = ",\n".join(f"    {parameter}" for parameter in signature.parameters.values())
        return_annotation = ""
        if signature.return_annotation is not inspect.Signature.empty:
            annotation = signature.return_annotation
            if annotation is np.ndarray:
                annotation = "np.ndarray"
            return_annotation = f" -> {annotation}"
        return f"(\n{parameters},\n){return_annotation}"

    @staticmethod
    def _validated_parameters(
        signature: inspect.Signature,
        documented: tuple[AccessorParameterSpec, ...],
        subject: str,
    ) -> tuple[AccessorParameterSpec, ...]:
        """Keep prose descriptions synchronized with the live callable signature."""
        live_names = tuple(name for name in signature.parameters if name != "self")
        documented_names = tuple(parameter.name for parameter in documented)
        if live_names != documented_names:
            raise ValueError(
                f"Registered parameter names for {subject} do not match signature: "
                f"expected {live_names}, got {documented_names}"
            )
        return documented

    def _copy_content_assets(
        self,
        views: list[AccessorDocumentationView],
        asset_dir: Path,
        generated: dict[str, Path],
    ) -> None:
        """Copy only registry-referenced documentation images into the offline site."""
        source_dir = self.plugin_generator.template_dir / "web" / "content-assets"
        image_sources = {
            block.image_src
            for view in views
            for section in view.narrative_sections
            for block in section.blocks
            if block.kind == "image"
        }
        for image_src in sorted(image_sources):
            relative_path = Path(PurePosixPath(image_src))
            source_path = source_dir / relative_path
            if not source_path.is_file():
                raise ValueError(
                    f"Documentation image {image_src!r} is not present in {source_dir}"
                )
            target_path = asset_dir / "content" / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            generated[f"asset:content/{image_src}"] = target_path

    def generate(self, output_dir: Path) -> dict[str, Path]:
        output_dir = Path(output_dir)
        rendered_guides = self._rendered_guides()
        guide_route_map = {
            page.source_label: page.route
            for section in rendered_guides.sections
            for page in section.pages
        }
        self.plugin_generator.load_builtin_plugins()
        views = self.build_accessor_views()
        context_view = self.build_callable_page_view(CONTEXT_DOCUMENTATION_PAGE)
        records_view_page = self.build_callable_page_view(RECORDS_VIEW_DOCUMENTATION_PAGE)
        visualization_views = [
            self.build_callable_page_view(spec) for spec in VISUALIZATION_DOCUMENTATION_PAGES
        ]
        adapter_view = self.build_callable_page_view(ADAPTER_DOCUMENTATION_PAGE)
        site_search_entries = [
            {
                "title": "Context 与 Plugin 入门",
                "summary": "Context 管理 run_id、配置、插件依赖和缓存；Plugin 负责产出具名数据。",
                "kind": "入门",
                "url": "index.html#context-and-plugin",
                "keywords": "Context Plugin 插件 DAG run_id 配置 缓存 依赖",
            },
            {
                "title": "Context 最小流程",
                "summary": "创建 Context、注册 cpu_default 插件集，再通过 get_data 请求目标产物。",
                "kind": "入门",
                "url": "index.html#minimal-workflow",
                "keywords": "Context register cpu_default get_data peaks run_id 最小示例",
            },
        ]
        for view in views:
            base_url = f"accessors/{view.slug}.html"
            site_search_entries.extend(
                {
                    "title": view.name,
                    "summary": view.summary,
                    "kind": "Accessor",
                    "url": f"{base_url}{anchor}",
                    "keywords": f"{view.name} {view.summary} {heading}",
                }
                for heading, anchor in (
                    ("整体介绍", "#overview"),
                    ("构造器", "#constructor"),
                    ("快速开始", "#quickstart"),
                    ("公开成员", "#members"),
                )
            )
        for view in (context_view, records_view_page, adapter_view, *visualization_views):
            section = (
                "contexts"
                if view.slug in {"context", "records-view"}
                else "adapters" if view.slug == "adapter" else "visualizations"
            )
            for group, members in view.groups:
                site_search_entries.append(
                    {
                        "title": f"{view.title}: {group.title}",
                        "summary": group.description,
                        "kind": (
                            "Context"
                            if section == "contexts"
                            else "DAQ 适配器" if section == "adapters" else "可视化"
                        ),
                        "url": f"{section}/{view.slug}.html#{group.anchor}",
                        "keywords": f"{view.title} {group.title} "
                        + " ".join(member.name for member in members),
                    }
                )
            for narrative_section in view.narrative_sections:
                site_search_entries.append(
                    {
                        "title": f"{view.title}: {narrative_section.title}",
                        "summary": view.summary,
                        "kind": "Context",
                        "url": f"{section}/{view.slug}.html#{narrative_section.anchor}",
                        "keywords": (
                            f"{view.title} records wave_pool {narrative_section.title} "
                            "RecordsBundle wave_offset event_length records_view V1725 "
                            "ExecutorManager BatchProcessor thread process parallel_map"
                        ),
                    }
                )
        for guide_section in rendered_guides.sections:
            for page in guide_section.pages:
                if page.html is None:
                    continue
                site_search_entries.append(
                    {
                        "title": page.title,
                        "summary": page.summary,
                        "kind": guide_section.title,
                        "url": page.route,
                        "keywords": f"{guide_section.title} {page.title} {page.summary}",
                    }
                )
                site_search_entries.extend(
                    {
                        "title": f"{page.title}: {heading.title}",
                        "summary": page.summary,
                        "kind": guide_section.title,
                        "url": f"{page.route}#{heading.anchor}",
                        "keywords": f"{guide_section.title} {page.title} {heading.title}",
                    }
                    for heading in page.headings
                    if heading.level in {2, 3}
                )
        env = self.plugin_generator._get_web_jinja_env()
        env.filters["inline_code"] = _inline_code
        env.filters["mathml"] = _safe_mathml
        env.filters["guide_relative"] = lambda target_route, current_route: self._route_href(
            current_route, target_route
        )
        mermaid_asset = (
            self.plugin_generator.template_dir / "web" / "assets" / "mermaid" / "mermaid.min.js"
        )
        env.globals["mermaid_asset_version"] = (
            hashlib.sha256(mermaid_asset.read_bytes()).hexdigest()[:12]
            if mermaid_asset.is_file()
            else ""
        )
        env.globals["guide_sections"] = rendered_guides.sections
        env.globals["guide_route_map"] = guide_route_map
        generated = self.plugin_generator.generate_web(
            output_dir,
            index_relative_path="plugins/index.html",
            plugin_relative_dir="plugins",
            asset_relative_dir="assets",
            site_home_href="index.html",
            accessor_relative_path="accessors/index.html",
            context_relative_path="contexts/context.html",
            adapter_relative_path="adapters/adapter.html",
            visualization_relative_path="visualizations/index.html",
            extra_search_entries=site_search_entries,
        )
        # Keep the historical root URL as a full-site DAG page.  The plugin
        # reference itself lives under ``plugins/``, but users and LAN links
        # commonly open ``/lineage.html`` directly.
        root_lineage_payload = self.plugin_generator._build_cytoscape_lineage_payload(
            self.plugin_generator._with_web_scores(
                self.plugin_generator.get_all_doc_info(),
                dependencies_by_provides=self.plugin_generator._default_dependency_map(),
            ),
            self.plugin_generator._default_dependency_map(),
            plugin_href_prefix="plugins/",
        )
        root_lineage_json = (
            json.dumps(root_lineage_payload, ensure_ascii=True, separators=(",", ":"))
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
        )
        react_assets = self.plugin_generator.template_dir / "web" / "assets" / "react"
        react_asset_version = hashlib.sha256(
            (react_assets / "waveform-docs.js").read_bytes()
            + (react_assets / "waveform-docs.css").read_bytes()
        ).hexdigest()[:12]
        root_lineage_path = output_dir / "lineage.html"
        root_lineage_path.write_text(
            self.plugin_generator.render_lineage_html(
                lineage_json=root_lineage_json,
                asset_prefix="assets/",
                site_home_href="index.html",
                plugin_index_href="plugins/index.html",
                plugin_href_prefix="plugins/",
                accessor_index_href="accessors/index.html",
                context_index_href="contexts/context.html",
                adapter_index_href="adapters/adapter.html",
                visualization_index_href="visualizations/index.html",
                visualization_detail_prefix="visualizations/",
                site_root_prefix="",
                react_asset_version=react_asset_version,
                lineage_index_href="lineage.html",
            ),
            encoding="utf-8",
        )
        generated["ROOT_LINEAGE"] = root_lineage_path
        self._copy_content_assets(views, output_dir / "assets", generated)
        accessor_dir = output_dir / "accessors"
        accessor_dir.mkdir(parents=True, exist_ok=True)
        home_path = output_dir / "index.html"
        context_plugin_example = """from waveform_analysis import Context
from waveform_analysis.plugins import profiles

run_id = \"run_001\"
ctx = Context(config={\"data_root\": \"DAQ\", \"daq_adapter\": \"vx2730\"})
ctx.register(*profiles.cpu_default())

# Context resolves the plugin DAG and reuses available cache entries.
peaks = ctx.get_data(run_id, \"peaks\")"""
        home_path.write_text(
            env.get_template("web/site_index.html.j2").render(
                accessor_count=len(views),
                context_view=context_view,
                visualization_views=visualization_views,
                context_plugin_example_html=_highlight_python(context_plugin_example),
            ),
            encoding="utf-8",
        )
        generated["SITE_INDEX"] = home_path
        accessor_index = accessor_dir / "index.html"
        accessor_index.write_text(
            env.get_template("web/accessor_index.html.j2").render(
                accessors=views,
                selection_guide=ACCESSOR_SELECTION_GUIDE,
            ),
            encoding="utf-8",
        )
        generated["ACCESSOR_INDEX"] = accessor_index
        for view in views:
            path = accessor_dir / f"{view.slug}.html"
            path.write_text(
                env.get_template("web/accessor.html.j2").render(accessor=view),
                encoding="utf-8",
            )
            generated[f"accessor:{view.slug}"] = path
        context_dir = output_dir / "contexts"
        context_dir.mkdir(parents=True, exist_ok=True)
        context_adapter_intro_blocks = (
            DocumentationContentBlock(
                kind="paragraph",
                text=(
                    "`Context` 是分析运行时的协调层：它管理显式 `run_id`、插件 DAG、配置解析、"
                    "lineage 与缓存复用。DAQ 适配器是硬件无关边界：它将不同数字化仪的文件格式、"
                    "目录布局和时间戳语义收敛为统一输入。"
                ),
            ),
            DocumentationContentBlock(
                kind="table",
                table_headers=("层", "职责", "边界"),
                table_rows=(
                    (
                        "Context",
                        "协调 DAG、配置、lineage 与缓存",
                        "不解析具体 DAQ 文件格式，也不保存隐式当前运行",
                    ),
                    (
                        "DAQ 适配器",
                        "描述格式读取、目录布局、采样率与时间戳语义",
                        "不决定插件算法、依赖图或缓存策略",
                    ),
                    (
                        "插件链路",
                        "将 `raw_files` 构建为 `records`、`wave_pool` 与后续分析产物",
                        "处理行为由插件配置和已解析的 adapter 信息共同约束",
                    ),
                ),
            ),
            DocumentationContentBlock(
                kind="paragraph",
                text=(
                    "典型 records-backed 数据流为 `raw_files -> records + wave_pool -> "
                    "(wave_pool_filtered) -> features/hit`。需要波形访问时，使用 "
                    "`records_view(ctx, run_id)` 读取正式产物。"
                ),
            ),
            DocumentationContentBlock(
                kind="note",
                tone="important",
                title="配置与复用",
                text=(
                    '将已注册 adapter 的名称配置到 `Context(config={"daq_adapter": ...})`。'
                    "显式插件配置优先于 adapter 推断，adapter 推断优先于插件默认值；"
                    "adapter 与已解析配置参与 lineage 和缓存键。"
                ),
            ),
        )
        context_index = context_dir / "index.html"
        context_index.write_text(
            env.get_template("web/callable_index.html.j2").render(
                title="Context 与适配器",
                eyebrow="分析运行时与硬件边界",
                summary="Context 负责配置、插件依赖与缓存；DAQ 适配器负责统一原始数据格式、目录布局与时间语义。",
                pages=(
                    replace(context_view, href="context.html"),
                    replace(adapter_view, href="../adapters/adapter.html"),
                ),
                current_section="contexts",
                intro_title="架构职责与数据流",
                intro_blocks=context_adapter_intro_blocks,
            ),
            encoding="utf-8",
        )
        generated["CONTEXT_INDEX"] = context_index
        context_path = context_dir / "context.html"
        context_path.write_text(
            env.get_template("web/callable_reference.html.j2").render(
                page=context_view,
                current_section="contexts",
                index_title="Context",
                related_guide_href="../architecture/system.html",
                related_guide_label="系统架构与执行器边界",
            ),
            encoding="utf-8",
        )
        generated["context:context"] = context_path
        records_view_path = context_dir / "records-view.html"
        records_view_path.write_text(
            env.get_template("web/callable_reference.html.j2").render(
                page=records_view_page,
                current_section="contexts",
                index_title="Context 与适配器",
                related_guide_href="../architecture/data-products.html",
                related_guide_label="数据产物与波形访问（架构文档）",
            ),
            encoding="utf-8",
        )
        generated["context:records-view"] = records_view_path
        legacy_route = "contexts/records-wave-pool.html"
        records_wave_pool_path = output_dir / legacy_route
        records_wave_pool_path.write_text(
            env.get_template("web/guide_redirect.html.j2").render(
                title="Records + WavePool",
                target_href="records-view.html#data-model",
                **self._route_context(output_dir, legacy_route),
            ),
            encoding="utf-8",
        )
        generated["context:records-wave-pool"] = records_wave_pool_path
        adapter_dir = output_dir / "adapters"
        adapter_dir.mkdir(parents=True, exist_ok=True)
        adapter_index = adapter_dir / "index.html"
        adapter_index.write_text(
            env.get_template("web/callable_index.html.j2").render(
                title="Context 与适配器",
                eyebrow="分析运行时与硬件边界",
                summary="Context 负责配置、插件依赖与缓存；DAQ 适配器负责统一原始数据格式、目录布局与时间语义。",
                pages=(
                    replace(context_view, href="../contexts/context.html"),
                    replace(adapter_view, href="adapter.html"),
                ),
                current_section="adapters",
                intro_title="架构职责与数据流",
                intro_blocks=context_adapter_intro_blocks,
            ),
            encoding="utf-8",
        )
        generated["ADAPTER_INDEX"] = adapter_index
        adapter_path = adapter_dir / "adapter.html"
        adapter_path.write_text(
            env.get_template("web/callable_reference.html.j2").render(
                page=adapter_view, current_section="adapters", index_title="DAQ 适配器"
            ),
            encoding="utf-8",
        )
        generated["adapter:adapter"] = adapter_path
        visualization_dir = output_dir / "visualizations"
        visualization_dir.mkdir(parents=True, exist_ok=True)
        visualization_index = visualization_dir / "index.html"
        visualization_index.write_text(
            env.get_template("web/callable_index.html.j2").render(
                title="可视化",
                eyebrow="参考",
                summary="统计图与波形图的公开绘图接口。",
                pages=visualization_views,
                current_section="visualizations",
            ),
            encoding="utf-8",
        )
        generated["VISUALIZATION_INDEX"] = visualization_index
        for view in visualization_views:
            path = visualization_dir / f"{view.slug}.html"
            path.write_text(
                env.get_template("web/callable_reference.html.j2").render(
                    page=view, current_section="visualizations", index_title="可视化"
                ),
                encoding="utf-8",
            )
            generated[f"visualization:{view.slug}"] = path
        self._publish_guides(
            output_dir=output_dir,
            rendered=rendered_guides,
            generated=generated,
            env=env,
        )

        # The consolidated Markdown guide owns the canonical plugin-system URL.
        # Keep the routes used by earlier site versions as lightweight aliases.
        plugin_overview_path = output_dir / "plugins" / "overview.html"
        generated["PLUGIN_OVERVIEW"] = plugin_overview_path
        for legacy_route, title in (
            ("plugins/system.html", "插件系统介绍"),
            ("plugins/template-api.html", "插件模板的 API 介绍"),
            ("plugins/authoring.html", "编写插件"),
            ("architecture/CONTEXT_PROCESSOR_WORKFLOW.html", "Context 处理工作流"),
            ("features/advanced/EXECUTOR_MANAGER_GUIDE.html", "全局执行器管理框架"),
        ):
            legacy_path = output_dir / legacy_route
            target_href = "overview.html"
            if legacy_route.startswith("architecture/"):
                target_href = "../contexts/context.html#execution-framework"
            elif legacy_route.startswith("features/"):
                target_href = "../../contexts/context.html#execution-framework"
            legacy_path.write_text(
                env.get_template("web/guide_redirect.html.j2").render(
                    title=title,
                    target_href=target_href,
                    **self._route_context(output_dir, legacy_route),
                ),
                encoding="utf-8",
            )
            generated[f"legacy:{legacy_route}"] = legacy_path
        generated["PLUGIN_AUTHORING"] = output_dir / "plugins" / "authoring.html"
        return generated
