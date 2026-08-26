from pathlib import Path

import pytest

from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator
from waveform_analysis.utils.site_guides import load_guide_manifest, render_guide_manifest


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _manifest(project: Path, body: str) -> Path:
    path = project / "docs" / "site-guides.yaml"
    _write(path, body)
    return path


def test_repository_manifest_publishes_plugin_bundle_guide():
    manifest_path = Path(__file__).parents[1] / "docs" / "site-guides.yaml"

    rendered = render_guide_manifest(load_guide_manifest(manifest_path))
    pages = {page.route: page for section in rendered.sections for page in section.pages}
    overview = pages["plugins/overview.html"]

    assert overview.title == "插件系统与模板 API"
    assert any(heading.title == "Canonical Bundle 与兼容转发" for heading in overview.headings)
    assert any(heading.title == "Plugin Sets" for heading in overview.headings)
    assert any(heading.title == "Profiles" for heading in overview.headings)
    bundle_warnings = [w for w in rendered.warnings if "PLUGIN_BUNDLE_GUIDE" in w]
    assert not bundle_warnings
    adapter = pages["plugins/reference/ADAPTER_SYSTEM_GUIDE.html"]
    assert "DAQ 适配器" in adapter.title
    assert not any("ADAPTER_SYSTEM_GUIDE.md" in warning for warning in rendered.warnings)
    position_dashboard = pages["features/visualizations/POSITION_DASHBOARD_GUIDE.html"]
    assert position_dashboard.title == "位置二维 Dashboard"
    assert "plugins/tutorials/SIGNAL_PROCESSING_PLUGINS.html" not in pages


def test_manifest_renders_markdown_and_rewrites_selected_links_and_assets(tmp_path):
    _write(
        tmp_path / "docs" / "guides" / "start.md",
        """**导航**: [文档中心](../README.md)

# 快速开始

这是摘要。

## 中文标题

[本页目录](#%E4%B8%AD%E6%96%87%E6%A0%87%E9%A2%98)
[架构](../architecture/design.md#%E6%95%B0%E6%8D%AE%E6%A8%A1%E5%9E%8B)
[插件](../plugins/reference/agent/records.md)
[未收录](hidden.md)

| 字段 | 含义 |
| --- | --- |
| record_id | 稳定标识 |

```python
value = 1
```

![示意图](plot.png)

脚注[^one]

[^one]: 脚注正文
""",
    )
    _write(
        tmp_path / "docs" / "architecture" / "design.md",
        "# 架构\n\n## 数据模型\n\n架构正文。\n",
    )
    (tmp_path / "docs" / "guides" / "plot.png").write_bytes(b"png")
    manifest_path = _manifest(
        tmp_path,
        """schema_version: 1
sections:
  - id: guides
    title: 用户指南
    index_route: guides/index.html
    pages:
      - source: docs/guides/start.md
        route: guides/deep/start.html
  - id: architecture
    title: 架构设计
    index_route: architecture/index.html
    pages:
      - source: docs/architecture/design.md
        route: architecture/design.html
""",
    )

    rendered = render_guide_manifest(load_guide_manifest(manifest_path))
    page = rendered.sections[0].pages[0]

    assert page.title == "快速开始"
    assert page.summary == "这是摘要。"
    assert "文档中心" not in page.html
    assert 'id="中文标题"' in page.html
    assert 'href="#中文标题"' in page.html
    assert 'href="../../architecture/design.html#数据模型"' in page.html
    assert 'href="../../plugins/records.html"' in page.html
    assert '<span class="guide-link-unavailable"' in page.html
    assert "<table>" in page.html
    assert '<pre class="code-block language-python"><code><span class=' in page.html
    assert 'src="../../assets/content/guides/plot.png"' in page.html
    assert "footnotes" in page.html
    assert page.assets[0].route == "assets/content/guides/plot.png"
    assert rendered.warnings == ("未收录 Markdown 链接: docs/guides/start.md -> hidden.md",)


