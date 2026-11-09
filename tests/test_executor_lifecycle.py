"""Executor lifecycle regressions, with deadlocks bounded by a child-process watchdog."""

from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import Mock

import pytest

from waveform_analysis.core.execution import manager as execution


def _shutdown_registry_probe(action):
    manager = execution.get_executor_manager()
    executor = manager.get_executor("registry-probe", max_workers=1)
    worker_ready = threading.Event()
    shutdown_started = threading.Event()
    original_shutdown = executor.shutdown

    def inspect_registry():
        worker_ready.set()
        assert shutdown_started.wait(3), "shutdown never started"
        return manager.list_executors()

    def shutdown(*, wait):
        shutdown_started.set()
        original_shutdown(wait=wait)

    executor.shutdown = shutdown
    future = executor.submit(inspect_registry)
    assert worker_ready.wait(3), "worker never started"
    if action == "shutdown_all":
        manager.get_executor("other-registry-probe", max_workers=1)
    print("worker ready", flush=True)
    if action == "release":
        manager.release_executor("registry-probe", max_workers=1)
    elif action == "shutdown":
        manager.shutdown_executor("registry-probe", max_workers=1)
    else:
        manager.shutdown_all()
    assert future.result(timeout=1) == {}
    assert manager.list_executors() == {}


def _concurrent_release_probe():
    manager = execution.get_executor_manager()
    executor = manager.get_executor("concurrent-release", max_workers=1)
    shutdown_started = threading.Event()
    allow_shutdown = threading.Event()
    original_shutdown = executor.shutdown
    shutdown_calls = []

    def shutdown(*, wait):
        shutdown_calls.append(wait)
        shutdown_started.set()
        assert allow_shutdown.wait(3), "shutdown gate never opened"
        original_shutdown(wait=wait)

    executor.shutdown = shutdown
    first_release = threading.Thread(
        target=manager.release_executor, args=("concurrent-release",), kwargs={"max_workers": 1}
    )
    second_release = threading.Thread(
        target=manager.release_executor, args=("concurrent-release",), kwargs={"max_workers": 1}
    )
    first_release.start()
    assert shutdown_started.wait(3), "first release never reached shutdown"
    try:
        second_release.start()
        second_release.join(timeout=1)
        assert not second_release.is_alive(), "concurrent release blocked on shutdown"
        replacement = manager.get_executor("concurrent-release", max_workers=1)
        assert replacement is not executor
    finally:
        allow_shutdown.set()
        first_release.join(timeout=3)
        second_release.join(timeout=3)
    assert not first_release.is_alive()
    assert shutdown_calls == [True]
    assert replacement.submit(lambda: 42).result(timeout=1) == 42
    manager.release_executor("concurrent-release", max_workers=1)
    assert manager.list_executors() == {}


def _run_probe(probe, *args):
    code = (
        "import faulthandler; faulthandler.dump_traceback_later(5); "
        f"from tests.test_executor_lifecycle import {probe}; {probe}(*{args!r})"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"executor child process deadlocked: {exc.stdout!r}\n{exc.stderr!r}")
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("action", ["release", "shutdown", "shutdown_all"])
def test_shutdown_allows_worker_registry_access(action):
    _run_probe("_shutdown_registry_probe", action)


def test_concurrent_release_preserves_replacement():
    _run_probe("_concurrent_release_probe")


@pytest.fixture
def manager():
    manager = execution.get_executor_manager()
    manager.shutdown_all()
    yield manager
    manager.shutdown_all()


def test_shared_references_close_after_last_release(manager):
    with manager.executor("shared", max_workers=1, wait_on_exit=True) as first:
        with manager.executor("shared", max_workers=1, wait_on_exit=True) as second:
            assert first is second
            assert manager.list_executors()["shared_thread_1"]["ref_count"] == 2
        assert manager.list_executors()["shared_thread_1"]["ref_count"] == 1
        assert first.submit(lambda: 42).result(timeout=1) == 42
    assert manager.list_executors() == {}
    with pytest.raises(RuntimeError, match="shutdown"):
        first.submit(lambda: None)


