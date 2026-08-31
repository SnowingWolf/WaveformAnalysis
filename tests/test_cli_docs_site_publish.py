from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

import pytest

from scripts.build_docs_site_dist import _without_trailing_whitespace
from waveform_analysis.documentation import cli
from waveform_analysis.documentation.site_web import (
    NextSiteBuilder,
    SiteExportValidationError,
    SiteWebBuildError,
    copy_prebuilt_site,
    validate_static_export,
    write_prebuilt_manifest,
)


def _fixture_model() -> dict:
    return {
        "schema": "site-model/v1",
        "modelVersion": "1",
        "project": {"name": "fixture", "version": "0", "tagline": "Fixture"},
        "provenance": "fixture",
        "navigation": [],
        "routes": [
            {"path": "/", "title": "Home", "kind": "home"},
            {"path": "/plugins/records/", "title": "records", "kind": "plugin"},
        ],
        "plugins": [
            {
                "provides": "records",
                "pluginClass": "RecordsPlugin",
                "version": "0.14.2",
                "executionKind": "static",
                "outputKind": "structured_array",
                "category": "other",
                "summary": "Records fixture",
                "dependsOn": ["raw_files"],
                "config": [],
                "fields": [],
                "usage": "",
                "route": "/plugins/records/",
                "provenance": "fixture",
            }
        ],
        "contexts": [],
        "accessors": [],
        "visualizations": [],
        "guides": [],
        "lineage": {"nodes": [], "edges": [], "views": {"overview": [], "full": []}},
    }


class _FakeSiteGenerator:
    def __init__(self, *, fail=False, broken_link=False):
        self.fail = fail
        self.broken_link = broken_link

    def generate(self, output_dir: Path) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        index = output_dir / "index.html"
        link = '<a href="missing.html">broken</a>' if self.broken_link else ""
        index.write_text(f"<!doctype html><title>Home</title>{link}", encoding="utf-8")
        records_page = output_dir / "plugins" / "records" / "index.html"
        records_page.parent.mkdir(parents=True, exist_ok=True)
        records_page.write_text("<!doctype html><title>records</title>", encoding="utf-8")
        model_path = output_dir / "site-model.v1.json"
        model_path.write_text(json.dumps(_fixture_model()), encoding="utf-8")
        results = {"SITE_INDEX": index, "SITE_MODEL": model_path}
        if self.fail:
            raise RuntimeError("generation failed")
        return results


def test_atomic_site_publish_replaces_the_complete_output(tmp_path):
    output = tmp_path / "site"
    output.mkdir()
    (output / "stale.html").write_text("old", encoding="utf-8")

    results = cli._atomic_generate_site(output, _FakeSiteGenerator())

    assert not (output / "stale.html").exists()
    assert results["SITE_MODEL"] == output / "site-model.v1.json"
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
        cli._atomic_generate_site(output, generator)

    assert original.read_text(encoding="utf-8") == "previous site"
    assert not list(tmp_path.glob(".site.staging-*"))
    assert not list(tmp_path.glob(".site.backup-*"))


def test_static_export_rejects_legacy_routes_and_path_escape(tmp_path):
    output = tmp_path / "site"
    output.mkdir()
    (output / "index.html").write_text(
        '<a href="/plugins/records.html">legacy</a><img src="/../secret.png">',
        encoding="utf-8",
    )
    with pytest.raises(
        SiteExportValidationError,
        match=r"legacy \.html route|missing local target",
    ):
        validate_static_export(output)


def test_next_build_requires_explicitly_installed_dependencies(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "package.json").write_text(
        '{"scripts":{"check":"true","build":"true"}}', encoding="utf-8"
    )
    calls = []

    def runner(command, **kwargs):
        calls.append(command)

    builder = NextSiteBuilder(project_root=tmp_path, app_root=app, command_runner=runner)
    with pytest.raises(SiteWebBuildError, match="npm ci"):
        builder.generate(tmp_path / "output")
    assert calls == []


def test_next_build_rejects_stale_fallback_export(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    stale = app / "out"
    stale.mkdir()
    (stale / "index.html").write_text("stale", encoding="utf-8")
    builder = NextSiteBuilder(project_root=tmp_path, app_root=app)
    before = {stale: stale.stat().st_mtime_ns}

    with pytest.raises(SiteWebBuildError, match="static export"):
        builder._export_directory(tmp_path / "requested", 10**30, before)


def test_prebuilt_manifest_hash_mismatch_fails_closed(tmp_path):
    source = tmp_path / "prebuilt"
    source.mkdir()
    page = source / "index.html"
    page.write_text("<!doctype html><title>ok</title>", encoding="utf-8")
    (source / "site-manifest.json").write_text(
        json.dumps(
            {
                "schema": "site-web/v1",
                "files": [{"path": "index.html", "size": page.stat().st_size, "sha256": "0" * 64}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SiteExportValidationError, match="hash manifest mismatch"):
        copy_prebuilt_site(source, tmp_path / "output")


def test_prebuilt_manifest_round_trip_is_node_free(tmp_path):
    source = tmp_path / "prebuilt"
    source.mkdir()
    (source / "index.html").write_text("<!doctype html><title>ok</title>", encoding="utf-8")
    records_page = source / "plugins" / "records" / "index.html"
    records_page.parent.mkdir(parents=True)
    records_page.write_text("<!doctype html><title>records</title>", encoding="utf-8")
    (source / "site-model.v1.json").write_text(json.dumps(_fixture_model()), encoding="utf-8")

    manifest = write_prebuilt_manifest(source)
    output = tmp_path / "output"
    result = copy_prebuilt_site(source, output)

    assert manifest.name == "site-manifest.json"
    assert result["SITE_INDEX"] == output / "index.html"
    assert result["SITE_MODEL"] == output / "site-model.v1.json"


def test_documentation_server_disables_cache_and_reads_republished_files(tmp_path):
    page = tmp_path / "index.html"
    page.write_text("first build", encoding="utf-8")
    try:
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            partial(
                cli._DocumentationRequestHandler,
                directory=str(tmp_path),
                lineage_payload_provider=None,
            ),
        )
    except PermissionError as exc:
        pytest.skip(f"socket creation is unavailable in this environment: {exc}")
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


def test_site_web_cli_has_no_plugins_web_dispatch():
    parser_args = type("Args", (), {"doc_type": "plugins-web", "plugin": None, "output": None})()
    with pytest.raises(ValueError, match="unsupported document type"):
        cli.cmd_generate(parser_args)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b"", b""),
        (b"alpha  \n beta\t\r\ngamma \rdelta\t", b"alpha\n beta\r\ngamma\rdelta\n"),
        (b"alpha\r\nbeta\nbeta2\r", b"alpha\r\nbeta\nbeta2\r"),
        (b"alpha\r\nbeta", b"alpha\r\nbeta\n"),
        (b"alpha\r\nbeta\n\n\r", b"alpha\r\nbeta\n"),
        (b" \t", b"\n"),
    ],
)
def test_text_normalizer_preserves_line_endings_and_has_one_eof_newline(content, expected):
    assert _without_trailing_whitespace(content) == expected
