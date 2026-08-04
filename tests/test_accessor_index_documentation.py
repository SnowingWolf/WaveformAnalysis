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
    assert (
        "按稳定 <code>record_id</code> 访问 <code>records</code> 与 <code>wave_pool</code>" in html
    )


def test_accessor_index_includes_selection_guide_and_shared_conventions():
    env = PluginDocGenerator()._get_web_jinja_env()
    html = env.get_template("web/accessor_index.html.j2").render(
        accessors=(
            SimpleNamespace(
                slug="example-accessor",
                name="ExampleAccessor",
                summary="Example summary.",
            ),
        ),
        selection_guide=(
            SimpleNamespace(
                name="PeakChannelAccessor",
                slug="peak-channel-accessor",
                entry="peak_id",
                question="一个 peak 由哪些通道构成？",
                scenario="通道级排查。",
                route="",
            ),
            SimpleNamespace(
                name="RecordsView",
                slug="records-view",
                entry="record_id",
                question="如何按 record_id 读波形？",
                scenario="records-backed 波形访问。",
                route="../contexts/records-view.html",
            ),
        ),
    )

    assert 'class="accessor-selection"' in html
    assert 'id="accessor-selection-heading"' in html
    assert "先确定查询入口，再选 Accessor" in html
    assert 'href="peak-channel-accessor.html"' in html
    assert 'href="../contexts/records-view.html"' in html
    assert "一个 peak 由哪些通道构成？" in html
    assert "通道级排查。" in html
    assert 'class="accessor-common"' in html
    assert "所有 Accessor 遵循同一套约定" in html
    assert "只读查询" in html
    assert "显式绑定" in html
    assert "按需加载" in html
    assert "逻辑通道键" in html
    assert 'href="../architecture/accessor-analysis.html"' in html
