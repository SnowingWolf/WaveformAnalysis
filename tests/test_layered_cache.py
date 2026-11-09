"""Integration checks for immutable published cache layers.

All records and values here are synthetic; no detector data is read.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Option, Plugin

RUN = "synthetic_run"
DTYPE = np.dtype([("value", "i4")])
CALLS = []


class SyntheticSource(Plugin):
    provides = "synthetic_source"
    options = {"source_scale": Option(default=1, type=int)}
    output_dtype = DTYPE
    uses_run_config = True
    version = "1.0.0"

    def compute(self, context, run_id, **kwargs):
        CALLS.append(self.provides)
        scale = context.get_config(self, "source_scale")
        return np.array([(2 * scale,), (4 * scale,)], dtype=self.output_dtype)


class SyntheticRecords(Plugin):
    provides = "records"
    depends_on = ["synthetic_source"]
    output_dtype = DTYPE
    save_when = "always"
    version = "1.0.0"

    def compute(self, context, run_id, **kwargs):
        CALLS.append(self.provides)
        return context.get_data(run_id, "synthetic_source").copy()


class SyntheticWavePool(Plugin):
    provides = "wave_pool"
    depends_on = ["records"]
    output_dtype = DTYPE
    save_when = "always"
    version = "1.0.0"

    def compute(self, context, run_id, **kwargs):
        CALLS.append(self.provides)
        return context.get_data(run_id, "records").copy()


class SyntheticAnalysis(Plugin):
    provides = "synthetic_analysis"
    depends_on = ["wave_pool"]
    options = {"analysis_scale": Option(default=1, type=int)}
    output_dtype = DTYPE
    save_when = "always"
    version = "1.0.0"

    def compute(self, context, run_id, **kwargs):
        CALLS.append(self.provides)
        result = context.get_data(run_id, "wave_pool").copy()
        result["value"] *= context.get_config(self, "analysis_scale")
        return result


def context(path, config_path, *, base=None, scale=1):
    kwargs = {"base": str(base)} if base is not None else {}
    ctx = Context(
        storage_dir=str(path),
        config={
            "run_config_path": str(config_path),
            "analysis_scale": scale,
            "show_progress": False,
        },
        **kwargs,
    )
    ctx.register(SyntheticSource, SyntheticRecords, SyntheticWavePool, SyntheticAnalysis)
    return ctx


@pytest.fixture
def published(tmp_path):
    CALLS.clear()
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        json.dumps({"calibration": {"gain_adc_per_pe": {"0:0": 1}}, "plugins": {}}),
        encoding="utf-8",
    )
    producer = context(tmp_path / "producer", config_path)
    producer.get_data(RUN, "wave_pool", output="array")
    base = tmp_path / "published"
    producer.publish(RUN, targets=["records", "wave_pool"], destination=str(base))
    CALLS.clear()
    return producer, base, config_path


def inventory(root):
    return {
        str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in [root, *root.rglob("*")]
    }


def bin_for(root, name):
    matches = list(root.rglob(f"*-{name}-*.bin"))
    assert len(matches) == 1, matches
    return matches[0]


def test_shared_readonly_mmap_and_independent_private_results(tmp_path, published):
    _, base, config_path = published
    before = inventory(base)
    first = context(tmp_path / "private_a", config_path, base=base, scale=2)
    second = context(tmp_path / "private_b", config_path, base=base, scale=3)
    a = first.get_data(RUN, "wave_pool", output="array")
    b = second.get_data(RUN, "wave_pool", output="array")
    assert isinstance(a, np.memmap) and isinstance(b, np.memmap)
    assert not a.flags.writeable and not b.flags.writeable
    assert Path(a.filename).samefile(Path(b.filename))
    np.testing.assert_array_equal(first.get_data(RUN, "synthetic_analysis")["value"], [4, 8])
    np.testing.assert_array_equal(second.get_data(RUN, "synthetic_analysis")["value"], [6, 12])
    assert CALLS == ["synthetic_analysis", "synthetic_analysis"]
    assert bin_for(tmp_path / "private_a", "synthetic_analysis").is_file()
    assert bin_for(tmp_path / "private_b", "synthetic_analysis").is_file()
    first.clear_cache_for(RUN, verbose=False)
    assert inventory(base) == before
    np.testing.assert_array_equal(second.get_data(RUN, "wave_pool")["value"], [2, 4])


@pytest.mark.parametrize("change", ["config", "version", "dtype", "dependency"])
def test_changed_frozen_identity_fails_before_private_or_memory_hit(tmp_path, published, change):
    _, base, config_path = published
    private = tmp_path / "private"
    original = context(private, config_path, base=base)
    original.get_data(RUN, "synthetic_analysis")
    consumer = context(private, config_path, base=base)
    if change == "config":
        consumer.set_config({"source_scale": 2})
    else:
        source = consumer._plugins["synthetic_source"]
        if change == "version":
            source.version = "2.0.0"
        elif change == "dtype":
            source.output_dtype = np.dtype([("value", "i8")])
        else:
            consumer._plugins["records"].depends_on = []
        consumer._invalidate_planning_caches()
    consumer._set_data(RUN, "synthetic_analysis", np.array([(999,)], dtype=DTYPE))
    CALLS.clear()
    with pytest.raises((ValueError, FileNotFoundError)):
        consumer.get_data(RUN, "synthetic_analysis")
    assert CALLS == []


@pytest.mark.parametrize("damage", ["missing", "truncated"])
@pytest.mark.parametrize("warm", ["memory", "private"])
def test_broken_published_payload_fails_before_cached_target(tmp_path, published, damage, warm):
    _, base, config_path = published
    private = tmp_path / "private"
    consumer = context(private, config_path, base=base)
    consumer.get_data(RUN, "synthetic_analysis")
    if warm == "private":
        consumer = context(private, config_path, base=base)
    payload = bin_for(base, "wave_pool")
    payload.chmod(
        0o600
    )  # Deliberately simulate an external owner corrupting an immutable snapshot.
    if damage == "missing":
        payload.unlink()
    else:
        with payload.open("r+b") as handle:
            handle.truncate(1)
        payload.chmod(0o444)
    CALLS.clear()
    with pytest.raises((ValueError, FileNotFoundError)):
        consumer.get_data(RUN, "synthetic_analysis")
    assert CALLS == []


def test_wrong_run_and_direct_frozen_ancestor_never_compute(tmp_path, published):
    _, base, config_path = published
    consumer = context(tmp_path / "private", config_path, base=base)
    with pytest.raises((ValueError, FileNotFoundError)):
        consumer.get_data("another_run", "synthetic_analysis")
    with pytest.raises((ValueError, FileNotFoundError)):
        consumer.get_data(RUN, "synthetic_source")
    with pytest.raises(RuntimeError, match="Cannot execute frozen"):
        consumer._execute_single_plugin(
            "synthetic_source", RUN, "synthetic_source", {}, None, None, skip_cache_check=True
        )
    assert CALLS == []


def test_incomplete_publish_is_atomic_and_existing_destination_is_not_overwritten(
    tmp_path, published
):
    producer, base, _ = published
    before = inventory(base)
    with pytest.raises(FileExistsError):
        producer.publish(RUN, targets=["records"], destination=str(base))
    assert inventory(base) == before
    producer.clear_cache_for(RUN, data_name="wave_pool", verbose=False)
    incomplete = tmp_path / "incomplete"
    with pytest.raises((FileNotFoundError, ValueError)):
        producer.publish(RUN, targets=["wave_pool"], destination=str(incomplete))
    assert not incomplete.exists()
    assert not list(tmp_path.glob(".published-cache-*"))


def test_first_snapshot_survives_producer_mutation_and_next_snapshot_reuses_base(
    tmp_path, published
):
    producer, base, config_path = published
    original = bin_for(base, "wave_pool")
    producer_payload = bin_for(tmp_path / "producer", "wave_pool")
    assert not original.samefile(producer_payload)
    with producer_payload.open("r+b") as handle:
        handle.write(b"\x00" * producer_payload.stat().st_size)
    consumer = context(tmp_path / "private", config_path, base=base)
    np.testing.assert_array_equal(consumer.get_data(RUN, "wave_pool")["value"], [2, 4])
    next_base = tmp_path / "published_next"
    consumer.publish(RUN, targets=["wave_pool"], destination=str(next_base))
    assert original.samefile(bin_for(next_base, "wave_pool"))


@pytest.mark.parametrize("change", ["changed", "missing"])
def test_changed_or_missing_run_config_fails_even_with_warm_private_target(
    tmp_path, published, change
):
    _, base, config_path = published
    private = tmp_path / "private"
    consumer = context(private, config_path, base=base)
    consumer.get_data(RUN, "synthetic_analysis")
    if change == "changed":
        config_path.write_text(
            json.dumps({"calibration": {"gain_adc_per_pe": {"0:0": 2}}, "plugins": {}}),
            encoding="utf-8",
        )
    else:
        config_path.unlink()
    CALLS.clear()
    with pytest.raises((ValueError, FileNotFoundError)):
        consumer.get_data(RUN, "synthetic_analysis")
    assert CALLS == []


@pytest.mark.parametrize("worker_type", ["clone", "factory"])
def test_worker_context_keeps_published_base_and_guards(tmp_path, published, worker_type):
    _, base, config_path = published
    parent = context(tmp_path / "private", config_path, base=base)
    worker = parent.clone() if worker_type == "clone" else parent.create_context_factory()()
    result = worker.get_data(RUN, "wave_pool")
    assert isinstance(result, np.memmap) and not result.flags.writeable
    assert Path(result.filename).samefile(bin_for(base, "wave_pool"))
    with pytest.raises((ValueError, FileNotFoundError)):
        worker.get_data(RUN, "synthetic_source")
    assert CALLS == []


def test_builtin_records_view_with_published_synthetic_v1725_cache(tmp_path):
    from waveform_analysis.core.data.records_view import records_view
    from waveform_analysis.core.plugins import profiles
    from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE

    config_path = tmp_path / "run_config.json"
    config_path.write_text('{"calibration": {}, "plugins": {}}', encoding="utf-8")
    config = {
        "daq_adapter": "v1725",
        "input_source": "raw_files",
        "run_config_path": str(config_path),
        "show_progress": False,
    }
    producer = Context(storage_dir=str(tmp_path / "builtin_producer"), config=config)
    producer.register(*profiles.cpu_default())
    producer._config_domain.maybe_invalidate_run_config_cache(RUN)
    records = np.zeros(1, dtype=RECORDS_DTYPE)
    records["record_id"] = 7
    records["event_length"] = 3
    records["wave_offset"] = 0
    waves = np.array([3, 5, 8], dtype=np.uint16)
    for name, data in (("records", records), ("wave_pool", waves)):
        producer.storage.save_memmap(
            producer.key_for(RUN, name),
            data,
            run_id=RUN,
            extra_metadata={"lineage": producer.get_lineage(name)},
        )
    base = tmp_path / "builtin_published"
    producer.publish(RUN, targets=["records", "wave_pool"], destination=str(base))
    consumer = Context(storage_dir=str(tmp_path / "builtin_private"), config=config, base=str(base))
    consumer.register(*profiles.cpu_default())
    view = records_view(consumer, RUN)
    np.testing.assert_array_equal(view.waves(7), waves)
    assert isinstance(view.records, np.memmap) and isinstance(view.wave_pool, np.memmap)
    assert not view.records.flags.writeable and not view.wave_pool.flags.writeable


def test_published_metadata_tampering_fails_before_warm_result(tmp_path, published):
    _, base, config_path = published
    consumer = context(tmp_path / "private", config_path, base=base)
    consumer.get_data(RUN, "synthetic_analysis")
    meta_path = bin_for(base, "wave_pool").with_suffix(".json")
    meta_path.chmod(0o600)
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["itemsize"] += 1
    meta_path.write_text(json.dumps(metadata), encoding="utf-8")
    meta_path.chmod(0o444)
    CALLS.clear()
    with pytest.raises(ValueError, match="metadata mismatch"):
        consumer.get_data(RUN, "synthetic_analysis")
    assert CALLS == []


def test_publish_holds_all_target_locks_while_copying(tmp_path, published, monkeypatch):
    """A cooperating writer for target two cannot alter it after target one is copied."""
    import fcntl
    import os
    import shutil
    import threading

    producer, _, config_path = published
    record_key = producer.key_for(RUN, "records")
    wave_key = producer.key_for(RUN, "wave_pool")
    record_path, _, _ = producer.storage._get_paths(record_key, RUN)
    _, _, wave_lock = producer.storage._get_paths(wave_key, RUN)
    original_copy = shutil.copyfile
    original_acquire = producer.storage._acquire_lock
    attempting = threading.Event()
    done = threading.Event()
    errors = []
    workers = []
    observed = []

    def acquire(lock_path, *args, **kwargs):
        if threading.current_thread().name == "competing-writer":
            attempting.set()
        return original_acquire(lock_path, *args, **kwargs)

    def writer():
        try:
            producer.storage.save_memmap(
                wave_key,
                np.array([(20,), (40,)], dtype=DTYPE),
                run_id=RUN,
                extra_metadata={"lineage": producer.get_lineage("wave_pool")},
            )
        except Exception as exc:
            errors.append(exc)
        finally:
            done.set()

    def copy_and_interleave(src, dst, *args, **kwargs):
        result = original_copy(src, dst, *args, **kwargs)
        if str(src) == record_path and not observed:
            worker = threading.Thread(target=writer, name="competing-writer")
            workers.append(worker)
            worker.start()
            assert attempting.wait(5), "writer did not reach the lock"
            fd = os.open(wave_lock, os.O_RDWR)
            try:
                with pytest.raises(BlockingIOError):
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            finally:
                os.close(fd)
            assert not done.is_set()
            observed.append(True)
        return result

    monkeypatch.setattr(producer.storage, "_acquire_lock", acquire)
    monkeypatch.setattr(shutil, "copyfile", copy_and_interleave)
    destination = tmp_path / "concurrent_snapshot"
    producer.publish(RUN, targets=["records", "wave_pool"], destination=str(destination))
    assert observed == [True]
    workers[0].join(timeout=5)
    assert done.is_set() and not errors
    consumer = context(tmp_path / "consumer_after_race", config_path, base=destination)
    np.testing.assert_array_equal(consumer.get_data(RUN, "wave_pool")["value"], [2, 4])
    np.testing.assert_array_equal(producer.storage.load_memmap(wave_key, RUN)["value"], [20, 40])


@pytest.mark.parametrize("invalid", ["mismatch", "missing"])
def test_request_rejects_invalid_published_base(tmp_path, published, invalid):
    _, base, config_path = published
    consumer = context(tmp_path / "preview_private", config_path, base=base)
    if invalid == "mismatch":
        consumer.set_config({"source_scale": 2})
        error = ValueError
    else:
        bin_for(base, "wave_pool").unlink()
        error = FileNotFoundError
    CALLS.clear()
    with pytest.raises(error):
        consumer.get_data(RUN, "synthetic_analysis")
    assert CALLS == []


def test_config_snapshot_cannot_write_inside_published_base(tmp_path, published):
    _, base, config_path = published
    consumer = context(tmp_path / "config_private", config_path, base=base)
    consumer.config["custom_config_json_path"] = str(base / "nested" / "snapshot.json")
    before = inventory(base)
    with pytest.raises(ValueError, match="custom_config_json_path.*published base"):
        consumer.get_data(RUN, "synthetic_analysis")
    assert inventory(base) == before


def test_stats_log_cannot_write_inside_published_base(tmp_path, published):
    _, base, _ = published
    before = inventory(base)
    with pytest.raises(ValueError, match="stats_log_file.*published base"):
        Context(
            storage_dir=str(tmp_path / "stats_private"),
            base=str(base),
            stats_mode="basic",
            stats_log_file=str(base / "nested" / "stats.log"),
        )
    assert inventory(base) == before


def test_cross_device_publish_copies_inherited_readonly_payload(tmp_path, published, monkeypatch):
    import errno
    import os

    _, base, config_path = published
    consumer = context(tmp_path / "private_for_exdev", config_path, base=base)

    def cross_device(*args, **kwargs):
        raise OSError(errno.EXDEV, "cross-device link")

    monkeypatch.setattr(os, "link", cross_device)
    destination = tmp_path / "cross_device_snapshot"
    consumer.publish(RUN, targets="wave_pool", destination=str(destination))
    original = bin_for(base, "wave_pool")
    copied = bin_for(destination, "wave_pool")
    assert not original.samefile(copied)
    assert copied.stat().st_mode & 0o777 == 0o444
    reader = context(tmp_path / "cross_device_private", config_path, base=destination)
    np.testing.assert_array_equal(reader.get_data(RUN, "wave_pool")["value"], [2, 4])


class SyntheticObjectAnalysis(Plugin):
    provides = "synthetic_object_analysis"
    depends_on = ["wave_pool"]
    output_dtype = np.dtype("O")
    version = "1.0.0"

    def compute(self, context, run_id, **kwargs):
        wave_pool = context.get_data(run_id, "wave_pool")
        return np.array([{"sum": int(wave_pool["value"].sum())}], dtype=object)


class SyntheticAncestorAnalysis(Plugin):
    provides = "synthetic_ancestor_analysis"
    depends_on = ["synthetic_source"]
    output_dtype = DTYPE
    version = "1.0.0"

    def compute(self, context, run_id, **kwargs):
        raise AssertionError("Frozen ancestor must not be computed")


def test_private_object_output_can_depend_on_published_wave_pool(tmp_path, published):
    _, base, config_path = published
    consumer = context(tmp_path / "private_object", config_path, base=base)
    consumer.register(SyntheticObjectAnalysis)
    result = consumer.get_data(RUN, "synthetic_object_analysis")
    assert result.dtype == np.dtype("O")
    assert result.tolist() == [{"sum": 6}]
    assert not list((tmp_path / "private_object").rglob("*.bin"))


def test_request_rejects_unmaterialized_frozen_ancestor(tmp_path, published):
    _, base, config_path = published
    consumer = context(tmp_path / "private_preview", config_path, base=base)
    consumer.register(SyntheticAncestorAnalysis)
    np.testing.assert_array_equal(consumer.get_data(RUN, "wave_pool")["value"], [2, 4])
    for target, error in (
        ("synthetic_source", FileNotFoundError),
        ("synthetic_ancestor_analysis", RuntimeError),
    ):
        with pytest.raises(error, match="(?i)(frozen|published)"):
            consumer.get_data(RUN, target)
    assert CALLS == []
