import json
from pathlib import Path
import subprocess
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run(cmd):
    return subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)


def test_assess_change_impact_cli_writes_json(tmp_path):
    out_json = tmp_path / "impact.json"
    result = _run(
        [
            sys.executable,
            "scripts/assess_change_impact.py",
            "--base",
            "HEAD",
            "--json-out",
            str(out_json),
        ]
    )

    # high-risk change returns 1; no/high can both happen depending on current diff.
    assert result.returncode in (0, 1)
    assert out_json.exists()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "records" in payload
    assert "risk_counts" in payload


@pytest.fixture
def retirement_repo(tmp_path, monkeypatch):
    """Use real Git ancestry/deletions and the real AgentTask validator."""
    import yaml

    from scripts import assess_change_impact as impact
    from scripts.agent_workflow import canonical_spec_sha256

    def create(*, metadata_drift=False):
        root = tmp_path / "repo"
        root.mkdir()

        def git(*args):
            result = subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, check=True
            )
            return result.stdout.strip()

        git("init")
        git("config", "user.email", "quality-test@example.invalid")
        git("config", "user.name", "Quality Test")
        plugin_path = "waveform_analysis/core/plugins/retired.py"
        plugin = root / plugin_path
        plugin.parent.mkdir(parents=True)
        source = (
            "class RetiredPlugin(Plugin):\n"
            "    provides = 'retired'\n"
            "    version = '1.0.0'\n"
            "    depends_on = ['records']\n"
        )
        plugin.write_text(source)
        manifest_path = root / impact.RETIREMENTS_MANIFEST
        manifest_path.parent.mkdir(parents=True)
        (manifest_path.parent / "index.yaml").write_text(
            (PROJECT_ROOT / "docs/agents/index.yaml").read_text()
        )
        task_relpath = "docs/agents/runs/current/retire-legacy-df-20261105/task.yaml"
        task = yaml.safe_load((PROJECT_ROOT / task_relpath).read_text())
        task["spec"]["compat_inventory"]["items"] = [
            {"legacy_form": "retired/RetiredPlugin", "delete_action": "remove"}
        ]
        digest = canonical_spec_sha256(task["spec"])
        task["status"]["plan_sha256"] = digest
        task["status"]["review"]["plan_sha256"] = digest
        task_path = root / task_relpath
        task_path.parent.mkdir(parents=True)
        task_path.write_text(yaml.safe_dump(task))
        git("add", ".")
        git("commit", "-m", "initial plugin and approved retirement")
        base = git("rev-parse", "HEAD")
        if metadata_drift:
            plugin.write_text(source.replace("1.0.0", "2.0.0"))
            git("add", ".")
            git("commit", "-m", "change metadata after comparison base")
        git("rm", plugin_path)
        git("commit", "-m", "remove approved plugin")
        commit = git("rev-parse", "HEAD")
        manifest = {
            "schema_version": 1,
            "retirements": [
                {
                    "file": plugin_path,
                    "class": "RetiredPlugin",
                    "provides": "retired",
                    "removal_commit": commit,
                    "approval_task": task_relpath,
                }
            ],
        }
        manifest_path.write_text(yaml.safe_dump(manifest))
        monkeypatch.setattr(impact, "PROJECT_ROOT", root)
        monkeypatch.setattr(sys, "argv", ["assess_change_impact.py", "--base", base])
        return impact, root, base, manifest_path, task_path, plugin, source, git

    return create


def test_approved_retirement_keeps_high_risk_but_passes_gate(retirement_repo):
    impact, _root, base, *_ = retirement_repo()
    report = impact.assess(base)
    assert report["risk_counts"] == {"high": 1, "medium": 0, "low": 0}
    assert report["approved_retirement_count"] == 1
    assert report["unapproved_high_risk_count"] == 0
    assert report["records"][0]["approved_retirement"]["approval_task"].endswith("task.yaml")
    assert impact.main() == 0


def test_retirement_without_manifest_keeps_original_failure(retirement_repo):
    impact, _root, base, manifest, *_ = retirement_repo()
    manifest.unlink()
    assert impact.assess(base)["unapproved_high_risk_count"] == 1
    assert impact.main() == 1


@pytest.mark.parametrize(
    "case",
    [
        "new_class",
        "provides_change",
        "dtype_change",
        "depends_change",
        "downstream",
        "metadata_drift",
    ],
)
def test_retirement_does_not_approve_other_high_risks(retirement_repo, case):
    impact, root, base, _manifest, _task, plugin, source, _git = retirement_repo(
        metadata_drift=case == "metadata_drift"
    )
    plugin.parent.mkdir(parents=True, exist_ok=True)
    if case == "new_class":
        (plugin.parent / "new.py").write_text("class NewPlugin(Plugin):\n    provides = 'new'\n")
    elif case == "provides_change":
        plugin.write_text(source.replace("'retired'", "'renamed'"))
    elif case == "dtype_change":
        plugin.write_text(source + "    output_dtype = [('value', 'i8')]\n")
    elif case == "depends_change":
        plugin.write_text(source.replace("['records']", "['other']"))
    elif case == "downstream":
        (plugin.parent / "consumer.py").write_text(
            "class ConsumerPlugin(Plugin):\n    provides = 'consumer'\n    depends_on = ['retired']\n"
        )
    report = impact.assess(base)
    assert report["unapproved_high_risk_count"] >= 1
    if case != "new_class":
        assert report["approved_retirement_count"] == 0
    assert impact.main() == 1


