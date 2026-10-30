"""Cache-only batch execution must never fall through to plugin computation."""

import json
from pathlib import Path

import numpy as np
import pytest

from waveform_analysis.core.cancellation import CancellationToken, TaskCancelledException
from waveform_analysis.core.context import Context
from waveform_analysis.core.data.batch_processor import BatchProcessor
from waveform_analysis.core.plugins.core.base import Option, Plugin

pytestmark = pytest.mark.integration


class CacheOnlyDataPlugin(Plugin):
    provides = "readonly_data"
    options = {"scale": Option(default=1, type=int)}
    output_dtype = np.dtype([("value", "i4")])

    def compute(self, context, run_id, **kwargs):
        raise AssertionError("Readonly batch invoked plugin computation")


class MissingDependencyPlugin(CacheOnlyDataPlugin):
    provides = "missing_dependency_data"
    depends_on = ["unregistered_dependency"]


class RunConfigPlugin(CacheOnlyDataPlugin):
    provides = "run_config_data"
    uses_run_config = True


class RunConfigChildPlugin(CacheOnlyDataPlugin):
    provides = "run_config_child"
    depends_on = ["run_config_data"]


def _read_cached_value(context, run_id):
    data = context.get_data(run_id, "readonly_data", output="array")
    return int(data[0]["value"]), context.storage_dir, context._cache_readonly


def _seed_cache(ctx, data_name="readonly_data", memory=False):
    data = np.array([(42,)], dtype=CacheOnlyDataPlugin.output_dtype)
    ctx.storage.save_memmap(
        ctx.key_for("run_1", data_name),
        data,
        extra_metadata={"lineage": ctx.get_lineage(data_name)},
        run_id="run_1",
    )
    if memory:
        ctx._set_data("run_1", data_name, data)
    return data


