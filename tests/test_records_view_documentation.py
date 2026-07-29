from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator


def test_site_web_includes_records_view_reference(tmp_path):
    result = DocumentationSiteGenerator().generate(tmp_path)

    context_index = result["CONTEXT_INDEX"].read_text(encoding="utf-8")
    adapter_index = result["ADAPTER_INDEX"].read_text(encoding="utf-8")
    page = result["context:records-view"].read_text(encoding="utf-8")
    search_index = (tmp_path / "assets" / "search-index.js").read_text(encoding="utf-8")

    assert 'href="records-view.html"' in context_index
    assert 'href="../contexts/records-view.html"' in adapter_index
    assert "records_view" in page
    assert "RecordsView" in page
    assert "waves" in page
    assert "signals" in page
    assert "query_time_window" in page
    assert "wave_pool_filtered" in page
    assert "contexts/records-view.html#construction" in search_index