@pytest.mark.parametrize(
    "case",
    [
        "stale_digest",
        "stale_review_digest",
        "missing_task",
        "missing_confirmation",
        "partial_inventory_identity",
        "keep_inventory_action",
        "unapproved_review",
        "unconfirmed_deletion",
        "wrong_identity",
        "not_removal_commit",
        "not_ancestor",
        "duplicate",
        "malformed_manifest",
    ],
)
def test_invalid_retirement_evidence_fails_clearly(retirement_repo, case, capsys):
    import yaml

    from scripts.agent_workflow import canonical_spec_sha256

    impact, _root, _base, manifest_path, task_path, _plugin, _source, git = retirement_repo(
        metadata_drift=case == "not_removal_commit"
    )
    task = yaml.safe_load(task_path.read_text())
    manifest = yaml.safe_load(manifest_path.read_text())
    if case == "stale_digest":
        task["spec"]["goal"] += " changed after approval"
    elif case == "stale_review_digest":
        task["status"]["review"]["plan_sha256"] = "0" * 64
    elif case == "missing_task":
        task_path.unlink()
    elif case == "missing_confirmation":
        task["spec"]["compat_inventory"]["confirmation"] = ""
        digest = canonical_spec_sha256(task["spec"])
        task["status"]["plan_sha256"] = digest
        task["status"]["review"]["plan_sha256"] = digest
    elif case == "unapproved_review":
        task["status"]["review"]["decision"] = "rejected"
    elif case == "unconfirmed_deletion":
        task["status"]["review"]["gate_results"]["deletion_scope_confirmed"]["status"] = "FAIL"
    elif case == "wrong_identity":
        manifest["retirements"][0]["provides"] = "another"
    elif case == "not_removal_commit":
        manifest["retirements"][0]["removal_commit"] = git("rev-parse", "HEAD^")
    elif case == "not_ancestor":
        commit = git("commit-tree", "HEAD^{tree}", "-m", "detached commit")
        manifest["retirements"][0]["removal_commit"] = commit
    elif case == "duplicate":
        manifest["retirements"].append(manifest["retirements"][0].copy())
    elif case in {"partial_inventory_identity", "keep_inventory_action"}:
        item = task["spec"]["compat_inventory"]["items"][0]
        if case == "partial_inventory_identity":
            item["legacy_form"] += "Extra"
        else:
            item["delete_action"] = "keep"
        digest = canonical_spec_sha256(task["spec"])
        task["status"]["plan_sha256"] = digest
        task["status"]["review"]["plan_sha256"] = digest
    elif case == "malformed_manifest":
        manifest = [manifest]
    if case != "missing_task":
        task_path.write_text(yaml.safe_dump(task))
    manifest_path.write_text(yaml.safe_dump(manifest))
    assert impact.main() == 2
    assert "ERROR:" in capsys.readouterr().err


