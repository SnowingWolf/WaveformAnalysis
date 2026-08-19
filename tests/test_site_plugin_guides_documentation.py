from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator


def test_site_web_includes_consolidated_markdown_plugin_guide(tmp_path):
    result = DocumentationSiteGenerator().generate(tmp_path)

    overview = result["PLUGIN_OVERVIEW"].read_text(encoding="utf-8")
    # The documentation migration consolidated the former standalone bundle
    # guide into PLUGIN_SYSTEM_OVERVIEW.md.  Keep the public route canonical
    # at plugins/overview.html and retain lightweight legacy aliases.
    bundle_guide = result["guide:docs/plugins/PLUGIN_SYSTEM_OVERVIEW.md"].read_text(
        encoding="utf-8"
    )
    authoring = result["PLUGIN_AUTHORING"].read_text(encoding="utf-8")
    plugin_index = result["INDEX"].read_text(encoding="utf-8")
    search_index = (tmp_path / "assets" / "search-index.js").read_text(encoding="utf-8")

    assert result["PLUGIN_OVERVIEW"] == tmp_path / "plugins" / "overview.html"
    assert result["guide:docs/plugins/PLUGIN_SYSTEM_OVERVIEW.md"] == (
        tmp_path / "plugins" / "overview.html"
    )
    assert result["PLUGIN_AUTHORING"] == tmp_path / "plugins" / "authoring.html"
    assert "系统边界与数据流" in overview
    assert "Plugin 内部数据获取与生命周期" in overview
    assert "Chunk Plugin：流式与批量计算" in overview
    assert '<pre class="code-block language-python"><code><span class=' in overview
    assert "一个 <code>provides</code> 对应一个 bundle" in bundle_guide
    assert "Canonical Bundle 与兼容转发" in bundle_guide
    assert 'href="overview.html"' in authoring
    assert 'window.location.replace("overview.html")' in authoring
    assert 'href="overview.html"' in plugin_index
    assert "插件系统与模板 API" in plugin_index
    assert '"url":"plugins/overview.html"' in search_index
    assert '"url":"plugins/bundles.html"' not in search_index
    assert '"plugins/system.html"' not in search_index
    assert '"plugins/template-api.html"' not in search_index
