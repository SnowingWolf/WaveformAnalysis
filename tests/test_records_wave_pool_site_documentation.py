import json

from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator


def test_site_web_includes_records_wave_pool_design_reference(tmp_path):
    result = DocumentationSiteGenerator().generate(tmp_path)

    context_index = result["CONTEXT_INDEX"].read_text(encoding="utf-8")
    home = result["SITE_INDEX"].read_text(encoding="utf-8")
    records_view = result["context:records-view"].read_text(encoding="utf-8")
    legacy_page = result["context:records-wave-pool"].read_text(encoding="utf-8")
    guide_page = result["guide:docs/architecture/RECORDS_WAVE_POOL.md"].read_text(encoding="utf-8")
    search_index = (tmp_path / "assets" / "search-index.js").read_text(encoding="utf-8")
    search_entries = json.loads(
        search_index.removeprefix("window.WAVEFORM_DOCS_SEARCH=").rstrip(";\n")
    )

    assert result["context:records-wave-pool"] == tmp_path / "contexts" / "records-wave-pool.html"
    assert result["guide:docs/architecture/RECORDS_WAVE_POOL.md"] == (
        tmp_path / "architecture" / "records-wave-pool.html"
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
        '<a class="inline-reference-link" href="../architecture/records-wave-pool.html">'
        not in records_view
    )
    assert "RecordsBundle" in guide_page
    assert "contexts/records-view.html#input-routing" in {entry["url"] for entry in search_entries}


def test_site_web_publishes_the_architecture_learning_path_without_data_access_route(tmp_path):
    result = DocumentationSiteGenerator().generate(tmp_path)
    expected_pages = {
        "ARCHITECTURE.md": ("system.html", "系统总览：组件、边界与数据流"),
        "PLUGIN_DAG_LINEAGE_CACHE.md": (
            "plugin-dag-lineage-cache.html",
            "插件执行链：DAG、动态依赖、Lineage 与缓存",
        ),
        "DATA_PRODUCTS.md": ("data-products.html", "数据产物：实体关系与派生结果"),
        "RECORDS_WAVE_POOL.md": (
            "records-wave-pool.html",
            "波形数据：records 与 Wave Pool 的配对访问",
        ),
        "ACCESSOR_ANALYSIS.md": ("accessor-analysis.html", "分析查询：Accessor 与只读数据访问"),
        "MULTI_RUN_PROCESSING.md": (
            "multi-run-processing.html",
            "批量运行：多 Run 调度与执行（开发中）",
        ),
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
        "DATA_PRODUCTS.md": ("成员关系表", "peaklet_components", 8),
        "RECORDS_WAVE_POOL.md": ("当前配对实例", "peaklet_waveform_pool", 7),
        "ACCESSOR_ANALYSIS.md": ("数据获取模型", "Context.get_data", 6),
        "MULTI_RUN_PROCESSING.md": ("状态：开发中", "名称未形成强制只读契约", 6),
    }
    for source_name, (section, evidence, minimum_diagrams) in expected_contract_evidence.items():
        page = result[f"guide:docs/architecture/{source_name}"].read_text(encoding="utf-8")
        assert section in page
        assert evidence in page
        assert page.count('class="mermaid-block"') >= minimum_diagrams

    assert not (tmp_path / "architecture" / "data-access.html").exists()
    assert "architecture/data-access.html" not in search_urls
