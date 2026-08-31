import json
from pathlib import Path

import pytest
import yaml

from waveform_analysis.documentation.site_model import (
    SITE_MODEL_SCHEMA_PATH,
    SITE_MODEL_VERSION,
    SiteModelError,
    build_lineage_facts,
    build_site_model,
    canonical_route,
    validate_site_model,
)


def test_site_model_v1_uses_real_plugin_and_guide_facts_without_html():
    model = build_site_model(Path(__file__).parents[1])

    validate_site_model(model)
    assert model["schema"] == SITE_MODEL_VERSION == "site-model/v1"
    assert model["provenance"] == "generated"
    assert model["plugins"]
    assert model["guides"]
    assert model["lineage"]["nodes"]
    assert model["lineage"]["edges"]
    assert {node["id"] for node in model["lineage"]["nodes"]} == {
        plugin["provides"] for plugin in model["plugins"]
    }
    nodes_by_id = {node["id"]: node for node in model["lineage"]["nodes"]}
    assert nodes_by_id["raw_files"]["kind"] == "raw"
    assert nodes_by_id["records"]["kind"] == "record"
    assert nodes_by_id["hit_threshold"]["kind"] == "signal"
    assert nodes_by_id["peaks"]["kind"] == "peak"
    assert nodes_by_id["events"]["kind"] == "event"
    assert {node["kind"] for node in model["lineage"]["nodes"]} == {
        "raw",
        "record",
        "signal",
        "peak",
        "event",
        "virtual",
    }
    assert all(route["path"].endswith("/") for route in model["routes"])
    assert all(".html" not in route["path"] for route in model["routes"])
    assert all("[^" not in guide["summary"] for guide in model["guides"])
    assert all(guide["summary"] != "---" for guide in model["guides"])

    records = next(plugin for plugin in model["plugins"] if plugin["provides"] == "records")
    assert records["version"] == "0.14.2"
    assert records["dependsOn"][0] == "raw_files"
    assert records["fields"]
    assert json.dumps(model, ensure_ascii=False).find("<html") < 0
    assert SITE_MODEL_SCHEMA_PATH.is_file()


def test_site_model_builder_has_no_markdown_html_renderer():
    import waveform_analysis.documentation.site_guides as site_guides

    assert not hasattr(site_guides, "render_guide_manifest")
    model = build_site_model(Path(__file__).parents[1])
    assert model["guides"]


def test_canonical_route_rejects_legacy_html_spelling():
    with pytest.raises(SiteModelError, match="must be extensionless"):
        canonical_route("/plugins/records.html")


def test_route_migration_map_covers_all_routes_without_emitting_aliases():
    project_root = Path(__file__).parents[1]
    model = build_site_model(project_root)
    routes = {route["path"] for route in model["routes"]}
    manifest = yaml.safe_load(
        (project_root / "docs" / "site-route-migration.yaml").read_text(encoding="utf-8")
    )
    mappings = manifest["mappings"]
    old_routes = [entry["from"] for entry in mappings]
    targets = [entry["to"].split("#", 1)[0] for entry in mappings]

    assert manifest["canonical_style"] == "extensionless-trailing-slash"
    assert len(old_routes) == len(set(old_routes))
    assert all(route.startswith("/") and route.endswith(".html") for route in old_routes)
    assert all(".html" not in target and target.endswith("/") for target in targets)
    assert set(targets) <= routes
    old_route_set = set(old_routes)
    for route in routes:
        candidates = (
            {"/index.html"} if route == "/" else {f"{route.rstrip('/')}.html", f"{route}index.html"}
        )
        assert candidates & old_route_set, f"missing historical spelling for {route}"
    assert not (set(old_routes) & routes)


def test_site_model_rejects_generated_route_collisions(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Collision\n\nA guide.\n", encoding="utf-8")
    manifest = docs / "site-guides.yaml"
    manifest.write_text(
        """schema_version: 2
sections:
  - id: collision
    title: Collision
    index_route: /custom/
    pages:
      - source: docs/guide.md
        route: /plugins/records/
""",
        encoding="utf-8",
    )

    with pytest.raises(SiteModelError, match="Duplicate site route.*plugins/records"):
        build_site_model(tmp_path, guide_manifest_path=manifest)


def test_dynamic_lineage_uses_context_metadata_only():
    class FakeContext:
        _plugins = {}

        def get_lineage(self, _provides):
            raise AssertionError("no plugin should be queried")

    with pytest.raises(SiteModelError, match="registered plugins"):
        build_lineage_facts(context=FakeContext())
