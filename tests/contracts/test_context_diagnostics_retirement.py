"""Keep run configuration and read-only diagnosis useful after facade retirement."""

import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from waveform_analysis import Context
from waveform_analysis.core.hardware.channel import get_plugin_run_config
from waveform_analysis.core.storage.cache_diagnostics import DiagnosticIssueType

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("as_plugin", [False, True])
@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"plugins": {"hit": {"height": 40}}}, {"height": 40}),
        ({"plugins": {"hit": {}}}, {}),
        ({"plugins": {"other": {"height": 90}}}, {"height": 20}),
        ({"plugins": {"hit": None}}, {"height": 20}),
        ({}, {"height": 20}),
    ],
)
def test_plugin_run_config_preserves_file_precedence_and_fallback(
    tmp_path, as_plugin, payload, expected
):
    run_path = tmp_path / "run_001.json"
    run_path.write_text(json.dumps(payload), encoding="utf-8")
    ctx = Context(
        storage_dir=str(tmp_path / "cache"),
        config={
            "run_config_path": str(tmp_path / "{run_id}.json"),
            "hit": {"runs": {"run_001": {"height": 20}, "run_002": {"height": 25}}},
        },
    )
    plugin = SimpleNamespace(provides="hit") if as_plugin else "hit"

    assert get_plugin_run_config(ctx, plugin, "run_001") == expected
    assert get_plugin_run_config(ctx, plugin, "run_002") == {"height": 25}
    assert get_plugin_run_config(ctx, plugin, "missing") == {}


def test_plugin_run_config_supports_config_only_and_mapping_contexts():
    ctx = SimpleNamespace(config=MappingProxyType({"hit": {"runs": {"run_001": {"height": 20}}}}))
    assert get_plugin_run_config(ctx, "hit", "run_001") == {"height": 20}

    ctx.get_run_config = lambda run_id: MappingProxyType(
        {"plugins": MappingProxyType({"hit": MappingProxyType({"height": 40})})}
    )
    assert get_plugin_run_config(ctx, "hit", "run_001") == {"height": 40}


def test_plugin_run_config_does_not_hide_getter_failure():
    def fail_read(run_id):
        raise OSError("run config unavailable")

    ctx = SimpleNamespace(
        config={"hit": {"runs": {"run_001": {"height": 20}}}},
        get_run_config=fail_read,
    )
    with pytest.raises(OSError, match="run config unavailable"):
        get_plugin_run_config(ctx, "hit", "run_001")


def test_diagnose_cache_checks_only_selected_run_without_mutating_files(tmp_path, monkeypatch):
    ctx = Context(storage_dir=str(tmp_path))
    for run_id in ("run_001", "run_002"):
        data_dir = Path(ctx.storage.get_run_data_dir(run_id))
        data_dir.mkdir(parents=True)
        (data_dir / f"{run_id}-orphan-unused.bin").write_bytes(b"orphan fixture")

    def snapshot():
        return {
            path.relative_to(tmp_path): (path.stat().st_size, path.stat().st_mtime_ns)
            for path in tmp_path.rglob("*")
        }

    before = snapshot()
    scanned_runs = []
    list_keys = ctx.storage.list_keys

    def record_list_keys(run_id=None):
        scanned_runs.append(run_id)
        return list_keys(run_id)

    monkeypatch.setattr(ctx.storage, "list_keys", record_list_keys)
    issues = ctx.diagnose_cache("run_001", verbose=False)

    assert scanned_runs == ["run_001"]
    assert [(issue.run_id, issue.issue_type, issue.fixable) for issue in issues] == [
        ("run_001", DiagnosticIssueType.ORPHAN_FILE, True)
    ]
    assert snapshot() == before


def test_diagnose_cache_missing_run_does_not_create_cache_directories(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    before = set(tmp_path.rglob("*"))

    assert ctx.diagnose_cache("missing", verbose=False) == []
    assert set(tmp_path.rglob("*")) == before