def _snapshot(root):
    # Fixture files are tiny. Size/mtime and the directory inventory detect
    # mutations without hashing or scanning an external dataset.
    return {
        str(path.relative_to(root)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in [root, *root.rglob("*")]
    }


@pytest.mark.parametrize("mode", ["serial", "thread", "process"])
@pytest.mark.parametrize("method", ["process_runs", "process_func"])
@pytest.mark.parametrize("cached", [False, True])
def test_readonly_reads_original_cache_or_reports_miss(tmp_path, mode, method, cached):
    cache_root = tmp_path / "cache"
    ctx = Context(
        storage_dir=str(cache_root),
        config={"custom_config_json_path": str(tmp_path / "snapshot.json")},
    )
    ctx.register(CacheOnlyDataPlugin)
    if cached:
        _seed_cache(ctx)
    before = _snapshot(tmp_path)
    kwargs = (
        {"data_name": "readonly_data"} if method == "process_runs" else {"func": _read_cached_value}
    )

    result = getattr(BatchProcessor(ctx), method)(
        ["run_1"],
        max_workers=1 if mode == "serial" else 2,
        executor_type="process" if mode == "process" else "thread",
        storage_dir_strategy="readonly",
        show_progress=False,
        jupyter_mode=True,
        **kwargs,
    )

    assert _snapshot(tmp_path) == before
    assert ctx.storage_dir == str(cache_root)
    assert ctx._cache_readonly is False
    if cached:
        assert result["errors"] == {}
        value = result["results"]["run_1"]
        if method == "process_runs":
            assert value[0]["value"] == 42
        else:
            assert value == (42, str(cache_root), True)
    else:
        assert result["results"] == {}
        assert result["errors"]["run_1"]["type"] == "FileNotFoundError"
        assert "Readonly cache miss" in result["errors"]["run_1"]["message"]
        assert result["meta"]["run_1"]["status"] == "failed"


@pytest.mark.parametrize("mode", ["serial", "thread", "process"])
@pytest.mark.parametrize("explicit_factory", [False, True])
@pytest.mark.parametrize("cache_state", ["valid", "missing", "changed_lineage"])
def test_config_grid_preserves_readonly(tmp_path, mode, explicit_factory, cache_state):
    ctx = Context(storage_dir=str(tmp_path / "cache"))
    ctx.register(CacheOnlyDataPlugin)
    if cache_state != "missing":
        _seed_cache(ctx)
    before = _snapshot(tmp_path)
    config = {"scale": 2 if cache_state == "changed_lineage" else 1}

    result = BatchProcessor(ctx).process_runs_with_config_grid(
        ["run_1"],
        "readonly_data",
        "readonly_data",
        [config],
        max_workers=1 if mode == "serial" else 2,
        executor_type="process" if mode == "process" else "thread",
        context_factory=ctx.create_context_factory() if explicit_factory else None,
        storage_dir_strategy="readonly",
        show_progress=False,
        jupyter_mode=True,
    )

    assert _snapshot(tmp_path) == before
    assert not ctx._cache_readonly
    batch = result["results"][0]["batch"]
    if cache_state == "valid":
        assert batch["errors"] == {}
        assert batch["results"]["run_1"][0]["value"] == 42
    else:
        assert batch["results"] == {}
        assert batch["errors"]["run_1"]["type"] == "FileNotFoundError"
        assert "Readonly cache miss" in batch["errors"]["run_1"]["message"]


def test_config_grid_rejects_tmp_cache_with_readonly(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(CacheOnlyDataPlugin)
    before = _snapshot(tmp_path)
    with pytest.raises(ValueError, match="tmp_cache.*readonly"):
        BatchProcessor(ctx).process_runs_with_config_grid(
            ["run_1"],
            "readonly_data",
            "readonly_data",
            [{}],
            max_workers=1,
            storage_dir_strategy="readonly",
            tmp_cache=True,
            show_progress=False,
            jupyter_mode=True,
        )
    assert _snapshot(tmp_path) == before


def test_readonly_rejects_changed_lineage_and_missing_dependencies(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(CacheOnlyDataPlugin, MissingDependencyPlugin)
    _seed_cache(ctx, memory=True)
    ctx.set_config({"scale": 2}, plugin_name="readonly_data")
    before = _snapshot(tmp_path)
    for name in ("readonly_data", "missing_dependency_data", "unregistered_dependency"):
        result = BatchProcessor(ctx).process_runs(
            ["run_1"],
            name,
            max_workers=1,
            storage_dir_strategy="readonly",
            show_progress=False,
            jupyter_mode=True,
        )
        assert result["errors"]["run_1"]["type"] == "FileNotFoundError"
    assert _snapshot(tmp_path) == before


def test_readonly_accepts_materialized_memory_but_does_not_consume_stream(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    values = np.array([7])
    ctx._set_data("run_1", "manual_data", values)
    consumed = []

    def deferred():
        consumed.append(True)
        yield values

    ctx._set_data("run_1", "lazy_data", deferred())
    before = _snapshot(tmp_path)
    processor = BatchProcessor(ctx)
    result = processor.process_runs(
        ["run_1"],
        "manual_data",
        max_workers=1,
        storage_dir_strategy="readonly",
        show_progress=False,
        jupyter_mode=True,
    )
    assert result["results"]["run_1"] is values
    result = processor.process_runs(
        ["run_1"],
        "lazy_data",
        max_workers=1,
        storage_dir_strategy="readonly",
        show_progress=False,
        jupyter_mode=True,
    )
    assert result["errors"]["run_1"]["type"] == "FileNotFoundError"
    assert consumed == []
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("exc_type", [ValueError, TaskCancelledException, KeyboardInterrupt])
def test_readonly_restores_context_after_callback_failure(tmp_path, exc_type):
    ctx = Context(storage_dir=str(tmp_path))

    def fail(context, run_id):
        assert context._cache_readonly is True
        raise exc_type("callback interrupted")

    with pytest.raises(exc_type, match="callback interrupted"):
        BatchProcessor(ctx).process_func(
            ["run_1"],
            fail,
            max_workers=1,
            storage_dir_strategy="readonly",
            on_error="raise",
            show_progress=False,
            jupyter_mode=True,
        )
    assert ctx._cache_readonly is False


def test_readonly_preserves_mode_in_nested_clone_and_factory(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(CacheOnlyDataPlugin)
    _seed_cache(ctx)
    workers = []

    def factory():
        worker = ctx.clone()
        workers.append(worker)
        return worker

    def read_nested(context, run_id):
        clone = context.clone()
        from_spec = context.create_context_factory()()
        assert clone._cache_readonly and from_spec._cache_readonly
        return _read_cached_value(clone, run_id)[0] + _read_cached_value(from_spec, run_id)[0]

    result = BatchProcessor(ctx).process_func(
        ["run_1"],
        read_nested,
        max_workers=2,
        context_factory=factory,
        storage_dir_strategy="readonly",
        show_progress=False,
        jupyter_mode=True,
    )
    assert result["errors"] == {}
    assert result["results"]["run_1"] == 84
    assert len(workers) == 1 and workers[0] is not ctx
    assert not workers[0]._cache_readonly and not ctx._cache_readonly


def test_readonly_rejects_context_without_cache_only_support(tmp_path):
    class UnsupportedContext:
        def get_data(self, run_id, name):
            pytest.fail("Unsupported context must not be invoked")

    result = BatchProcessor(UnsupportedContext()).process_runs(
        ["run_1"],
        "data",
        max_workers=2,
        storage_dir_strategy="readonly",
        show_progress=False,
        jupyter_mode=True,
    )
    assert result["errors"]["run_1"]["type"] == "TypeError"


@pytest.mark.parametrize("mode", ["serial", "thread"])
def test_readonly_raise_keeps_cache_miss_message(tmp_path, mode):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(CacheOnlyDataPlugin)
    with pytest.raises((FileNotFoundError, RuntimeError), match="Readonly cache miss"):
        BatchProcessor(ctx).process_runs(
            ["run_1"],
            "readonly_data",
            max_workers=1 if mode == "serial" else 2,
            storage_dir_strategy="readonly",
            on_error="raise",
            show_progress=False,
            jupyter_mode=True,
        )
    assert not ctx._cache_readonly


def test_readonly_precancelled_serial_batch_has_no_side_effects(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(CacheOnlyDataPlugin)
    token = CancellationToken()
    token.cancel()
    before = _snapshot(tmp_path)
    result = BatchProcessor(ctx).process_runs(
        ["run_1"],
        "readonly_data",
        max_workers=1,
        storage_dir_strategy="readonly",
        cancellation_token=token,
        show_progress=False,
        jupyter_mode=True,
    )
    assert result["meta"]["run_1"]["status"] == "skipped"
    assert not ctx._cache_readonly
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("freshness", ["valid", "changed", "missing", "changed_memory"])
def test_readonly_checks_run_config_freshness_without_rewriting_state(tmp_path, freshness):
    config_path = tmp_path / "run_config.json"
    config_path.write_text('{"calibration": 1}')
    ctx = Context(
        storage_dir=str(tmp_path / "cache"),
        config={"run_config_path": str(config_path)},
    )
    ctx.register(RunConfigPlugin, RunConfigChildPlugin)
    ctx._config_domain.maybe_invalidate_run_config_cache("run_1")
    _seed_cache(ctx, "run_config_child", memory=freshness == "changed_memory")
    state_path = Path(ctx._config_domain.get_run_config_hash_state_path("run_1"))
    if freshness in {"changed", "changed_memory"}:
        config_path.write_text('{"calibration": 2}')
    if freshness == "missing":
        state_path.unlink()
    if freshness == "changed_memory":
        current_hash, _ = ctx._config_domain.compute_run_config_hash("run_1")
        state = json.loads(state_path.read_text())
        state["run_config_hash"] = current_hash
        state_path.write_text(json.dumps(state))
        # A different Context has refreshed the disk cache; this Context still
        # holds the old memory array and run-level hash.
        ctx.storage.save_memmap(
            ctx.key_for("run_1", "run_config_child"),
            np.array([(84,)], dtype=CacheOnlyDataPlugin.output_dtype),
            extra_metadata={"lineage": ctx.get_lineage("run_config_child")},
            run_id="run_1",
        )
    before = _snapshot(tmp_path)
    processor = BatchProcessor(ctx)
    for _ in range(2):
        result = processor.process_runs(
            ["run_1"],
            "run_config_child",
            max_workers=1,
            storage_dir_strategy="readonly",
            show_progress=False,
            jupyter_mode=True,
        )
        if freshness in {"valid", "changed_memory"}:
            assert result["errors"] == {}
            expected = 84 if freshness == "changed_memory" else 42
            assert result["results"]["run_1"][0]["value"] == expected
        else:
            assert result["errors"]["run_1"]["type"] == "FileNotFoundError"
            assert "run_config" in result["errors"]["run_1"]["message"]
    assert _snapshot(tmp_path) == before


def test_readonly_run_config_memory_only_result_is_not_trusted(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(RunConfigPlugin)
    ctx._config_domain.maybe_invalidate_run_config_cache("run_1")
    _seed_cache(ctx, "run_config_data", memory=True)
    ctx.storage.delete(ctx.key_for("run_1", "run_config_data"), "run_1")
    before = _snapshot(tmp_path)
    result = BatchProcessor(ctx).process_runs(
        ["run_1"],
        "run_config_data",
        max_workers=1,
        storage_dir_strategy="readonly",
        show_progress=False,
        jupyter_mode=True,
    )
    assert result["errors"]["run_1"]["type"] == "FileNotFoundError"
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("cleanup_raises", [False, True])
def test_stream_close_cleans_before_unlock_and_releases_after_cleanup_failure(
    tmp_path, monkeypatch, cleanup_raises
):
    ctx = Context(storage_dir=str(tmp_path), config={"show_progress": False})
    ctx.register(CacheOnlyDataPlugin)
    key = ctx.key_for("run_1", "readonly_data")
    bin_path, _, _ = ctx.storage._get_paths(key, "run_1")
    release = ctx.storage._release_lock
    observed = []

    def checked_release(fd, lock_path):
        observed.append(not Path(bin_path + ".tmp").exists())
        release(fd, lock_path)

    monkeypatch.setattr(ctx.storage, "_release_lock", checked_release)
    chunks = iter([np.array([(1,)], dtype=CacheOnlyDataPlugin.output_dtype)])
    stream = ctx._execution_domain.wrap_generator_to_save(
        "run_1",
        "readonly_data",
        chunks,
        CacheOnlyDataPlugin.output_dtype,
    )
    next(stream)
    assert Path(bin_path + ".tmp").exists()
    if cleanup_raises:

        def fail_cleanup(path):
            raise PermissionError("cleanup unavailable")

        monkeypatch.setattr("waveform_analysis.core.context_execution.os.remove", fail_cleanup)
    stream.close()
    assert observed == [not cleanup_raises]
