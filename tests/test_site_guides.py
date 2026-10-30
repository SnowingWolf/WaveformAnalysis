import ast
import importlib
import inspect
from pathlib import Path
import re

import pytest

from waveform_analysis.documentation.site_guides import load_guide_manifest, parse_frontmatter


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _manifest(project: Path, body: str) -> Path:
    path = project / "docs" / "site-guides.yaml"
    _write(path, body)
    return path


def test_repository_manifest_contains_canonical_fact_routes():
    path = Path(__file__).parents[1] / "docs" / "site-guides.yaml"
    manifest = load_guide_manifest(path)

    assert manifest.sections
    assert all(section.index_route.startswith("/") for section in manifest.sections)
    assert all(section.index_route.endswith("/") for section in manifest.sections)
    assert all(".html" not in section.index_route for section in manifest.sections)
    assert all(".html" not in page.route for section in manifest.sections for page in section.pages)
    assert any(
        page.route == "/plugins/overview/"
        for section in manifest.sections
        for page in section.pages
    )
    assert any(
        page.route == "/accessors/records-view/"
        for section in manifest.sections
        for page in section.pages
    )
    assert not any(
        page.route == "/contexts/records-view/"
        for section in manifest.sections
        for page in section.pages
    )


def test_manifest_loads_markdown_and_reflected_facts(tmp_path):
    _write(tmp_path / "docs" / "guide.md", "# Guide\n")
    path = _manifest(
        tmp_path,
        """schema_version: 2
sections:
  - id: guides
    title: Guides
    index_route: /guides/
    pages:
      - source: docs/guide.md
        route: /guides/start/
      - route: /contexts/context/
        title: Context
        tag: reflect
""",
    )
    manifest = load_guide_manifest(path)
    pages = manifest.sections[0].pages

    markdown_page = next(page for page in pages if page.tag == "markdown")
    reflected_page = next(page for page in pages if page.tag == "reflect")
    assert markdown_page.source == tmp_path / "docs" / "guide.md"
    assert reflected_page.source is None
    assert manifest.provider_pages == (reflected_page,)


@pytest.mark.parametrize(
    "route",
    ["guides/start/", "/guides/start.html", "/../escape/", "/guides/?x=1", "/guides/#top"],
)
def test_manifest_rejects_noncanonical_routes(tmp_path, route):
    _write(tmp_path / "docs" / "guide.md", "# Guide\n")
    path = _manifest(
        tmp_path,
        f"""schema_version: 2
sections:
  - id: guides
    title: Guides
    index_route: /guides/
    pages:
      - source: docs/guide.md
        route: {route}
""",
    )
    with pytest.raises(ValueError, match="canonical route|leading and trailing|unsupported"):
        load_guide_manifest(path)


def test_manifest_rejects_duplicate_sources(tmp_path):
    _write(tmp_path / "docs" / "one.md", "# One\n")
    path = _manifest(
        tmp_path,
        """schema_version: 2
sections:
  - id: guides
    title: Guides
    index_route: /guides/
    pages:
      - source: docs/one.md
        route: /guides/one/
      - source: docs/one.md
        route: /guides/two/
""",
    )
    with pytest.raises(ValueError, match="Duplicate guide source"):
        load_guide_manifest(path)


def test_manifest_rejects_duplicate_canonical_routes(tmp_path):
    _write(tmp_path / "docs" / "one.md", "# One\n")
    _write(tmp_path / "docs" / "two.md", "# Two\n")
    path = _manifest(
        tmp_path,
        """schema_version: 2
sections:
  - id: guides
    title: Guides
    index_route: /guides/
    pages:
      - source: docs/one.md
        route: /guides/one/
      - source: docs/two.md
        route: /guides/one/
""",
    )
    with pytest.raises(ValueError, match="Duplicate guide route"):
        load_guide_manifest(path)


def test_schema_v2_scans_source_dirs_and_frontmatter(tmp_path):
    _write(
        tmp_path / "docs" / "features" / "a.md",
        "---\ntitle: Feature A\nsummary: Summary\nnav_weight: 5\n---\n# A\n",
    )
    _write(tmp_path / "docs" / "features" / "README.md", "# Features\n")
    path = _manifest(
        tmp_path,
        """schema_version: 2
sections:
  - id: features
    title: Features
    index_route: /features/
    source_dirs: [docs/features]
""",
    )
    manifest = load_guide_manifest(path)
    page = manifest.sections[0].pages[0]

    assert page.route == "/features/a/"
    assert page.title_override == "Feature A"
    assert page.summary_override == "Summary"
    assert manifest.sections[0].source_indexes[0].name == "README.md"


def test_frontmatter_must_be_a_mapping():
    with pytest.raises(ValueError, match="frontmatter must be a mapping"):
        parse_frontmatter("---\n- invalid\n---\nbody\n")


def test_context_migration_guide_examples_match_public_signatures():
    from waveform_analysis import Context

    root = Path(__file__).parents[1]
    manifest = load_guide_manifest(root / "docs/site-guides.yaml")
    guides = {
        page.route: page.source
        for section in manifest.sections
        for page in section.pages
        if page.source is not None
    }
    guide = guides["/features/context/CONFIGURATION/"]
    source = guide.read_text(encoding="utf-8")
    migration = source.split("## Context API 迁移", 1)[1].split("## 相关文档", 1)[0]
    calls = []
    for example in re.findall(r"```python\n(.*?)```", migration, re.DOTALL):
        for node in ast.walk(ast.parse(example)):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "ctx":
                continue
            name = node.func.attr
            signature = inspect.signature(getattr(Context, name))
            signature.bind(None, *node.args, **{kw.arg: kw.value for kw in node.keywords})
            calls.append(name)

    assert set(calls) == {"set_config", "get_lineage", "analyze_dependencies", "preview_execution"}
    assert "ctx.profiler.summary()" in migration
    assert "不会发出弃用警告" in source


@pytest.mark.parametrize("filename", ["ADAPTER_SYSTEM_GUIDE.md", "ADAPTER_PLUGIN_BEHAVIOR.md"])
def test_adapter_guide_loading_examples_match_hardware_key_signatures(filename):
    from waveform_analysis.acquisition.formats import DAQAdapter

    root = Path(__file__).parents[1]
    source = (root / "docs/plugins/reference" / filename).read_text(encoding="utf-8")
    calls = []
    for example in re.findall(r"```python\n(.*?)```", source, re.DOTALL):
        for node in ast.walk(ast.parse(example)):
            if isinstance(node, ast.ImportFrom):
                module = importlib.import_module(node.module)
                for imported in node.names:
                    assert hasattr(module, imported.name), (node.module, imported.name)
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "adapter":
                continue
            name = node.func.attr
            if not name.startswith("load_"):
                continue
            signature = inspect.signature(getattr(DAQAdapter, name))
            signature.bind(None, *node.args, **{kw.arg: kw.value for kw in node.keywords})
            if name != "load_all_channels":
                assert "board" in {kw.arg for kw in node.keywords}
            calls.append(name)
    assert set(calls) == {"load_channel", "load_channel_generator", "load_all_channels"}
