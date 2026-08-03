from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator


def test_site_web_includes_consolidated_markdown_plugin_guide(tmp_path):
    result = DocumentationSiteGenerator().generate(tmp_path)

    overview = result["PLUGIN_OVERVIEW"].read_text(encoding="utf-8")
    authoring = result["PLUGIN_AUTHORING"].read_text(encoding="utf-8")
    plugin_index = result["INDEX"].read_text(encoding="utf-8")
    search_index = (tmp_path / "assets" / "search-index.js").read_text(encoding="utf-8")

    assert result["PLUGIN_OVERVIEW"] == tmp_path / "plugins" / "overview.html"
    assert result["PLUGIN_AUTHORING"] == tmp_path / "plugins" / "authoring.html"
    assert "系统边界与数据流" in overview
    assert "Plugin 内部数据获取与生命周期" in overview
    assert "Chunk Plugin：流式与批量计算" in overview
    assert '<pre class="code-block language-python"><code><span class=' in overview
    assert 'href="overview.html"' in authoring
    assert 'window.location.replace("overview.html")' in authoring
    assert 'href="overview.html"' in plugin_index
    assert '"url":"plugins/overview.html"' in search_index
    assert '"plugins/system.html"' not in search_index
    assert '"plugins/template-api.html"' not in search_index
