from types import SimpleNamespace

from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator


def test_accessor_index_highlights_plugin_and_accessor_responsibilities():
    env = PluginDocGenerator()._get_web_jinja_env()
    html = env.get_template("web/accessor_index.html.j2").render(
        accessors=(
            SimpleNamespace(
                slug="example-accessor",
                name="ExampleAccessor",
                summary="Example summary.",
            ),
        )
    )

    assert 'class="accessor-responsibility"' in html
    assert "Plugin 产出单一数据，Accessor 连接多个产物" in html
    assert "每个插件聚焦一个稳定、具名的数据产物" in html
    assert "跨插件筛选、关联和回溯" in html
    assert "Accessor 不属于插件 DAG" in html
    assert "不生成新的缓存数据契约" in html
    assert 'href="../contexts/records-view.html"' in html
    assert 'aria-controls="tree-accessors"' in html
    assert "折叠 Accessor 接口" in html
    assert "records-backed 波形访问" in html
    assert "RecordsView" in html
    assert "按稳定 <code>record_id</code> 访问 <code>records</code> 与 <code>wave_pool</code>" in html
