"""Regression coverage for the consolidated plugin-system guide."""

import json


def test_plugin_system_navigation_and_legacy_routes(tmp_path):
    from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator

    generated = DocumentationSiteGenerator().generate(tmp_path)

    overview = generated["PLUGIN_OVERVIEW"].read_text(encoding="utf-8")
    plugin_index = generated["INDEX"].read_text(encoding="utf-8")
    search_index = (tmp_path / "assets" / "search-index.js").read_text(encoding="utf-8")
    search_entries = json.loads(
        search_index.removeprefix("window.WAVEFORM_DOCS_SEARCH=").rstrip(";\n")
    )
    plugin_tree = plugin_index.split('<ul id="tree-plugins">', 1)[1].split("</ul>", 1)[0]

    assert generated["PLUGIN_OVERVIEW"] == tmp_path / "plugins" / "overview.html"
    assert ">内置插件列表<" in plugin_tree
    assert ">插件系统与模板 API<" in plugin_tree
    assert ">插件系统介绍<" not in plugin_tree
    assert ">插件模板的 API 介绍<" not in plugin_tree
    assert ">插件 DAG<" not in plugin_tree
    assert 'href="overview.html"' in plugin_tree
    assert 'href="lineage.html">独立查看</a>' in plugin_index

    assert "系统边界与数据流" in overview
    assert "本节只说明请求和结果如何穿过系统边界" in overview
    assert "Plugin runtime" in overview
    assert "四个互相配合的声明" in overview
    assert "按 Context 解析出的 DAG 调用插件" in overview
    assert "配置优先级" in overview
    assert "get_config_value" in overview
    assert "显式配置" in overview
    assert "静态依赖和" in overview
    assert "Chunk Plugin：流式与批量计算" in overview
    assert "compute_array()" in overview
    assert "从浏览到使用" not in overview
    assert "\\n" not in overview
    assert '<pre class="code-block language-python"><code><span class=' in overview
    assert '<div class="mermaid-block" data-mermaid-block>' in overview

    for route in ("system.html", "template-api.html", "authoring.html"):
        legacy = (tmp_path / "plugins" / route).read_text(encoding="utf-8")
        assert 'href="overview.html"' in legacy
        assert 'window.location.replace("overview.html")' in legacy

    canonical_entries = [
        entry for entry in search_entries if entry["url"] == "plugins/overview.html"
    ]
    assert any(entry["title"] == "插件系统与模板 API" for entry in canonical_entries)
    assert not any(
        entry["url"] in {"plugins/system.html", "plugins/template-api.html"}
        for entry in search_entries
    )
