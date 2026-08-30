import hashlib
import json
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


def test_validate_manifest_rejects_invalid_workflow_cost():
    manifest = _load_manifest()
    route = next(route for route in manifest["task_routes"] if route["task"] == "run_tests")
    route["workflow_cost"] = "tiny"
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("invalid workflow_cost" in issue for issue in issues)


def test_validate_manifest_accepts_canonical_workflow_shapes():
    issues = render_agent_docs.validate_manifest(_load_manifest())
    assert not any("workflow_shape_contract" in issue for issue in issues)


def test_validate_manifest_rejects_unknown_workflow_shape():
    manifest = _load_manifest()
    manifest["workflow_shape_contract"]["allowed_shapes"].append("shortcut")
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("allowed_shapes must contain" in issue for issue in issues)


def test_validate_manifest_requires_cost_to_shape_defaults():
    manifest = _load_manifest()
    manifest["workflow_shape_contract"]["default_by_workflow_cost"]["standard"] = "compact"
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("standard/strict to staged" in issue for issue in issues)


def test_validate_manifest_forbids_compact_standard_workflow():
    manifest = _load_manifest()
    manifest["workflow_shape_contract"]["allowed_by_workflow_cost"]["standard"].append("compact")
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("allowed_by_workflow_cost must restrict" in issue for issue in issues)


def test_validate_manifest_requires_shape_driven_routes():
    manifest = _load_manifest()
    route = next(route for route in manifest["task_routes"] if route["task"] == "run_tests")
    route["workflow_mode"] = "plan_execute_review"
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("`run_tests` workflow_mode must be shape_driven" in issue for issue in issues)


def test_validate_manifest_requires_shape_field_in_all_artifacts():
    manifest = _load_manifest()
    manifest["workflow_shape_contract"]["shape_field_required_in_artifacts"].remove("review_report")
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("shape_field_required_in_artifacts must cover" in issue for issue in issues)


def test_validate_manifest_requires_compact_task_report():
    manifest = _load_manifest()
    manifest["workflow_shape_contract"]["shapes"]["compact"]["artifact"] = "execution_report"
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("`compact` must require task_report" in issue for issue in issues)


def test_validate_manifest_rejects_direct_mutation():
    manifest = _load_manifest()
    manifest["workflow_shape_contract"]["shapes"]["direct"]["mutation"] = "write_scoped"
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("`direct` mutation must be read_only" in issue for issue in issues)


def test_validate_manifest_requires_shape_escalation_triggers():
    manifest = _load_manifest()
    manifest["workflow_shape_contract"]["escalation_triggers"].remove("gate_failure")
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("missing escalation_triggers: gate_failure" in issue for issue in issues)


def test_validate_manifest_requires_gate_trigger_policy():
    manifest = _load_manifest()
    route = next(route for route in manifest["task_routes"] if route["task"] == "run_tests")
    route["gate_trigger_policy"] = []
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("missing gate_trigger_policy" in issue for issue in issues)


def test_validate_manifest_requires_strict_route_artifacts():
    manifest = _load_manifest()
    route = next(route for route in manifest["task_routes"] if route["task"] == "retire_compat")
    route["required_artifacts"] = ["plan_brief", "execution_report"]
    issues = render_agent_docs.validate_manifest(manifest)
    assert any(
        "Strict route `retire_compat` missing required_artifacts" in issue for issue in issues
    )


def test_validate_manifest_rejects_profile_with_unknown_role():
    manifest = _load_manifest()
    profile = manifest["agent_profiles"][0]
    profile["phase_participation"]["executing"]["allowed_roles"] = ["executor.graph"]
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("references unknown roles: executor.graph" in issue for issue in issues)


def test_validate_manifest_rejects_profile_without_route_handoff_role():
    manifest = _load_manifest()
    profile = manifest["agent_profiles"][0]
    profile["phase_participation"]["executing"]["allowed_roles"] = ["executor.qa"]
    profile["applicable_routes"] = ["modify_plugin"]
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("no allowed role in route `modify_plugin`" in issue for issue in issues)


def test_validate_manifest_rejects_profile_that_owns_lifecycle_states():
    manifest = _load_manifest()
    manifest["agent_profile_contract"]["profiles_own_lifecycle_states"] = True
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("profiles_own_lifecycle_states must be False" in issue for issue in issues)


def test_validate_manifest_rejects_noncanonical_profile_artifact_fields():
    manifest = _load_manifest()
    manifest["agent_profile_contract"]["required_artifact_fields"]["review_report"] = [
        "profile_review"
    ]
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("canonical profile fields" in issue for issue in issues)


