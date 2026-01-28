import os
import shutil
import threading
import time

import numpy as np
import pytest
import matplotlib
matplotlib.use('Agg')

from waveform_analysis.core.context import Context
from waveform_analysis.core.cancellation import CancellationToken
from waveform_analysis.core.data.batch_processor import BatchProcessor
from waveform_analysis.core.execution.timeout import get_timeout_manager, with_timeout
from waveform_analysis.core.plugins.core.base import Option, Plugin


class MockPlugin(Plugin):
    provides = "mock_data"
    depends_on = []
    output_dtype = np.dtype([("time", "f8"), ("value", "f8")])

    def compute(self, context, run_id, **kwargs):
        return np.array([(1.0, 10.0), (2.0, 20.0)], dtype=self.output_dtype)


class DependentPlugin(Plugin):
    provides = "dependent_data"
    depends_on = ["mock_data"]
    output_dtype = np.dtype([("time", "f8"), ("sum", "f8")])

    def compute(self, context, run_id, **kwargs):
        mock_data = context.get_data(run_id, "mock_data")
        return np.array([(d["time"], d["value"] + 1) for d in mock_data], dtype=self.output_dtype)


@pytest.fixture
def context(tmp_path):
    storage_dir = str(tmp_path / "strax_data")
    ctx = Context(storage_dir=storage_dir)
    ctx.register(MockPlugin)
    ctx.register(DependentPlugin)
    return ctx


def test_context_basic_get(context):
    """Test basic data retrieval from context."""
    run_id = "test_run"
    data = context.get_data(run_id, "mock_data")
    assert len(data) == 2
    assert data[0]["value"] == 10.0
    assert data[1]["value"] == 20.0


def test_context_dependency(context):
    """Test data retrieval with dependencies."""
    run_id = "test_run"
    data = context.get_data(run_id, "dependent_data")
    assert len(data) == 2
    assert data[0]["sum"] == 11.0
    assert data[1]["sum"] == 21.0


def test_context_config(tmp_path):
    """Test context configuration and plugin options."""

    class ConfigurablePlugin(Plugin):
        provides = "config_data"
        options = {"multiplier": Option(default=1, type=int)}
        output_dtype = np.dtype([("val", "i4")])

        def compute(self, context, run_id, **kwargs):
            multiplier = context.get_config(self, "multiplier")
            return np.array([(multiplier,)], dtype=self.output_dtype)

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(ConfigurablePlugin)

    # Default config
    data = ctx.get_data("run1", "config_data")
    assert data[0]["val"] == 1

    # Override config
    ctx.set_config({"multiplier": 10})
    ctx.clear_config_cache()
    # Use a completely different run_id to avoid any memory cache issues
    data = ctx.get_data("run_new", "config_data")
    assert data[0]["val"] == 10


def test_context_circular_dependency(tmp_path):
    """Test detection of circular dependencies."""

    class PluginA(Plugin):
        provides = "data_a"
        depends_on = ["data_b"]

        def compute(self, context, run_id):
            return np.array([1])

    class PluginB(Plugin):
        provides = "data_b"
        depends_on = ["data_a"]

        def compute(self, context, run_id):
            return np.array([2])

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PluginA, PluginB)

    with pytest.raises(RuntimeError, match="Circular dependency detected"):
        ctx.get_data("run1", "data_a")


def test_context_missing_dependency(tmp_path):
    """Test behavior when a dependency is missing."""

    class PluginA(Plugin):
        provides = "data_a"
        depends_on = ["missing_data"]

        def compute(self, context, run_id):
            return np.array([1])

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PluginA)

    with pytest.raises(ValueError, match="Missing dependency"):
        ctx.get_data("run1", "data_a")


def test_context_streaming_plugin(tmp_path):
    """Test streaming plugins and generator saving."""

    class StreamPlugin(Plugin):
        provides = "stream_data"
        output_kind = "stream"
        output_dtype = np.dtype([("val", "i4")])
        save_when = "always"

        def compute(self, context, run_id):
            for i in range(5):
                yield np.array([(i,)], dtype=self.output_dtype)

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(StreamPlugin)

    # First call: executes plugin and saves
    data_gen = ctx.get_data("run1", "stream_data")
    results = list(data_gen)
    assert len(results) == 5
    assert results[0]["val"] == 0
    assert results[4]["val"] == 4

    # Second call: should load from disk (memmap)
    # Clear memory cache to force disk reload
    del ctx._results[("run1", "stream_data")]

    data_cached = ctx.get_data("run1", "stream_data")
    # For streams, it should now return a memmap-backed array if it was saved as static,
    # or a new generator if it's still a stream.
    # In our case, save_stream saves it as a contiguous file.
    assert len(data_cached) == 5
    assert data_cached[0]["val"] == 0