@pytest.mark.parametrize("shutdown_all", [False, True])
def test_old_context_does_not_release_replacement(manager, shutdown_all):
    with manager.executor("replaced", max_workers=1, wait_on_exit=True) as first:
        if shutdown_all:
            manager.shutdown_all()
        else:
            manager.shutdown_executor("replaced", max_workers=1)
        second = manager.get_executor("replaced", max_workers=1)
        assert first is not second
    assert manager.list_executors()["replaced_thread_1"]["ref_count"] == 1
    assert second.submit(lambda: 42).result(timeout=1) == 42
    manager.release_executor("replaced", max_workers=1)
    assert manager.list_executors() == {}


def test_nonreused_executor_does_not_replace_shared_reference(manager):
    shared = manager.get_executor("separate", max_workers=1)
    with manager.executor("separate", max_workers=1, reuse=False) as separate:
        assert separate is not shared
        assert separate.submit(lambda: 1).result(timeout=1) == 1
    assert manager.list_executors()["separate_thread_1"]["ref_count"] == 1
    assert shared.submit(lambda: 42).result(timeout=1) == 42
    manager.release_executor("separate", max_workers=1)


@pytest.mark.parametrize("parallel", [execution.parallel_map, execution.parallel_apply])
def test_empty_input_defaults(parallel):
    assert parallel(lambda *args: None, []) == []


@pytest.mark.parametrize("parallel", [execution.parallel_map, execution.parallel_apply])
@pytest.mark.parametrize("max_workers", [None, 2])
@pytest.mark.parametrize("executor_type", ["thread", "process"])
def test_empty_input_does_not_create_pool(monkeypatch, parallel, max_workers, executor_type):
    create_executor = Mock(side_effect=AssertionError("empty input must not create a pool"))
    monkeypatch.setattr(execution._manager, "_create_executor", create_executor)
    assert (
        parallel(lambda *args: None, [], max_workers=max_workers, executor_type=executor_type) == []
    )
    create_executor.assert_not_called()


@pytest.mark.parametrize("parallel", [execution.parallel_map, execution.parallel_apply])
@pytest.mark.parametrize("max_workers", [None, 2])
def test_empty_input_skips_load_balancer(monkeypatch, parallel, max_workers):
    balancer = Mock()
    balancer.get_optimal_workers.side_effect = AssertionError("no tasks to balance")
    monkeypatch.setattr(execution._manager, "_load_balancing_enabled", True)
    monkeypatch.setattr(execution._manager, "_load_balancer", balancer)
    assert parallel(lambda *args: None, [], max_workers=max_workers) == []
    balancer.get_optimal_workers.assert_not_called()
    balancer.record_task_completion.assert_not_called()


@pytest.mark.parametrize("parallel", [execution.parallel_map, execution.parallel_apply])
@pytest.mark.parametrize("configuration", ["function", "context"])
def test_empty_input_creates_no_progress_bar(monkeypatch, parallel, configuration):
    from waveform_analysis.core.foundation import progress

    tracker = Mock()
    monkeypatch.setattr(progress, "get_global_tracker", lambda: tracker)

    def func(*args):
        pytest.fail("empty input must not call the function")

    if configuration == "function":
        execution.parallel_progress()(func)
        assert parallel(func, []) == []
    else:
        with execution.ParallelProgressConfig():
            assert parallel(func, []) == []
    tracker.create_bar.assert_not_called()
    tracker.close.assert_not_called()


@pytest.mark.parametrize("parallel", [execution.parallel_map, execution.parallel_apply])
def test_empty_input_does_not_call_progress_callback(parallel):
    callback = Mock()
    assert parallel(lambda *args: None, [], progress_callback=callback) == []
    callback.assert_not_called()
