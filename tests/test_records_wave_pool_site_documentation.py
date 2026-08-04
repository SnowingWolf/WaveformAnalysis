import json

from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator


def test_site_web_includes_records_wave_pool_design_reference(tmp_path):
    result = DocumentationSiteGenerator().generate(tmp_path)

    context_index = result["CONTEXT_INDEX"].read_text(encoding="utf-8")
    home = result["SITE_INDEX"].read_text(encoding="utf-8")
    records_view = result["context:records-view"].read_text(encoding="utf-8")
    legacy_page = result["context:records-wave-pool"].read_text(encoding="utf-8")
    guide_page = result["guide:docs/architecture/DATA_PRODUCTS.md"].read_text(encoding="utf-8")
    search_index = (tmp_path / "assets" / "search-index.js").read_text(encoding="utf-8")
    search_entries = json.loads(
        search_index.removeprefix("window.WAVEFORM_DOCS_SEARCH=").rstrip(";\n")
    )

    assert result["context:records-wave-pool"] == tmp_path / "contexts" / "records-wave-pool.html"
    assert result["guide:docs/architecture/DATA_PRODUCTS.md"] == (
        tmp_path / "architecture" / "data-products.html"
    )
    assert 'href="records-wave-pool.html"' not in context_index
    assert '<a class="resource-card" href="architecture/records-wave-pool.html">' not in home
    assert "RecordsBundle" in records_view
    assert "wave_offset" in records_view
    assert "event_length" in records_view
    assert "st_waveforms" in records_view
    assert "V1725" in records_view
    assert "records_view" in records_view
    assert "wave_pool_filtered" in records_view
    assert 'href="records-view.html#data-model"' in legacy_page
    assert 'window.location.replace("records-view.html#data-model")' in legacy_page
    assert (
        '<a class="inline-reference-link" href="../architecture/data-products.html">'
        in records_view
    )
    assert "data-mermaid-block" in records_view
    assert records_view.count('class="mermaid-block"') >= 2
    assert "assets/mermaid/mermaid.min.js" in records_view
    assert "RecordsBundle" in guide_page
    assert "wave_pool_filtered" in guide_page
    assert "contexts/records-view.html#input-routing" in {entry["url"] for entry in search_entries}


def test_site_web_publishes_the_architecture_learning_path_without_data_access_route(tmp_path):
    result = DocumentationSiteGenerator().generate(tmp_path)
    expected_pages = {
        "ARCHITECTURE.md": ("system.html", "系统架构与数据流"),
        "PLUGIN_DAG_LINEAGE_CACHE.md": (
            "plugin-dag-lineage-cache.html",
            "插件执行链与缓存",
        ),
        "DATA_PRODUCTS.md": ("data-products.html", "数据产物与波形访问"),
        "ACCESSOR_ANALYSIS.md": ("accessor-analysis.html", "分析查询与批量运行"),
    }
    search_index = (tmp_path / "assets" / "search-index.js").read_text(encoding="utf-8")
    search_entries = json.loads(
        search_index.removeprefix("window.WAVEFORM_DOCS_SEARCH=").rstrip(";\n")
    )
    search_urls = {entry["url"] for entry in search_entries}

    for source_name, (route_name, heading) in expected_pages.items():
        source = f"docs/architecture/{source_name}"
        page = result[f"guide:{source}"].read_text(encoding="utf-8")
        assert result[f"guide:{source}"] == tmp_path / "architecture" / route_name
        assert heading in page
        assert f"architecture/{route_name}" in search_urls

    expected_contract_evidence = {
        "ARCHITECTURE.md": ("Context 配置模型", "plugin_name", 4),
        "PLUGIN_DAG_LINEAGE_CACHE.md": ("动态依赖", "Lineage 与缓存身份", 8),
        "DATA_PRODUCTS.md": ("成员关系表", "peaklet_waveform_pool", 15),
        "ACCESSOR_ANALYSIS.md": ("数据获取模型", "名称未形成强制只读契约", 12),
    }
    for source_name, (section, evidence, minimum_diagrams) in expected_contract_evidence.items():
        page = result[f"guide:docs/architecture/{source_name}"].read_text(encoding="utf-8")
        assert section in page
        assert evidence in page
        assert page.count('class="mermaid-block"') >= minimum_diagrams

    assert not (tmp_path / "architecture" / "data-access.html").exists()
    assert "architecture/data-access.html" not in search_urls
