"""Isolation and transactional staging checks using controlled npm commands."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("docs_build", ROOT / "scripts/docs_build.py")
docs_build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(docs_build)


def tree_hash(root):
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode() + path.read_bytes())
    return digest.hexdigest()


@pytest.fixture
def fake_npm(monkeypatch):
    from waveform_analysis.documentation.site_model import load_site_model, write_site_model
    from waveform_analysis.documentation.site_web import NextSiteBuilder

    old = ROOT / "waveform_analysis/documentation/site_dist"
    model = load_site_model(old / "site-model.v1.json")

    def model_builder(self, path):
        write_site_model(model, path)
        return model

    monkeypatch.setattr(NextSiteBuilder, "_build_model", model_builder)

    def run(command, *, cwd, env, **kwargs):
        app = Path(cwd)
        assert not app.is_relative_to(ROOT)
        assert env["PYTHONPATH"] == str(ROOT)
        assert Path(env["npm_config_cache"]).name == "npm-cache"
        if command == ["npm", "ci", "--ignore-scripts"]:
            assert not (app / "node_modules").exists()
            assert not (app / ".next").exists()
            (app / "node_modules").mkdir()
        if command == ["npm", "run", "build"]:
            shutil.copytree(old, env["WAVEFORM_SITE_EXPORT_DIR"], dirs_exist_ok=True)
        return subprocess.CompletedProcess(command, 0)

    return run


def test_default_isolation_and_duplicate(tmp_path, fake_npm):
    old = ROOT / "waveform_analysis/documentation/site_dist"
    before = tree_hash(old)
    report = docs_build.build(ROOT, "one", tmp_path, command_runner=fake_npm)
    assert report["status"] == "success", report
    assert tree_hash(old) == before
    assert [c["exit_status"] for c in report["commands"]] == [0, 0, 0]
    evidence = tmp_path / "runs/one/report.json"
    original = evidence.read_bytes()
    with pytest.raises(FileExistsError):
        docs_build.build(ROOT, "one", tmp_path, command_runner=fake_npm)
    assert evidence.read_bytes() == original
    assert Path(report["artifacts"]["model"]).is_file()


def test_failure_report_and_exit(tmp_path, monkeypatch):
    old = ROOT / "waveform_analysis/documentation/site_dist"
    before = tree_hash(old)

    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(17, command)

    report = docs_build.build(ROOT, "fail", tmp_path, True, command_runner=fail)
    assert report["status"] == "failed"
    assert report["commands"][0]["exit_status"] == 17
    assert tree_hash(old) == before
    assert json.loads(Path(report["artifacts"]["report"]).read_text())["error"]
    monkeypatch.setattr(docs_build, "build", lambda *args: report)
    assert docs_build.main(["build", "--workspace", str(ROOT), "--run-id", "failure"]) == 1


def test_stage_success_and_rollback(tmp_path, monkeypatch):
    site, destination = tmp_path / "site", tmp_path / "site_dist"
    site.mkdir()
    destination.mkdir()
    (site / "index.html").write_text("new")
    (destination / "index.html").write_text("old")

    def validate(path):
        return None

    rename = Path.rename

    def fail_candidate(self, target):
        if self.name == "candidate":
            raise OSError("replacement failed")
        return rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_candidate)
    with pytest.raises(OSError, match="replacement failed"):
        docs_build.stage_site(site, destination, validate)
    assert (destination / "index.html").read_text() == "old"
    monkeypatch.setattr(Path, "rename", rename)

    def invalid(path):
        raise ValueError("invalid export")

    with pytest.raises(ValueError, match="invalid export"):
        docs_build.stage_site(site, destination, invalid)
    assert (destination / "index.html").read_text() == "old"
    docs_build.stage_site(site, destination, validate)
    assert (destination / "index.html").read_text() == "new"


@pytest.mark.parametrize("run_id", ["../escape", ".", "x/y", "x.y", "", "a" * 81])
def test_unsafe_id(tmp_path, run_id):
    with pytest.raises(ValueError):
        docs_build.build(ROOT, run_id, tmp_path)
    assert not (tmp_path / "runs").exists()


def test_unsafe_paths(tmp_path):
    with pytest.raises(ValueError, match="outside workspace"):
        docs_build.build(ROOT, "bad", ROOT / "external")
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "target", target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        docs_build.build(ROOT, "bad", link)
    with pytest.raises(ValueError, match="symlink"):
        docs_build.stage_site(tmp_path, link, lambda p: None)


def test_fingerprint_actual_bytes(tmp_path):
    source = tmp_path / "docs"
    source.mkdir()
    page = source / "guide.md"
    page.write_text("first")
    before = docs_build.input_fingerprint(tmp_path)
    page.write_text("second")
    after = docs_build.input_fingerprint(tmp_path)
    assert before != after
    for name in ("site_dist", ".git", "runs"):
        ignored = source / name
        ignored.mkdir()
        (ignored / "report.json").write_text("generated")
    assert docs_build.input_fingerprint(tmp_path) == after


def test_real_build_evidence():
    evidence_path = Path("/tmp/waveform-docs-skill-task/real-build-evidence.json")
    if not evidence_path.exists():
        pytest.skip("real acceptance builds have not run")
    evidence = json.loads(evidence_path.read_text())
    assert evidence["default_before_hash"] == evidence["default_after_hash"]
    for key in ("default_report", "staged_report"):
        path = Path(evidence[key])
        assert path.is_absolute()
        report = json.loads(path.read_text())
        assert report["status"] == "success"
        assert "docs-build external workspace" in Path(report["artifacts"]["model"]).read_text()
        site = Path(report["artifacts"]["site"])
        assert (
            "docs-build external workspace"
            in (site / "user-guide/docs-build/index.html").read_text()
        )
    import tempfile

    from waveform_analysis.documentation.site_web import copy_prebuilt_site

    with tempfile.TemporaryDirectory() as temporary:
        copy_prebuilt_site(
            ROOT / "waveform_analysis/documentation/site_dist", Path(temporary) / "verified"
        )


def test_fresh_process_leaves_entire_workspace_unchanged(tmp_path):
    """Exercise real cold imports, including Numba, with controlled npm output."""
    import os
    import sys

    workspace = tmp_path / "checkout"
    workspace.mkdir()
    for name in ("docs", "waveform_analysis", "scripts"):
        shutil.copytree(
            ROOT / name,
            workspace / name,
            ignore=lambda _, names: [n for n in names if docs_build.ignored(n)],
        )
    for name in ("pyproject.toml", "AGENTS.md"):
        shutil.copy2(ROOT / name, workspace / name)

    def snapshot():
        import hashlib

        return {
            str(path.relative_to(workspace)): (
                path.stat().st_mtime_ns,
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
            )
            for path in [workspace, *sorted(workspace.rglob("*"))]
        }

    before = snapshot()
    code = r"""
