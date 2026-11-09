"""Run-aware calls use one storage contract without changing existing keys."""

from types import SimpleNamespace

import numpy as np
import pytest

from waveform_analysis.analysis.cache_queries import list_channel_cache_keys
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin
from waveform_analysis.core.storage.backends import SQLiteBackend
from waveform_analysis.core.storage.memmap import MemmapStorage


@pytest.fixture(params=["memmap", "sqlite"])
def backend(request, tmp_path):
    if request.param == "memmap":
        storage = MemmapStorage(str(tmp_path / "storage"))
    else:
        storage = SQLiteBackend(str(tmp_path / "storage.sqlite"))
    yield storage
    if request.param == "sqlite":
        storage.close()


def test_backend_accepts_run_keyword_for_array_metadata_and_stream(backend):
    run_id = "run-with-dash"
    key = f"{run_id}-data-hash"
    data = np.array([1, 2], dtype="i8")
    backend.save_memmap(key, data, extra_metadata={"tag": "array"}, run_id=run_id)
    assert backend.exists(key, run_id=run_id)
    np.testing.assert_array_equal(backend.load_memmap(key, run_id=run_id), data)
    assert backend.get_metadata(key, run_id=run_id)["tag"] == "array"
    assert backend.get_size(key, run_id=run_id) > 0
    assert key in backend.list_keys(run_id=run_id)

    stream_key = f"{run_id}-stream-hash"
    assert backend.save_stream(stream_key, iter([data]), data.dtype, run_id=run_id) == 2
    np.testing.assert_array_equal(backend.load_memmap(stream_key, run_id=run_id), data)
    backend.save_metadata(key, {"tag": "updated"}, run_id=run_id)
    assert backend.get_metadata(key, run_id=run_id) == {"tag": "updated"}
    backend.delete(key, run_id=run_id)
    assert not backend.exists(key, run_id=run_id)


def test_sqlite_run_filter_is_literal_and_retains_all_keys_without_run(tmp_path):
    backend = SQLiteBackend(str(tmp_path / "storage.sqlite"))
    keys = ["run_%1-data-a", "run_X1-data-b", "other-data-c"]
    for key in keys:
        backend.save_memmap(key, np.array([1]))
    assert set(backend.list_keys()) == set(keys)
    assert backend.list_keys(run_id="run_%1") == [keys[0]]
    backend.save_metadata("run_%1-metadata-only", {"tag": True}, run_id="run_%1")
    assert backend.list_keys(run_id="run_%1") == [keys[0]]
    backend.close()


def test_cache_query_fallback_passes_run_and_propagates_errors():
    calls = []

    def list_keys(*, run_id):
        calls.append(run_id)
        return ["run-data-hash_ch10", "run-data-hash_ch2"]

    storage = SimpleNamespace(list_keys=list_keys)
    ctx = SimpleNamespace(
        _plugins={"data": object()},
        key_for=lambda run_id, data_name: "run-data-hash",
        _get_storage_for_data_name=lambda name: storage,
    )
    assert list_channel_cache_keys(ctx, "run", "data") == [
        "run-data-hash_ch2",
        "run-data-hash_ch10",
    ]
    assert calls == ["run"]

    def broken_list_keys(*, run_id):
        raise OSError("list failed")

    storage.list_keys = broken_list_keys
    with pytest.raises(OSError, match="list failed"):
        list_channel_cache_keys(ctx, "run", "data")


def test_memmap_context_stream_uses_complete_run_id(tmp_path):
    class Source(Plugin):
        provides = "stream_source"
        output_dtype = np.dtype("i8")

        def compute(self, context, run_id):
            yield np.array([1, 2], dtype=self.output_dtype)

    ctx = Context(storage_dir=str(tmp_path), config={"show_progress": False})
    ctx.register(Source())
    run_id = "run-with-dash"
    key = ctx.key_for(run_id, "stream_source")
    chunks = iter([np.array([1, 2], dtype="i8")])
    assert (
        len(
            list(
                ctx._execution_domain.wrap_generator_to_save(
                    run_id, "stream_source", chunks, np.dtype("i8")
                )
            )
        )
        == 1
    )
    assert (tmp_path / run_id / "_cache" / f"{key}.bin").is_file()
    assert ctx.storage.exists(key, run_id=run_id)
    assert not (tmp_path / "run" / "_cache" / f"{key}.bin").exists()


@pytest.mark.parametrize("historical", [False, True])
def test_old_backend_signature_fails_on_real_cache_lookup(tmp_path, historical):
    class Source(Plugin):
        provides = "cached_source"
        output_dtype = np.dtype("i8")
        save_when = "always"

        def compute(self, context, run_id):
            raise AssertionError("cache lookup must not silently fall back to recomputation")

    class LegacyBackend:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

        def get_metadata(self, key):
            return self.wrapped.get_metadata(key)

    storage = MemmapStorage(str(tmp_path))
    ctx = Context(storage_backend=LegacyBackend(storage), config={"show_progress": False})
    ctx.register(Source())
    run_id = "run-legacy"
    key = ctx.key_for(run_id, "cached_source")
    if historical:
        key = f"{run_id}-cached_source-oldhash"
    storage.save_memmap(
        key,
        np.array([42], dtype="i8"),
        extra_metadata={"lineage": ctx.get_lineage("cached_source")},
        run_id=run_id,
    )
    with pytest.raises(TypeError, match="run_id"):
        ctx.get_data(run_id, "cached_source")


def test_sqlite_context_reloads_two_runs_without_recomputing(tmp_path):
    calls = []

    class Source(Plugin):
        provides = "sqlite_source"
        output_dtype = np.dtype("i8")
        save_when = "always"

        def compute(self, context, run_id):
            calls.append(run_id)
            return np.array([1 if run_id == "run-a" else 2], dtype=self.output_dtype)

    storage = SQLiteBackend(str(tmp_path / "storage.sqlite"))
    writer = Context(storage_backend=storage, config={"show_progress": False})
    writer.register(Source())
    np.testing.assert_array_equal(writer.get_data("run-a", "sqlite_source"), [1])
    np.testing.assert_array_equal(writer.get_data("run-b", "sqlite_source"), [2])
    assert len(storage.list_keys(run_id="run-a")) == 1
    assert len(storage.list_keys(run_id="run-b")) == 1
    reader = Context(storage_backend=storage, config={"show_progress": False})
    reader.register(Source())
    np.testing.assert_array_equal(reader.get_data("run-a", "sqlite_source"), [1])
    np.testing.assert_array_equal(reader.get_data("run-b", "sqlite_source"), [2])
    assert calls == ["run-a", "run-b"]
    storage.close()
