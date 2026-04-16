from pathlib import Path

import pytest
import yaml

from scripts import render_agent_docs


def _load_manifest() -> dict:
    return yaml.safe_load(render_agent_docs.MANIFEST_PATH.read_text(encoding="utf-8"))


def test_validate_manifest_current_repo_has_no_errors():
    issues = render_agent_docs.validate_manifest(_load_manifest())
    assert issues == []


def test_validate_manifest_rejects_alias_with_redefined_fields():
    manifest = _load_manifest()
    alias = next(route for route in manifest["task_routes"] if route["task"] == "release_check")
    alias["summary"] = "bad alias"
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("must not redefine" in issue for issue in issues)


def test_render_file_replaces_generated_section():
    path = Path(__file__).parent / "_tmp_render_agent_docs.md"
    path.write_text(
        """Header
<!-- BEGIN GENERATED: supported_routes -->
old
<!-- END GENERATED: supported_routes -->
Footer
""",
        encoding="utf-8",
    )
    sections = {"supported_routes": "- `modify_plugin`：demo"}
    try:
        rendered = render_agent_docs.render_file(path, sections)
        assert "- `modify_plugin`：demo" in rendered
        assert "old" not in rendered
    finally:
        path.unlink(missing_ok=True)


def test_render_file_fails_for_unknown_section(tmp_path: Path):
    path = tmp_path / "doc.md"
    path.write_text(
        """<!-- BEGIN GENERATED: unknown -->
placeholder
<!-- END GENERATED: unknown -->
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown generated section"):
        render_agent_docs.render_file(path, {"supported_routes": "x"})


def test_build_generated_sections_include_retire_compat():
    sections = render_agent_docs.build_generated_sections(_load_manifest())
    assert "profile_summary_retire_compat" in sections
    assert "`retire_compat`" in sections["supported_routes"]


def test_collect_targets_include_retire_compat_profile():
    targets = render_agent_docs.collect_targets()
    assert any(path.name == "retire_compat.md" for path in targets)
