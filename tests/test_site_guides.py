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
        ("schema_version: 2\nsections: []\n", "schema_version: 1"),
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