def test_rendered_body_tracks_markdown_as_the_single_source_of_truth(tmp_path):
    source = tmp_path / "docs" / "guide.md"
    _write(source, "# 标题\n\n第一版正文。\n")
    manifest_path = _manifest(
        tmp_path,
        """schema_version: 1
sections:
  - id: guides
    title: 用户指南
    index_route: guides/index.html
    pages:
      - source: docs/guide.md
        route: guides/guide.html
""",
    )

    first = render_guide_manifest(load_guide_manifest(manifest_path)).sections[0].pages[0]
    _write(source, "# 标题\n\n第二版正文。\n")
    second = render_guide_manifest(load_guide_manifest(manifest_path)).sections[0].pages[0]

    assert "第一版正文" in first.html
    assert "第二版正文" not in first.html
    assert "第二版正文" in second.html


def test_manifest_renders_mermaid_flowchart_td_as_offline_svg(tmp_path):
    _write(
        tmp_path / "docs" / "guide.md",
        """# 流程图

```mermaid
flowchart TD
    START[开始] --> CHECK[检查缓存]
    CHECK -->|未命中| BUILD[构建结果]
    CHECK -->|命中| RETURN[返回结果]
```
""",
    )
    manifest_path = _manifest(
        tmp_path,
        """schema_version: 1
sections:
  - id: guides
    title: 用户指南
    index_route: guides/index.html
    pages:
      - source: docs/guide.md
        route: guides/guide.html
""",
    )

    page = render_guide_manifest(load_guide_manifest(manifest_path)).sections[0].pages[0]

    assert page.has_mermaid is True
    assert '<div class="mermaid-block" data-mermaid-block>' in page.html
    assert '<div class="mermaid-render" data-mermaid-render' in page.html
    assert "开始" in page.html
    assert "未命中" in page.html
    assert "flowchart TD" in page.html
    assert "<svg" not in page.html
    assert "language-mermaid" not in page.html


@pytest.mark.parametrize(
    ("manifest_body", "message"),
    [
        ("schema_version: 3\nsections: []\n", "schema_version: 1 or 2"),
        (
            """schema_version: 1
sections:
  - id: guides
    title: Guides
    index_route: guides/index.html
    pages:
      - source: docs/missing.md
        route: guides/missing.html
""",
            "existing Markdown file",
        ),
        (
            """schema_version: 1
sections:
  - id: guides
    title: Guides
    index_route: guides/index.html
    pages:
      - source: ../outside.md
        route: guides/outside.html
""",
            "must stay inside",
        ),
    ],
)
def test_manifest_rejects_invalid_schema_missing_source_and_source_escape(
    tmp_path, manifest_body, message
):
    _write(tmp_path / "outside.md", "# Outside\n")
    with pytest.raises(ValueError, match=message):
        load_guide_manifest(_manifest(tmp_path, manifest_body))


@pytest.mark.parametrize("duplicate_field", ["source", "route"])
def test_manifest_rejects_duplicate_sources_and_routes(tmp_path, duplicate_field):
    _write(tmp_path / "docs" / "one.md", "# One\n")
    _write(tmp_path / "docs" / "two.md", "# Two\n")
    second_source = "docs/one.md" if duplicate_field == "source" else "docs/two.md"
    second_route = "guides/one.html" if duplicate_field == "route" else "guides/two.html"
    manifest_path = _manifest(
        tmp_path,
        f"""schema_version: 1
sections:
  - id: guides
    title: Guides
    index_route: guides/index.html
    pages:
      - source: docs/one.md
        route: guides/one.html
      - source: {second_source}
        route: {second_route}
""",
    )

    with pytest.raises(ValueError, match=f"Duplicate guide {duplicate_field}"):
        load_guide_manifest(manifest_path)