def test_context_visualization_smoke(tmp_path):
    """Smoke test for visualization methods."""
    ctx = Context(storage_dir=str(tmp_path))

    class SimplePlugin(Plugin):
        provides = "data"

        def compute(self, context, run_id):
            return np.array([1])

    ctx.register(SimplePlugin)

    # Should not crash
    ctx.show_config()
    ctx.plot_lineage("data", kind="labview")
    ctx.plot_lineage("data", kind="mermaid")


def test_context_namespaced_config(tmp_path):
    """Test namespaced configuration."""

    class PluginA(Plugin):
        provides = "plugin_a"
        options = {"opt": Option(default=0)}

        def compute(self, context, run_id):
            return np.array([context.get_config(self, "opt")])

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PluginA)

    # Test "plugin_a.opt" style
    ctx.set_config({"plugin_a.opt": 42})
    assert ctx.get_data("run1", "plugin_a")[0] == 42

    # Test nested dict style
    ctx.set_config({"plugin_a": {"opt": 100}})
    ctx.clear_config_cache()
    assert ctx.get_data("run2", "plugin_a")[0] == 100


def test_context_registration_variants(tmp_path):
    """Test different ways to register plugins."""
    ctx = Context(storage_dir=str(tmp_path))

    # Register by class
    ctx.register(MockPlugin)
    assert "mock_data" in ctx._plugins

    # Register by instance
    ctx.register(DependentPlugin())
    assert "dependent_data" in ctx._plugins


def test_context_key_for(context):
    """Test lineage key generation."""
    key1 = context.key_for("test_run", "mock_data")
    key2 = context.key_for("test_run", "mock_data")
    assert key1 == key2

    key3 = context.key_for("other_run", "mock_data")
    assert key1 != key3


def test_context_is_stored(context):
    """Test checking if data is stored."""
    run_id = "test_run"
    # Context uses storage.exists
    key = context.key_for(run_id, "mock_data")
    assert not context.storage.exists(key)

    # Force save by setting save_when
    context._plugins["mock_data"].save_when = "always"
    context.get_data(run_id, "mock_data")

    assert context.storage.exists(key)


def test_context_cache_order_for_dependency(tmp_path, capsys):
    """Ensure cached dependencies are loaded before downstream plugins run."""
    calls = {"base": 0, "derived": 0}

    class BasePlugin(Plugin):
        provides = "base"
        save_when = "always"
        output_dtype = np.dtype([("val", "i4")])

        def compute(self, context, run_id, **kwargs):
            calls["base"] += 1
            return np.array([(1,)], dtype=self.output_dtype)

    class DerivedPlugin(Plugin):
        provides = "derived"
        depends_on = ["base"]
        output_dtype = np.dtype([("val", "i4")])

        def compute(self, context, run_id, **kwargs):
            calls["derived"] += 1
            data = context.get_data(run_id, "base")
            return np.array([(int(data[0]["val"]) + 1,)], dtype=self.output_dtype)

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(BasePlugin, DerivedPlugin)

    run_id = "run1"
    ctx.get_data(run_id, "derived")
    assert calls == {"base": 1, "derived": 1}

    ctx.clear_cache_for(run_id, clear_disk=False, verbose=False)
    capsys.readouterr()

    ctx.get_data(run_id, "derived")
    out = capsys.readouterr().out

    assert "[cache] Loaded 'base'" in out
    assert "[+] Running plugin: derived" in out
    assert out.index("[cache] Loaded 'base'") < out.index("[+] Running plugin: derived")
    assert "[+] Running plugin: base" not in out
    assert calls == {"base": 1, "derived": 2}


