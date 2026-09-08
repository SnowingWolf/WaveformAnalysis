from collections import Counter
import hashlib
import inspect
import json
from pathlib import Path

import pytest
import yaml

from waveform_analysis.documentation.site_docs.catalog import (
    ACCESSOR_DOCUMENTATION_REGISTRY,
    ADAPTER_DOCUMENTATION_PAGE,
    CONTEXT_DOCUMENTATION_PAGE,
    RECORDS_VIEW_DOCUMENTATION_PAGE,
    VISUALIZATION_DOCUMENTATION_PAGES,
)
from waveform_analysis.documentation.site_model import (
    SITE_MODEL_SCHEMA_PATH,
    SITE_MODEL_VERSION,
    SiteModelError,
    _package_version,
    build_lineage_facts,
    build_site_model,
    canonical_route,
    validate_site_model,
)


def test_site_model_package_version_prefers_tracked_pyproject(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "waveform-analysis"\nversion = "9.8.7"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("importlib.metadata.version", lambda _: "1.4.0")

    assert _package_version(tmp_path) == "9.8.7"


@pytest.mark.parametrize(
    "pyproject_text",
    [None, '[project]\nname = "waveform-analysis"\n', "not valid toml"],
)
def test_site_model_package_version_falls_back_to_distribution_metadata(
    tmp_path, monkeypatch, pyproject_text
):
    if pyproject_text is not None:
        (tmp_path / "pyproject.toml").write_text(pyproject_text, encoding="utf-8")
    monkeypatch.setattr("importlib.metadata.version", lambda _: "7.6.5")

    assert _package_version(tmp_path) == "7.6.5"


def _assert_callable_page_is_complete(page, spec):
    assert page["groups"]
    assert page["sections"]
    serialized = json.dumps(page["sections"], ensure_ascii=False)
    serialized_groups = {group["anchor"]: group for group in page["groups"]}
    for group in spec.groups:
        members_by_name = {
            member["name"]: member for member in serialized_groups[group.anchor]["members"]
        }
        for member in group.members:
            assert member.name in serialized
            serialized_member = members_by_name[member.name]
            assert serialized_member["signature"] == str(inspect.signature(member.callable))
            assert [parameter["name"] for parameter in serialized_member["parameters"]] == [
                parameter.name for parameter in member.parameters
            ]
            if member.returns:
                assert serialized_member["returns"] == member.returns
                assert member.returns in serialized


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
    assert len(model["source_indexes"]) == 11
    assert sum(bool(guide.get("source")) for guide in model["guides"]) == 34
    reference = next(section for section in model["navigation"] if section["id"] == "reference")
    cli_navigation = next(item for item in reference["items"] if item["href"] == "/cli/")
    assert [(item["label"], item["href"]) for item in cli_navigation["children"]] == [
        ("waveform-cache 命令参考", "/cli/WAVEFORM_CACHE/"),
        ("waveform-docs 命令参考", "/cli/WAVEFORM_DOCS/"),
        ("waveform-process 命令参考", "/cli/WAVEFORM_PROCESS/"),
    ]
    assert not next(item for item in reference["items"] if item["href"] == "/plugins/").get(
        "children"
    )


def test_site_model_rejects_navigation_children_with_unknown_routes():
    model = build_site_model(Path(__file__).parents[1])
    reference = next(section for section in model["navigation"] if section["id"] == "reference")
    cli_navigation = next(item for item in reference["items"] if item["href"] == "/cli/")
    cli_navigation["children"].append({"label": "Missing", "href": "/cli/MISSING/", "icon": "file"})

    with pytest.raises(SiteModelError, match="unknown route"):
        validate_site_model(model)


def test_site_model_builder_has_no_markdown_html_renderer():
    import waveform_analysis.documentation.site_guides as site_guides

    assert not hasattr(site_guides, "render_guide_manifest")
    model = build_site_model(Path(__file__).parents[1])
    assert model["guides"]


def test_site_model_preserves_rich_reference_content_and_accessor_classification():
    model = build_site_model(Path(__file__).parents[1])
    accessors = {page["slug"]: page for page in model["accessors"]}
    contexts = {page["slug"]: page for page in model["contexts"]}
    visualizations = {page["slug"]: page for page in model["visualizations"]}

    assert set(accessors) == {
        *(spec.slug for spec in ACCESSOR_DOCUMENTATION_REGISTRY),
        "records-view",
    }
    assert "records-view" not in contexts
    records_view_page = accessors["records-view"]
    assert records_view_page["route"] == "/accessors/records-view/"
    assert records_view_page["pageKind"] == "callable"
    assert records_view_page["selection"]["entry"] == "`record_id`"
    assert set(records_view_page["methods"]) == {
        member.name for group in RECORDS_VIEW_DOCUMENTATION_PAGE.groups for member in group.members
    }
    records_sections = {section["id"] for section in records_view_page["sections"]}
    assert {"data-model", "wave-access", "shared-cache", "ownership"} <= records_sections

    for spec in ACCESSOR_DOCUMENTATION_REGISTRY:
        page = accessors[spec.slug]
        assert page["pageKind"] == "class"
        assert page["methods"] == [member.name for member in spec.members]
        assert {section.anchor for section in spec.narrative_sections} <= {
            section["id"] for section in page["sections"]
        }
        serialized = json.dumps(page["sections"], ensure_ascii=False)
        assert all(member.name in serialized for member in spec.members)
        assert all(member.returns in serialized for member in spec.members if member.returns)

    context = contexts["context"]
    assert len(context["groups"]) == len(CONTEXT_DOCUMENTATION_PAGE.groups)
    assert sum(len(group["members"]) for group in context["groups"]) == sum(
        len(group.members) for group in CONTEXT_DOCUMENTATION_PAGE.groups
    )
    _assert_callable_page_is_complete(context, CONTEXT_DOCUMENTATION_PAGE)
    adapter = contexts["adapter"]
    _assert_callable_page_is_complete(adapter, ADAPTER_DOCUMENTATION_PAGE)
    _assert_callable_page_is_complete(records_view_page, RECORDS_VIEW_DOCUMENTATION_PAGE)
    assert set(visualizations) == {spec.slug for spec in VISUALIZATION_DOCUMENTATION_PAGES}
    for spec in VISUALIZATION_DOCUMENTATION_PAGES:
        _assert_callable_page_is_complete(visualizations[spec.slug], spec)
    assert all(
        [section["id"] for section in plugin["sections"]]
        == ["overview", "configuration", "output", "usage"]
        for plugin in model["plugins"]
    )


def test_site_model_meets_pre_next_rich_content_coverage_baseline():
    project_root = Path(__file__).parents[1]
    model = build_site_model(project_root)
    baseline = json.loads(
        (project_root / "docs" / "site-content-baseline.json").read_text(encoding="utf-8")
    )
    assert baseline["schema"] == "site-rich-content-baseline/v1"

    current_pages = {}
    for kind, collection in (
        ("plugin", model["plugins"]),
        ("context", model["contexts"]),
        ("accessor", model["accessors"]),
        ("visualization", model["visualizations"]),
    ):
        for page in collection:
            current_pages[page["route"]] = (kind, page)

    baseline_routes = {entry["route"] for entry in baseline["pages"]}
    assert baseline_routes == set(current_pages), "rich reference page inventory changed"
    for expected in baseline["pages"]:
        kind, page = current_pages[expected["route"]]
        assert kind == expected["kind"]
        assert set(expected["required_sections"]) <= {section["id"] for section in page["sections"]}

        member_names = set(page.get("methods", [])) or {
            member["name"] for group in page.get("groups", []) for member in group["members"]
        }
        assert set(expected["required_members"]) <= member_names
        assert set(expected["required_config"]) <= {
            entry["name"] for entry in page.get("config", [])
        }
        assert set(expected["required_fields"]) <= {
            entry["name"] for entry in page.get("fields", [])
        }

        block_counts = Counter(
            block["kind"] for section in page["sections"] for block in section["blocks"]
        )
        assert sum(expected["minimum_blocks"].values()) > 0
        for block_kind, minimum in expected["minimum_blocks"].items():
            assert block_counts[block_kind] >= minimum, (
                expected["route"],
                block_kind,
                block_counts[block_kind],
                minimum,
            )


def _independent_guide_counts(sections):
    counts = Counter()
    for section in sections:
        for block in section["blocks"]:
            counts[block["kind"]] += 1
            for inline in block.get("inlines", []):
                if inline.get("kind") == "link":
                    counts["link"] += 1
            for row in block.get("item_inlines", []):
                counts["link"] += sum(inline.get("kind") == "link" for inline in row)
            for row in block.get("table_inlines", []):
                for cell in row:
                    counts["link"] += sum(inline.get("kind") == "link" for inline in cell)
    return {kind: counts.get(kind, 0) for kind in ("paragraph", "link", "code", "table", "list")}


def _independent_guide_fingerprint(sections):
    payload = [
        {"id": section["id"], "title": section["title"], "blocks": section["blocks"]}
        for section in sections
    ]
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_public_guide_baseline_tracks_source_and_typed_content_independently():
    project_root = Path(__file__).parents[1]
    model = build_site_model(project_root)
    baseline = json.loads(
        (project_root / "docs" / "site-content-baseline.json").read_text(encoding="utf-8")
    )
    guides = {
        (guide["route"], guide["source"]): guide for guide in model["guides"] if guide.get("source")
    }
    assert len(guides) == 34
    assert len(baseline["guides"]) == 34
    for expected in baseline["guides"]:
        actual = guides[(expected["route"], expected["source"])]
        source_path = project_root / expected["source"]
        assert hashlib.sha256(source_path.read_bytes()).hexdigest() == expected["source_sha256"]
        assert actual["source_sha256"] == expected["source_sha256"]
        assert _independent_guide_fingerprint(actual["sections"]) == expected["model_fingerprint"]
        assert [
            block["kind"] for section in actual["sections"] for block in section["blocks"]
        ] == expected["block_types"]
        assert _independent_guide_counts(actual["sections"]) == expected["content_counts"]

    indexes = {(index["route"], index["source"]): index for index in model["source_indexes"]}
    assert len(indexes) == len(baseline["source_indexes"]) == 11
    for expected in baseline["source_indexes"]:
        actual = indexes[(expected["route"], expected["source"])]
        source_path = project_root / expected["source"]
        assert hashlib.sha256(source_path.read_bytes()).hexdigest() == expected["source_sha256"]
        assert _independent_guide_fingerprint(actual["sections"]) == expected["model_fingerprint"]
        assert [
            block["kind"] for section in actual["sections"] for block in section["blocks"]
        ] == expected["block_types"]
        assert _independent_guide_counts(actual["sections"]) == expected["content_counts"]


def test_markdown_blocks_preserve_ordered_lists_links_multiple_code_and_tables():
    model = build_site_model(Path(__file__).parents[1])
    guide = next(
        guide for guide in model["guides"] if guide["route"] == "/user-guide/QUICKSTART_GUIDE/"
    )
    blocks = [block for section in guide["sections"] for block in section["blocks"]]
    kinds = [block["kind"] for block in blocks]
    assert "list" in kinds and any(
        block.get("ordered") for block in blocks if block["kind"] == "list"
    )
    assert kinds.count("code") > 1
    assert "table" in kinds
    assert any(
        inline.get("kind") == "link" and inline.get("href", "").startswith("/")
        for block in blocks
        for inline in block.get("inlines", [])
    )


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


def test_plugin_guide_best_practices_keep_four_parent_items():
    from waveform_analysis.documentation.site_model import _markdown_sections

    source = Path(__file__).parents[1] / "docs/development/plugin-development/plugin_guide.md"
    sections = _markdown_sections(source.read_text(), fallback_title="Plugin guide")
    section = next(section for section in sections if section["title"] == "最佳实践")
    lists = [block for block in section["blocks"] if block["kind"] == "list"]
    assert len(lists) == 1
    tree = lists[0]["list_tree"]
    assert tree["ordered"] and tree["start"] == 1
    assert [entry["text"] for entry in tree["entries"]] == [
        "**命名规范**",
        "**性能优化**",
        "**配置管理**",
        "**测试**",
    ]
    assert all(len(entry["children"][0]["entries"]) == 3 for entry in tree["entries"])
    assert len(lists[0]["items"]) == len(lists[0]["item_inlines"]) == 16


def test_markdown_nested_lists_keep_starts_links_continuations_and_boundaries():
    from waveform_analysis.documentation.site_model import _markdown_sections

    sections = _markdown_sections(
        "## Lists\n\n3. parent\n   continued\n   - [child](https://example.com)\n"
        "     7. grandchild\n        continued\n   parent continuation\n\n"
        "4. sibling\n\nParagraph boundary\n\n0. zero\n- separate list\n\n## Next\nText\n",
        fallback_title="test",
    )
    blocks = sections[0]["blocks"]
    first = blocks[1]
    tree = first["list_tree"]
    assert tree["start"] == 3
    assert len(tree["entries"]) == 2
    parent = tree["entries"][0]
    assert parent["text"] == "parent continued parent continuation"
    child = parent["children"][0]["entries"][0]
    assert child["inlines"][0]["href"] == "https://example.com"
    assert child["children"][0]["start"] == 7
    assert child["children"][0]["entries"][0]["text"] == "grandchild continued"
    assert blocks[2]["text"] == "Paragraph boundary"
    assert blocks[3]["list_tree"]["start"] == 0
    assert blocks[4]["list_tree"]["ordered"] is False
    assert sections[1]["title"] == "Next"