@pytest.mark.slow
def test_schema_compat_check_cli_with_smoke(tmp_path):
    out_json = tmp_path / "schema.json"
    result = _run(
        [
            sys.executable,
            "scripts/schema_compat_check.py",
            "--base",
            "HEAD",
            "--run-smoke",
            "--json-out",
            str(out_json),
        ]
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert out_json.exists()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "dtype_changes" in payload
    assert payload["contract_issues"] == []
    assert payload["smoke_error"] is None
    products = payload["smoke_result"]["products"]
    assert products["records"]["count"] == 24
    assert products["hit_threshold"]["count"] == 24
    assert products["peaks"]["count"] == 12
    assert all(product["count"] > 0 for product in products.values())
    assert products["records"]["fields"]["board"] == "int16"
    assert products["peaks"]["fields"]["time_start"] == "int64"
    assert products["peaks"]["fields"]["area"] == "float32"


@pytest.mark.slow
def test_performance_regression_check_cli_runs(tmp_path):
    out_json = tmp_path / "perf.json"
    result = _run(
        [
            sys.executable,
            "scripts/performance_regression_check.py",
            "--base",
            "HEAD",
            "--repeats",
            "1",
            "--time-threshold-pct",
            "500",
            "--mem-threshold-pct",
            "500",
            "--json-out",
            str(out_json),
        ]
    )

    assert result.returncode == 0
    assert out_json.exists()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert "before" in payload
    assert "after" in payload
    assert "comparison" in payload
    assert "hit_threshold" in payload["before"]
    assert "hit_threshold" in payload["after"]
    assert "hit_merged" in payload["after"]
    assert "peaks" in payload["after"]
    assert payload["comparison"]["valid"]
    for side in ("base", "current"):
        source = payload["provenance"][side]
        assert len(source["commit"]) == 40
        assert Path(source["executable"]).resolve() == Path(sys.executable).resolve()
        assert Path(source["module_paths"]["waveform_analysis"]).is_relative_to(
            Path(source["checkout"]) / "waveform_analysis"
        )
    assert payload["provenance"]["base"]["harness"] == payload["provenance"]["current"]["harness"]


def test_performance_regression_check_defaults_to_five_repeats(monkeypatch):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    from scripts import performance_regression_check

    repeats_seen = {}

    source = {
        "commit": "0" * 40,
        "dirty": False,
        "checkout": str(PROJECT_ROOT),
        "executable": sys.executable,
        "module_paths": {"waveform_analysis": str(PROJECT_ROOT / "waveform_analysis/__init__.py")},
    }

    def fake_run_base(base, targets, repeats):
        repeats_seen["base"] = repeats
        assert targets == ["st_waveforms", "hit", "hit_threshold", "hit_merged", "peaks"]
        return {}, source

    def fake_run_current(targets, repeats):
        repeats_seen["current"] = repeats
        return {}, source

    def fake_compare(
        base_report,
        current_report,
        time_threshold_pct,
        mem_threshold_pct,
        expected_targets,
        expected_repeats,
    ):
        assert expected_repeats == 5
        return {
            "rows": [],
            "regressions": [],
            "errors": [],
            "valid": True,
            "time_threshold_pct": time_threshold_pct,
            "mem_threshold_pct": mem_threshold_pct,
        }

    monkeypatch.setattr(performance_regression_check, "_run_base", fake_run_base)
    monkeypatch.setattr(performance_regression_check, "_run_current", fake_run_current)
    monkeypatch.setattr(performance_regression_check, "compare", fake_compare)

    monkeypatch.setattr(sys, "argv", ["performance_regression_check.py", "--base", "HEAD"])
    assert performance_regression_check.main() == 0
    assert repeats_seen == {"base": 5, "current": 5}


def test_release_artifact_sync_defaults_to_five_perf_repeats(monkeypatch):
    from scripts import release_artifact_sync

    captured = {}

    def fake_run_release_sync(**kwargs):
        captured.update(kwargs)
        return {"base": kwargs["base"], "overall_ok": True, "checks": []}

    monkeypatch.setattr(release_artifact_sync, "run_release_sync", fake_run_release_sync)

    monkeypatch.setattr(sys, "argv", ["release_artifact_sync.py", "--base", "HEAD"])
    assert release_artifact_sync.main() == 0
    assert captured["perf_repeats"] == 5


def test_performance_compare_uses_median_and_ignores_sub_megabyte_noise(monkeypatch):
    monkeypatch.syspath_prepend(str(PROJECT_ROOT / "scripts"))
    from scripts.performance_regression_check import compare

    before = {
        "target": {
            "sample_count": 1,
            "samples": [{"time_sec": 1.0, "peak_mem_mb": 0.08}],
            "avg_time_sec": 1.0,
            "max_time_sec": 1.0,
            "avg_peak_mem_mb": 0.08,
            "max_peak_mem_mb": 0.08,
            "median_time_sec": 1.0,
            "median_peak_mem_mb": 0.08,
        }
    }
    after = {
        "target": {
            "sample_count": 1,
            "samples": [{"time_sec": 0.99, "peak_mem_mb": 0.12}],
            "avg_time_sec": 1.2,
            "max_time_sec": 1.2,
            "avg_peak_mem_mb": 0.12,
            "max_peak_mem_mb": 0.12,
            "median_time_sec": 0.99,
            "median_peak_mem_mb": 0.12,
        }
    }

    report = compare(before, after, time_threshold_pct=10.0, mem_threshold_pct=15.0)

    assert report["regressions"] == []
    assert report["rows"][0]["time_delta_pct"] == pytest.approx(-1.0)


def test_release_artifact_sync_key_tests_run_full_pytest(monkeypatch):
    from scripts import release_artifact_sync

    commands = []

    def fake_run(cmd, cwd=release_artifact_sync.PROJECT_ROOT):
        commands.append(cmd)
        return 0, "", ""

    monkeypatch.setattr(release_artifact_sync, "_run", fake_run)

    ok, detail = release_artifact_sync._run_key_tests("HEAD")

    assert ok
    assert detail["schema_smoke_rc"] == 0
    assert detail["full_pytest_rc"] == 0
    assert commands == [
        [
            sys.executable,
            "scripts/schema_compat_check.py",
            "--base",
            "HEAD",
            "--run-smoke",
        ],
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
        ],
    ]


def test_release_artifact_sync_keeps_legacy_reference_pages_allowed(tmp_path):
    from scripts import release_artifact_sync

    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()
    (expected / "INDEX.md").write_text("index\n", encoding="utf-8")
    (actual / "INDEX.md").write_text("index\n", encoding="utf-8")
    (actual / "s1_s2.md").write_text("legacy compatibility page\n", encoding="utf-8")

    assert release_artifact_sync._compare_docs(expected, actual) == []

    (actual / "unexpected.md").write_text("not allow-listed\n", encoding="utf-8")
    assert release_artifact_sync._compare_docs(expected, actual) == ["多余文档: unexpected.md"]
