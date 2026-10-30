"""Behavioral contracts for Context execution boundaries."""

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from waveform_analysis import Context
from waveform_analysis.plugins import Plugin

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("timeout", [0.05, 0, -1])
@pytest.mark.parametrize("in_worker_thread", [False, True])
def test_context_rejects_plugin_timeout_before_compute_and_save(
    tmp_path, timeout, in_worker_thread
):
    calls = []

    class TimeoutPlugin(Plugin):
        provides = "timeout_data"
        save_when = "always"
        output_dtype = np.dtype([("value", "i4")])

        def compute(self, context, run_id):
            calls.append(run_id)
            return np.array([(42,)], dtype=self.output_dtype)

    ctx = Context(storage_dir=str(tmp_path), config={"show_progress": False})
    plugin = TimeoutPlugin()
    plugin.timeout = timeout
    ctx.register(plugin)

    with pytest.raises(NotImplementedError, match="Plugin.timeout.*not supported"):
        if in_worker_thread:
            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(ctx.get_data, "run1", "timeout_data").result(timeout=5)
        else:
            ctx.get_data("run1", "timeout_data")

    assert calls == []
    assert ("run1", "timeout_data") not in ctx._results
    assert not list(tmp_path.rglob("*.bin"))


def test_context_default_timeout_computes_and_saves_normally(tmp_path):
    class DefaultTimeoutPlugin(Plugin):
        provides = "default_timeout_data"
        save_when = "always"
        output_dtype = np.dtype([("value", "i4")])

        def compute(self, context, run_id):
            return np.array([(42,)], dtype=self.output_dtype)

    ctx = Context(storage_dir=str(tmp_path), config={"show_progress": False})
    ctx.register(DefaultTimeoutPlugin)

    result = ctx.get_data("run1", "default_timeout_data")

    assert ctx.get_plugin("default_timeout_data").timeout is None
    np.testing.assert_array_equal(result["value"], [42])
    assert ("run1", "default_timeout_data") in ctx._results
    assert list(tmp_path.rglob("*.bin"))