def test_context_minimal_dag_happy_path(tmp_path):
    """Validate minimal DAG execution order and cache consistency."""
    order = []
    dtype = np.dtype([("val", "i4")])

    class PluginA(Plugin):
        provides = "data_a"
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            order.append("A")
            return np.array([(1,), (2,)], dtype=self.output_dtype)

    class PluginB(Plugin):
        provides = "data_b"
        depends_on = ["data_a"]
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            order.append("B")
            data_a = context.get_data(run_id, "data_a")
            return np.array([(int(x["val"]) + 10,) for x in data_a], dtype=self.output_dtype)

    class PluginC(Plugin):
        provides = "data_c"
        depends_on = ["data_b"]
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            order.append("C")
            data_b = context.get_data(run_id, "data_b")
            return np.array([(int(x["val"]) * 2,) for x in data_b], dtype=self.output_dtype)

    ctx_no_cache = Context(storage_dir=str(tmp_path / "no_cache"))
    ctx_no_cache.register(PluginA, PluginB, PluginC)
    result_no_cache = ctx_no_cache.get_data("run1", "data_c")

    assert order == ["A", "B", "C"]
    assert result_no_cache.dtype == dtype
    assert result_no_cache.shape == (2,)
    assert int(result_no_cache[0]["val"]) == 22
    assert int(result_no_cache[1]["val"]) == 24

    order.clear()
    ctx_cache = Context(storage_dir=str(tmp_path / "with_cache"))
    ctx_cache.register(PluginA, PluginB, PluginC)
    for plugin in ctx_cache._plugins.values():
        plugin.save_when = "always"

    ctx_cache.get_data("run1", "data_c")
    ctx_cache.clear_cache_for("run1", clear_disk=False, verbose=False)
    result_cached = ctx_cache.get_data("run1", "data_c")

    assert np.array_equal(result_no_cache, result_cached)


def test_context_dag_failure_propagation(tmp_path):
    """Ensure failures stop downstream plugins and avoid partial cache writes."""
    calls = {"A": 0, "B": 0, "C": 0}
    dtype = np.dtype([("val", "i4")])

    class PluginA(Plugin):
        provides = "data_a"
        save_when = "always"
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            calls["A"] += 1
            return np.array([(1,)], dtype=self.output_dtype)

    class PluginB(Plugin):
        provides = "data_b"
        depends_on = ["data_a"]
        save_when = "always"
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            calls["B"] += 1
            raise ValueError("boom")

    class PluginC(Plugin):
        provides = "data_c"
        depends_on = ["data_b"]
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            calls["C"] += 1
            return np.array([(3,)], dtype=self.output_dtype)

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PluginA, PluginB, PluginC)

    with pytest.raises(RuntimeError, match="Plugin 'data_b' failed"):
        ctx.get_data("run1", "data_c")

    assert calls == {"A": 1, "B": 1, "C": 0}

    key_a = ctx.key_for("run1", "data_a")
    key_b = ctx.key_for("run1", "data_b")
    key_c = ctx.key_for("run1", "data_c")

    assert ctx.storage.exists(key_a)
    assert not ctx.storage.exists(key_b)
    assert not ctx.storage.exists(key_c)


def test_batch_processor_cancellation_skips_remaining(tmp_path):
    """Cancellation should stop remaining runs without partial cache output."""
    dtype = np.dtype([("val", "i4")])
    cancellation_token = CancellationToken()

    class SlowPlugin(Plugin):
        provides = "slow_data"
        save_when = "always"
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            time.sleep(0.05)
            return np.array([(1,)], dtype=self.output_dtype)

    def cancel_soon():
        time.sleep(0.01)
        cancellation_token.cancel()

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(SlowPlugin)
    processor = BatchProcessor(ctx)

    thread = threading.Thread(target=cancel_soon)
    thread.start()

    result = processor.process_runs(
        run_ids=["run1", "run2"],
        data_name="slow_data",
        max_workers=1,
        show_progress=False,
        cancellation_token=cancellation_token,
        jupyter_mode=True,
    )

    thread.join()

    assert result["meta"]["run1"]["status"] == "success"
    assert result["meta"]["run2"]["status"] == "skipped"
    assert ctx.storage.exists(ctx.key_for("run1", "slow_data"))
    assert not ctx.storage.exists(ctx.key_for("run2", "slow_data"))


def test_context_timeout_does_not_cache(tmp_path, monkeypatch):
    """Timeouts should surface as failures and avoid cache writes."""
    dtype = np.dtype([("val", "i4")])
    manager = get_timeout_manager()
    manager.reset_stats()
    monkeypatch.setattr(manager, "is_unix", False)

    class TimeoutPlugin(Plugin):
        provides = "timeout_data"
        save_when = "always"
        output_dtype = dtype

        @with_timeout(timeout=0.01)
        def compute(self, context, run_id, **kwargs):
            time.sleep(0.05)
            return np.array([(1,)], dtype=self.output_dtype)

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(TimeoutPlugin)

    with pytest.raises(RuntimeError, match="Plugin 'timeout_data' failed"):
        ctx.get_data("run1", "timeout_data")

    key = ctx.key_for("run1", "timeout_data")
    assert not ctx.storage.exists(key)
    assert manager.get_timeout_stats().get("compute", 0) >= 1