def test_validate_manifest_requires_profile_planning_outputs():
    manifest = _load_manifest()
    profile = manifest["agent_profiles"][0]
    profile["phase_participation"]["planning"]["required_outputs"] = []
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("planning missing required_outputs" in issue for issue in issues)


def test_validate_manifest_preserves_planner_state_ownership():
    manifest = _load_manifest()
    profile = manifest["agent_profiles"][0]
    profile["phase_participation"]["planning"]["owns_state"] = True
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("planning.owns_state must be False" in issue for issue in issues)


def test_validate_manifest_preserves_reviewer_host_role():
    manifest = _load_manifest()
    profile = manifest["agent_profiles"][0]
    profile["phase_participation"]["reviewing"]["host_role"] = "planner"
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("reviewing.host_role must be reviewer" in issue for issue in issues)


def test_validate_manifest_rejects_noncanonical_phase_contract():
    manifest = _load_manifest()
    manifest["agent_profile_contract"]["phase_contracts"]["planning"]["mode"] = "assignee"
    issues = render_agent_docs.validate_manifest(manifest)
    assert any("phase_contracts must preserve canonical" in issue for issue in issues)


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
    assert "`workflow_cost`: `strict`" in sections["profile_summary_retire_compat"]
    assert "## Gate Trigger Policy" in sections["profile_summary_retire_compat"]


def test_build_generated_sections_include_graph_engineer_profile():
    sections = render_agent_docs.build_generated_sections(_load_manifest())
    catalog = sections["agent_profile_catalog"]
    assert "`graph_engineer`" in catalog
    assert "`executor.plugin`" in catalog
    assert "`runtime_lineage`" in catalog
    assert "`planning`：`contributor`" in catalog
    assert "`reviewing`：`review_subject`" in catalog


def test_modify_code_profile_is_independent_and_uses_code_executor(tmp_path):
    profile_path = (
        render_agent_docs.PROJECT_ROOT
        / "docs"
        / "agents"
        / "protocol"
        / "route-profiles"
        / "modify_code.md"
    )
    profile = profile_path.read_text(encoding="utf-8")
    assert "`executor.code`" in profile
    assert "`executor.plugin`" not in profile

    manifest = _load_manifest()
    route = next(item for item in manifest["task_routes"] if item["task"] == "modify_code")
    route["profile_doc"] = "docs/agents/protocol/route-profiles/modify_code.md"
    sections = render_agent_docs.build_generated_sections(manifest, tmp_path)
    rendered = render_agent_docs.render_file(profile_path, sections)

    assert "`task`: `modify_code`" in rendered
    assert "`profile_doc`: `docs/agents/protocol/route-profiles/modify_code.md`" in rendered
    assert "`executor_role`: `executor.code`" in rendered
    assert (
        "modify_plugin.md"
        not in rendered.split("<!-- END GENERATED: profile_summary_modify_code -->", 1)[0]
    )


def test_collect_targets_include_retire_compat_profile():
    targets = render_agent_docs.collect_targets()
    assert any(path.name == "retire_compat.md" for path in targets)


def test_collect_targets_include_skills_adapter():
    targets = render_agent_docs.collect_targets()
    assert any(path.as_posix().endswith("docs/agents/adapters/skills.md") for path in targets)


def test_profile_artifact_templates_expose_canonical_fields():
    artifact_root = render_agent_docs.PROJECT_ROOT / "docs" / "agents" / "protocol" / "artifacts"
    expected_fields = {
        "plan_brief.md": ("agent_profile", "profile_plan"),
        "execution_report.md": ("agent_profile",),
        "review_report.md": ("agent_profile", "agent_profile_review"),
        "task_report.md": ("agent_profile", "profile_plan", "agent_profile_review"),
    }
    for name, fields in expected_fields.items():
        content = (artifact_root / name).read_text(encoding="utf-8")
        for field in fields:
            assert f"`{field}`" in content


def test_profile_route_templates_expose_profile_handoff_fields():
    manifest = _load_manifest()
    routes = {route["task"]: route for route in manifest["task_routes"]}
    for profile in manifest["agent_profiles"]:
        for route_name in profile["applicable_routes"]:
            profile_doc = render_agent_docs.PROJECT_ROOT / routes[route_name]["profile_doc"]
            content = profile_doc.read_text(encoding="utf-8")
            planner_section = content.split("## Planner Template", 1)[1].split(
                "## Executor Template", 1
            )[0]
            executor_section = content.split("## Executor Template", 1)[1].split(
                "## Reviewer Template", 1
            )[0]
            reviewer_section = content.split("## Reviewer Template", 1)[1]
            assert "`agent_profile`" in planner_section
            assert "`profile_plan`" in planner_section
            assert "`agent_profile`" in executor_section
            assert "`agent_profile`" in reviewer_section
            assert "`agent_profile_review`" in reviewer_section


