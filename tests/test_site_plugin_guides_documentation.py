from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator


def test_site_web_includes_plugin_overview_and_authoring_guides(tmp_path):
    result = DocumentationSiteGenerator().generate(tmp_path)

    overview = result["PLUGIN_OVERVIEW"].read_text(encoding="utf-8")
    authoring = result["PLUGIN_AUTHORING"].read_text(encoding="utf-8")
    plugin_index = result["INDEX"].read_text(encoding="utf-8")
    search_index = (tmp_path / "assets" / "search-index.js").read_text(encoding="utf-8")

    assert result["PLUGIN_OVERVIEW"] == tmp_path / "plugins" / "overview.html"
    assert result["PLUGIN_AUTHORING"] == tmp_path / "plugins" / "authoring.html"
    assert "Plugin 将分析步骤组织成" in overview
    assert 'href="authoring.html"' in overview
    assert "class MyPlugin(Plugin):" in authoring
    assert "output_dtype" in authoring
    assert 'href="overview.html"' in plugin_index
    assert 'href="authoring.html"' in plugin_index
    assert '"url":"plugins/overview.html"' in search_index
    assert '"url":"plugins/authoring.html"' in search_index