def test_schema_v2_scans_source_dirs_with_frontmatter_and_exclude(tmp_path):
    _write(
        tmp_path / "docs" / "features" / "a.md",
        """---
title: 功能 A
summary: 前文摘要覆盖第一段。
---
# 备用 H1

第一段会被 frontmatter summary 覆盖。

## 小节

正文。
""",
    )
    _write(
        tmp_path / "docs" / "features" / "b.md",
        "# 功能 B\n\n功能 B 正文。\n",
    )
    _write(
        tmp_path / "docs" / "features" / "hidden.md",
        """---
hidden: true
---
# 隐藏页

不应出现在导航。
""",
    )
    _write(
        tmp_path / "docs" / "features" / "internal" / "draft.md",
        "# 草稿\n\n不应被扫描。\n",
    )
    manifest_path = _manifest(
        tmp_path,
        """schema_version: 2
sections:
  - id: features
    title: 功能特性
    index_route: features/index.html
    source_indexes:
      - docs/features/a.md
    source_dirs:
      - docs/features
    exclude:
      - "**/internal/**"
""",
    )

    rendered = render_guide_manifest(load_guide_manifest(manifest_path))
    pages = {page.route: page for section in rendered.sections for page in section.pages}

    assert set(pages) == {"features/a.html", "features/b.html"}
    assert "features/hidden.html" not in pages
    assert "features/internal/draft.html" not in pages
    assert pages["features/a.html"].title == "功能 A"
    assert pages["features/a.html"].summary == "前文摘要覆盖第一段。"
    assert "title: 功能 A" not in pages["features/a.html"].html
    assert "summary: 前文摘要覆盖第一段。" not in pages["features/a.html"].html
    assert "备用 H1" in pages["features/a.html"].html
    assert pages["features/b.html"].title == "功能 B"


def test_schema_v2_maps_skipped_directory_readmes_to_section_index(tmp_path):
    _write(tmp_path / "docs" / "features" / "advanced" / "README.md", "# 高级功能\n")
    _write(
        tmp_path / "docs" / "features" / "advanced" / "executor.md",
        "# 执行器\n\n参见同目录的 [高级功能](README.md)。\n",
    )
    manifest_path = _manifest(
        tmp_path,
        """schema_version: 2
sections:
  - id: features
    title: 功能特性
    index_route: features/index.html
    source_dirs:
      - docs/features
    exclude:
      - "**/README.md"
""",
    )

    rendered = render_guide_manifest(load_guide_manifest(manifest_path))
    page = rendered.sections[0].pages[0]

    assert 'href="../index.html">高级功能</a>' in page.html
    assert rendered.warnings == ()


def test_schema_v2_frontmatter_excludes_page_and_scanned_route_uses_md_path(tmp_path):
    _write(
        tmp_path / "docs" / "guides" / "excluded.md",
        """---
exclude_from_nav: true
---
# 不入导航

正文。
""",
    )
    _write(
        tmp_path / "docs" / "guides" / "kept.md",
        "# 保留页\n\n正文。\n",
    )
    manifest_path = _manifest(
        tmp_path,
        """schema_version: 2
sections:
  - id: guides
    title: 指南
    index_route: guides/index.html
    source_dirs:
      - docs/guides
""",
    )

    rendered = render_guide_manifest(load_guide_manifest(manifest_path))
    routes = [page.route for section in rendered.sections for page in section.pages]

    assert routes == ["guides/kept.html"]


def test_schema_v2_tag_registers_provider_page_without_rendering(tmp_path):
    _write(
        tmp_path / "docs" / "contexts" / "context.md",
        """---
tag: reflect
---
# Context

由 site_doc_generator 反射生成,无 H1 渲染需求。
""",
    )
    _write(
        tmp_path / "docs" / "contexts" / "manual.md",
        "# 手写页\n\n正文。\n",
    )
    manifest_path = _manifest(
        tmp_path,
        """schema_version: 2
sections:
  - id: api
    title: API 参考
    index_route: api/index.html
    source_dirs:
      - docs/contexts
""",
    )

    rendered = render_guide_manifest(load_guide_manifest(manifest_path))
    markdown_routes = [
        page.route
        for section in rendered.sections
        for page in section.pages
        if page.html is not None
    ]
    provider_routes = [page.route for page in rendered.provider_pages]

    assert markdown_routes == ["contexts/manual.html"]
    assert provider_routes == ["contexts/context.html"]
    assert [page.route for page in rendered.sections[0].pages] == [
        "contexts/context.html",
        "contexts/manual.html",
    ]
    assert rendered.sections[0].pages[0].tag == "reflect"
    assert rendered.sections[0].pages[0].html is None


