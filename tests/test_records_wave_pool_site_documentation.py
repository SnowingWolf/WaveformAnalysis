from waveform_analysis.utils.site_doc_generator import DocumentationSiteGenerator


def test_site_web_includes_records_wave_pool_design_reference(tmp_path):
    result = DocumentationSiteGenerator().generate(tmp_path)

    context_index = result["CONTEXT_INDEX"].read_text(encoding="utf-8")
    home = result["SITE_INDEX"].read_text(encoding="utf-8")
    page = result["context:records-wave-pool"].read_text(encoding="utf-8")
    search_index = (tmp_path / "assets" / "search-index.js").read_text(encoding="utf-8")

    assert result["context:records-wave-pool"] == tmp_path / "contexts" / "records-wave-pool.html"
    assert 'href="records-wave-pool.html"' in context_index
    assert 'href="contexts/records-wave-pool.html"' in home
    assert "RecordsBundle" in page
    assert "wave_offset" in page
    assert "event_length" in page
    assert "st_waveforms" in page
    assert "V1725" in page
    assert "records_view" in page
    assert "wave_pool_filtered" in page
    assert 'href="records-wave-pool.html" aria-current="page">Records + WavePool</a>' in page
    assert "contexts/records-wave-pool.html#input-routing" in search_index
