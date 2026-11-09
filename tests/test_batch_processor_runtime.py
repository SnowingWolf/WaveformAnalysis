"""BatchProcessor cancellation and meta tests."""

from pathlib import Path
import threading
import time

import pytest

from tests.batch_processor_helpers import SimpleDataPlugin, SlowPlugin
from waveform_analysis.core.cancellation import CancellationToken
from waveform_analysis.core.context import Context
from waveform_analysis.core.data.batch_processor import BatchProcessor

pytestmark = pytest.mark.integration


def _read_simple_value(context, run_id):
    return int(context.get_data(run_id, "simple_data")[0]["value"])


@pytest.mark.parametrize("method", ["process_runs", "process_func"])
def test_serial_uses_factory_for_each_run_and_retry(tmp_path, method):
    base = Context(storage_dir=str(tmp_path / "base"))
    worker = Context(storage_dir=str(tmp_path / "worker"))
    worker.register(SimpleDataPlugin)
    calls = []

    def factory():
        calls.append(True)
        if len(calls) == 1:
            raise ValueError("transient factory failure")
        return worker.clone()

    kwargs = (
        {"data_name": "simple_data"} if method == "process_runs" else {"func": _read_simple_value}
    )
    result = getattr(BatchProcessor(base), method)(
        ["run_1", "run_3"],
        max_workers=1,
        context_factory=factory,
        retries=1,
        retry_on=(ValueError,),
        show_progress=False,
        jupyter_mode=True,
        **kwargs,
    )

    assert result["errors"] == {}
    assert len(calls) == 3
    assert result["meta"]["run_1"]["attempts"] == 2
    assert result["meta"]["run_3"]["attempts"] == 1
    for run_id, expected in (("run_1", 1), ("run_3", 3)):
        value = result["results"][run_id]
        assert (value[0]["value"] if method == "process_runs" else value) == expected


@pytest.mark.parametrize("method", ["process_runs", "process_func"])
@pytest.mark.parametrize("on_error", ["continue", "stop", "raise"])
def test_serial_factory_failure_uses_error_policy(tmp_path, method, on_error):
    def factory():
        raise ValueError("factory unavailable")

    kwargs = (
        {"data_name": "simple_data"} if method == "process_runs" else {"func": _read_simple_value}
    )
    processor = BatchProcessor(Context(storage_dir=str(tmp_path)))
    options = dict(
        max_workers=1,
        context_factory=factory,
        on_error=on_error,
        show_progress=False,
        jupyter_mode=True,
        **kwargs,
    )
    if on_error == "raise":
        with pytest.raises(ValueError, match="factory unavailable"):
            getattr(processor, method)(["run_1", "run_2"], **options)
        return

    result = getattr(processor, method)(["run_1", "run_2"], **options)
    assert result["results"] == {}
    assert result["errors"]["run_1"]["type"] == "ValueError"
    assert result["errors"]["run_1"]["message"] == "factory unavailable"
    assert result["meta"]["run_1"]["status"] == "failed"
    assert result["meta"]["run_2"]["status"] == ("skipped" if on_error == "stop" else "failed")


@pytest.mark.parametrize("method", ["process_runs", "process_func"])
def test_serial_factory_preserves_per_worker_cache_isolation(tmp_path, method):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(SimpleDataPlugin)
    workers = []

    def factory():
        worker = ctx.clone()
        workers.append(worker)
        return worker

    kwargs = (
        {"data_name": "simple_data"} if method == "process_runs" else {"func": _read_simple_value}
    )
    result = getattr(BatchProcessor(ctx), method)(
        ["run_1", "run_2"],
        max_workers=1,
        context_factory=factory,
        storage_dir_strategy="per_worker",
        show_progress=False,
        jupyter_mode=True,
        **kwargs,
    )

    assert result["errors"] == {}
    assert len(workers) == 2
    cache_dirs = [worker.storage_dir for worker in workers]
    assert len(set(cache_dirs)) == 2
    assert all(cache_dir != str(tmp_path) for cache_dir in cache_dirs)
    assert all(not Path(cache_dir).exists() for cache_dir in cache_dirs)
    assert ctx.storage_dir == str(tmp_path)


class TestBatchProcessorCancellation:
    def test_cancellation_skips_remaining(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SlowPlugin)
        processor = BatchProcessor(ctx)

        cancellation_token = CancellationToken()

        def cancel_soon():
            time.sleep(0.02)
            cancellation_token.cancel()

        thread = threading.Thread(target=cancel_soon)
        thread.start()

        result = processor.process_runs(
            run_ids=["run_1", "run_2", "run_3"],
            data_name="slow_data",
            max_workers=1,
            show_progress=False,
            cancellation_token=cancellation_token,
            jupyter_mode=True,
        )

        thread.join()

        assert result["meta"]["run_1"]["status"] == "success"
        skipped_count = sum(1 for m in result["meta"].values() if m["status"] == "skipped")
        assert skipped_count >= 1


class TestBatchProcessorMeta:
    def test_meta_contains_elapsed_time(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        result = processor.process_runs(
            run_ids=["run_1"],
            data_name="simple_data",
            max_workers=1,
            show_progress=False,
            jupyter_mode=True,
        )

        assert "elapsed" in result["meta"]["run_1"]
        assert result["meta"]["run_1"]["elapsed"] >= 0

    def test_meta_contains_attempts(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        result = processor.process_runs(
            run_ids=["run_1"],
            data_name="simple_data",
            max_workers=1,
            show_progress=False,
            jupyter_mode=True,
        )

        assert "attempts" in result["meta"]["run_1"]
        assert result["meta"]["run_1"]["attempts"] == 1