def test_schema_v2_explicit_page_tag_and_title_override(tmp_path):
    _write(tmp_path / "docs" / "contexts" / "context.md", "# Context\n")
    manifest_path = _manifest(
        tmp_path,
        """schema_version: 2
sections:
  - id: api
    title: API 参考
    index_route: api/index.html
    pages:
      - route: contexts/context.html
        title: Context 参考
        tag: reflect
""",
    )

    rendered = render_guide_manifest(load_guide_manifest(manifest_path))
    page = rendered.sections[0].pages[0]
    assert page.route == "contexts/context.html"
    assert page.tag == "reflect"
    assert page.title == "Context 参考"
    assert page.html is None
    assert [p.route for p in rendered.provider_pages] == ["contexts/context.html"]


def test_schema_v2_pages_link_prev_next_and_source_relative(tmp_path):
    _write(tmp_path / "docs" / "guides" / "a.md", "# A\n\nA 正文。\n")
    _write(tmp_path / "docs" / "guides" / "b.md", "# B\n\nB 正文。\n")
    _write(tmp_path / "docs" / "guides" / "c.md", "# C\n\nC 正文。\n")
    manifest_path = _manifest(
        tmp_path,
        """schema_version: 2
sections:
  - id: guides
    title: 指南
    index_route: guides/index.html
    source_dirs: [docs/guides]
""",
    )

    rendered = render_guide_manifest(load_guide_manifest(manifest_path))
    pages = {page.route: page for section in rendered.sections for page in section.pages}

    assert pages["guides/a.html"].next_route == "guides/b.html"
    assert pages["guides/a.html"].next_title == "B"
    assert pages["guides/a.html"].prev_route is None
    assert pages["guides/b.html"].prev_route == "guides/a.html"
    assert pages["guides/b.html"].next_route == "guides/c.html"
    assert pages["guides/c.html"].next_route is None
    assert pages["guides/a.html"].source_relative == "docs/guides/a.md"


def test_schema_v2_nav_weight_orders_sections(tmp_path):
    _write(tmp_path / "docs" / "b" / "b.md", "# B\n")
    _write(tmp_path / "docs" / "a" / "a.md", "# A\n")
    manifest_path = _manifest(
        tmp_path,
        """schema_version: 2
sections:
  - id: first
    title: 第二栏
    index_route: b/index.html
    nav_weight: 30
    source_dirs: [docs/b]
  - id: second
    title: 第一栏
    index_route: a/index.html
    nav_weight: 10
    source_dirs: [docs/a]
""",
    )

    manifest = load_guide_manifest(manifest_path)

    assert [section.section_id for section in manifest.sections] == ["second", "first"]


def test_renderer_blocks_repository_escape(tmp_path):
    _write(tmp_path / "docs" / "guide.md", "# Guide\n\n[escape](../../outside.md)\n")
    _write(tmp_path.parent / "outside.md", "# Outside\n")
    manifest_path = _manifest(
        tmp_path,
        """schema_version: 1
sections:
  - id: guides
    title: Guides
    index_route: guides/index.html
    pages:
      - source: docs/guide.md
        route: guides/guide.html
""",
    )

    with pytest.raises(ValueError, match="escapes the repository"):
        render_guide_manifest(load_guide_manifest(manifest_path))


def test_site_generation_rejects_guide_route_collision(tmp_path):
    project = tmp_path / "project"
    _write(project / "docs" / "guide.md", "# Guide\n")
    manifest_path = _manifest(
        project,
        """schema_version: 1
sections:
  - id: guides
    title: Guides
    index_route: guides/index.html
    pages:
      - source: docs/guide.md
        route: index.html
""",
    )

    with pytest.raises(ValueError, match="collides with generated site page"):
        DocumentationSiteGenerator(guide_manifest_path=manifest_path).generate(tmp_path / "site")