def test_build_generated_sections_discovers_manifest_routes_without_route_allowlist(tmp_path):
    manifest = _load_manifest()
    manifest["task_routes"] = [
        route for route in manifest["task_routes"] if route["task"] != "modify_plugin"
    ]
    manifest["task_routes"].insert(
        0,
        {
            "task": "custom_route",
            "summary": "测试用自定义 route",
            "workflow_mode": "shape_driven",
            "workflow_cost": "light",
            "primary_doc": "docs/agents/workflows.md",
            "profile_doc": "docs/agents/protocol/route-profiles/custom_route.md",
            "aliases": [],
            "secondary_docs": [],
            "read_order": ["AGENTS.md"],
            "blocking_gates": ["custom_gate"],
            "gate_trigger_policy": ["custom policy"],
            "commands": ["custom command"],
        },
    )

    sections = render_agent_docs.build_generated_sections(manifest, tmp_path)

    assert "profile_summary_custom_route" in sections
    assert "`custom_route`" in sections["supported_routes"]
    assert "custom_route.md" in sections["route_profile_index"]
    assert "profile_summary_modify_plugin" not in sections


def test_build_generated_sections_reflects_manifest_shape_cost_and_state_changes(tmp_path):
    manifest = _load_manifest()
    shape_contract = manifest["workflow_shape_contract"]
    shape_contract["allowed_shapes"].append("queued")
    shape_contract["shapes"]["queued"] = {
        "mutation": "read_only",
        "artifact": "none",
        "terminal_condition": "queued_task",
        "topology": "queue",
    }
    shape_contract["default_by_workflow_cost"]["experimental"] = "queued"
    shape_contract["allowed_by_workflow_cost"]["experimental"] = ["queued"]
    manifest["lifecycle"]["primary_states"].append("queued")
    manifest["lifecycle"]["transitions"].append(
        {"from": "created", "to": "queued", "condition": "queue_requested"}
    )

    sections = render_agent_docs.build_generated_sections(manifest, tmp_path)

    assert "`experimental`" in sections["workflow_cost_catalog"]
    assert "`queued`" in sections["workflow_shape_catalog"]
    assert "`queued` (queue_requested)" in sections["lifecycle_state_catalog"]


def test_collect_targets_discovers_new_marked_profile(tmp_path):
    profile = tmp_path / "docs" / "agents" / "protocol" / "route-profiles" / "custom.md"
    profile.parent.mkdir(parents=True)
    profile.write_text(
        "<!-- BEGIN GENERATED: profile_summary_custom -->\n"
        "placeholder\n"
        "<!-- END GENERATED: profile_summary_custom -->\n",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("no markers\n", encoding="utf-8")

    targets = render_agent_docs.collect_targets(tmp_path)

    assert targets == [profile]


def test_render_active_plan_view_reads_current_task_records(tmp_path):
    task_path = tmp_path / "docs" / "agents" / "runs" / "current" / "demo" / "task.yaml"
    task_path.parent.mkdir(parents=True)
    task_path.write_text(
        yaml.safe_dump(
            {
                "metadata": {"id": "demo"},
                "spec": {
                    "route": "modify_code",
                    "workflow_cost": "standard",
                    "workflow_shape": "staged",
                },
                "status": {"state": "planning", "condition": "NeedsRevalidation"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    rendered = render_agent_docs.render_active_plan_view(tmp_path)

    view = yaml.safe_load(rendered)
    assert view["source"] == "docs/agents/runs/current/*/task.yaml"
    assert view["active_plans"] == [
        {
            "task_id": "demo",
            "state": "planning",
            "route": "modify_code",
            "workflow_cost": "standard",
            "workflow_shape": "staged",
            "condition": "NeedsRevalidation",
            "task_file": "docs/agents/runs/current/demo/task.yaml",
            "legacy_plan": "docs/agents/runs/current/demo/legacy-plan.md",
        }
    ]


def test_legacy_archive_manifest_preserves_count_size_and_hashes():
    manifest_path = (
        render_agent_docs.PROJECT_ROOT
        / "docs"
        / "agents"
        / "runs"
        / "archive"
        / "legacy"
        / "MANIFEST.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest["entries"]

    assert manifest["file_count"] == 148
    assert len(entries) == 148
    assert len({entry["archive_path"] for entry in entries}) == 148
    for entry in entries:
        archived = render_agent_docs.PROJECT_ROOT / entry["archive_path"]
        content = archived.read_bytes()
        assert len(content) == entry["size"]
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]