import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
workspace, original, build_root = map(pathlib.Path, sys.argv[1:])
spec = importlib.util.spec_from_file_location("docs_build", workspace / "scripts/docs_build.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
def runner(command, *, env, **kwargs):
    if command == ["npm", "ci", "--ignore-scripts"]:
        (pathlib.Path(kwargs["cwd"]) / "node_modules").mkdir()
    assert pathlib.Path(env["NUMBA_CACHE_DIR"]).is_relative_to(build_root)
    if command == ["npm", "run", "build"]:
        shutil.copytree(original / "waveform_analysis/documentation/site_dist",
                        env["WAVEFORM_SITE_EXPORT_DIR"], dirs_exist_ok=True)
    return subprocess.CompletedProcess(command, 0)
report = module.build(workspace, "cold", build_root, command_runner=runner)
assert report["status"] == "success", json.dumps(report)
assert pathlib.Path(report["import_source"]).is_relative_to(workspace)
"""
    env = dict(os.environ, PYTHONPATH=str(workspace), PYTHONDONTWRITEBYTECODE="1")
    env["GIT_DIR"] = subprocess.check_output(
        ["git", "rev-parse", "--absolute-git-dir"], cwd=ROOT, text=True
    ).strip()
    env["GIT_WORK_TREE"] = str(workspace)
    env["NUMBA_CACHE_DIR"] = str(workspace / "inherited-cache")
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(workspace), str(ROOT), str(tmp_path / "build")],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot() == before
    assert (tmp_path / "build/runs/cold/numba-cache").is_dir()
