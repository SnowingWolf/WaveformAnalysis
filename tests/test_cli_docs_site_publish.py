from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from urllib.request import urlopen

import pytest

from waveform_analysis.utils import cli_docs

REQUIRED_PATHS = {
    "SITE_INDEX": "index.html",
    "INDEX": "plugins/index.html",
    "ROOT_LINEAGE": "lineage.html",
    "LINEAGE_INDEX": "plugins/lineage.html",
    "ACCESSOR_INDEX": "accessors/index.html",
    "CONTEXT_INDEX": "contexts/index.html",
    "context:records-view": "contexts/records-view.html",
    "context:records-wave-pool": "contexts/records-wave-pool.html",
    "ADAPTER_INDEX": "adapters/index.html",
    "VISUALIZATION_INDEX": "visualizations/index.html",
}


class _FakeSiteGenerator:
    def __init__(self, *, fail=False, broken_link=False):
        self.fail = fail
        self.broken_link = broken_link

    def generate(self, output_dir: Path) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        results = {}
        for name, relative_path in REQUIRED_PATHS.items():
            path = output_dir / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            link = '<a href="missing.html">broken</a>' if self.broken_link else ""
            path.write_text(f"<!doctype html><title>{name}</title>{link}", encoding="utf-8")
            results[name] = path
        if self.fail:
            raise RuntimeError("generation failed")
        return results


def test_atomic_site_publish_replaces_the_complete_output(tmp_path):
    output = tmp_path / "site"
    output.mkdir()
    (output / "stale.html").write_text("old", encoding="utf-8")

    results = cli_docs._atomic_generate_site(output, _FakeSiteGenerator())

    assert not (output / "stale.html").exists()
    assert results["ACCESSOR_INDEX"] == output / "accessors" / "index.html"
    assert all(path.is_file() for path in results.values())
    assert not list(tmp_path.glob(".site.staging-*"))
    assert not list(tmp_path.glob(".site.backup-*"))


@pytest.mark.parametrize("failure", ["generate", "validate"])
def test_atomic_site_publish_preserves_the_previous_site_on_failure(tmp_path, failure):
    output = tmp_path / "site"
    output.mkdir()
    original = output / "index.html"
    original.write_text("previous site", encoding="utf-8")
    generator = _FakeSiteGenerator(
        fail=failure == "generate",
        broken_link=failure == "validate",
    )

    with pytest.raises((RuntimeError, ValueError)):
        cli_docs._atomic_generate_site(output, generator)

    assert original.read_text(encoding="utf-8") == "previous site"
    assert not list(tmp_path.glob(".site.staging-*"))
    assert not list(tmp_path.glob(".site.backup-*"))


def test_site_validation_checks_html_fragments_and_aria_controls(tmp_path):
    output = tmp_path / "site"
    output.mkdir()
    index = output / "index.html"
    index.write_text(
        '<nav id="site-navigation"></nav><a href="page.html#missing">bad</a>'
        '<button aria-controls="missing-node"></button>',
        encoding="utf-8",
    )
    page = output / "page.html"
    page.write_text('<h1 id="present">Page</h1>', encoding="utf-8")
    results = {name: output / relative for name, relative in REQUIRED_PATHS.items()}
    for path in results.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("<div id='site-navigation'></div>", encoding="utf-8")

    with pytest.raises(ValueError, match="fragment 不存在|DOM 节点不存在"):
        cli_docs._validate_generated_site(output, results)


def test_site_validation_checks_search_index_urls(tmp_path):
    output = tmp_path / "site"
    output.mkdir()
    results = {}
    for name, relative in REQUIRED_PATHS.items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<div id='site-navigation'></div>", encoding="utf-8")
        results[name] = path
    (output / "assets").mkdir()
    (output / "assets" / "search-index.js").write_text(
        'window.WAVEFORM_DOCS_SEARCH=[{"title":"bad","url":"missing.html#x"}];\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="search-index.js.*missing.html"):
        cli_docs._validate_generated_site(output, results)


def test_generate_site_web_uses_atomic_publication(tmp_path, monkeypatch):
    from waveform_analysis.utils import site_doc_generator

    monkeypatch.setattr(
        site_doc_generator,
        "DocumentationSiteGenerator",
        _FakeSiteGenerator,
    )
    output = tmp_path / "site"
    output.mkdir()
    (output / "stale.html").write_text("old", encoding="utf-8")

    result = cli_docs.generate_site_web(SimpleNamespace(plugin=None, output=str(output)))

    assert result == 0
    assert not (output / "stale.html").exists()
    assert (output / "accessors" / "index.html").is_file()


def test_documentation_server_disables_cache_and_reads_republished_files(tmp_path):
    page = tmp_path / "index.html"
    page.write_text("first build", encoding="utf-8")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(
            cli_docs._DocumentationRequestHandler,
            directory=str(tmp_path),
            lineage_payload_provider=None,
        ),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}/index.html"
    try:
        with urlopen(url) as response:
            assert response.read() == b"first build"
            assert response.headers["Cache-Control"] == "no-store, max-age=0"
            assert response.headers["Pragma"] == "no-cache"
            assert response.headers["Expires"] == "0"
        page.write_text("second build", encoding="utf-8")
        with urlopen(url) as response:
            assert response.read() == b"second build"
            assert response.headers["Cache-Control"] == "no-store, max-age=0"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_lineage_pages_use_depth_correct_navigation_links(tmp_path):
    from waveform_analysis.utils.plugin_doc_generator import PluginDocGenerator
    from waveform_analysis.utils.site_guides import RenderedGuidePage, RenderedGuideSection

    generator = PluginDocGenerator()
    nav_page = RenderedGuidePage(
        source=None,
        source_label="accessors/peak-channel-accessor.html",
        route="accessors/peak-channel-accessor.html",
        section_id="accessors-reference",
        title="PeakChannelAccessor",
        summary="",
        html=None,
        has_mermaid=False,
        headings=(),
        assets=(),
        tag="reflect",
    )
    generator._get_web_jinja_env().globals["guide_sections"] = (
        RenderedGuideSection(
            section_id="accessors-reference",
            title="Accessor 接口",
            index_route="accessors/guides.html",
            pages=(nav_page,),
        ),
    )
    common = {
        "lineage_json": "{}",
        "asset_prefix": "assets/",
        "site_home_href": "index.html",
        "plugin_index_href": "plugins/index.html",
        "plugin_href_prefix": "plugins/",
        "context_index_href": "contexts/context.html",
        "adapter_index_href": "adapters/adapter.html",
        "visualization_index_href": "visualizations/index.html",
        "visualization_detail_prefix": "visualizations/",
        "site_root_prefix": "",
    }
    root_html = generator.render_lineage_html(
        accessor_index_href="accessors/index.html",
        **common,
    )
    nested_html = generator.render_lineage_html(
        accessor_index_href="../accessors/index.html",
        plugin_index_href="index.html",
        site_home_href="../index.html",
        plugin_href_prefix="",
        asset_prefix="../assets/",
        context_index_href="../contexts/context.html",
        adapter_index_href="../adapters/adapter.html",
        visualization_index_href="../visualizations/index.html",
        visualization_detail_prefix="../visualizations/",
        site_root_prefix="../",
        lineage_json="{}",
    )

    assert 'href="accessors/peak-channel-accessor.html"' in root_html
    assert 'href="../accessors/peak-channel-accessor.html"' in nested_html
    assert 'href="None"' not in root_html
    assert 'href="None"' not in nested_html
