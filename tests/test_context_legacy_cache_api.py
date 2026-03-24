from __future__ import annotations

import warnings

import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin


def test_clear_cache_compat_warns_and_clears_memory(tmp_path):
    class PluginA(Plugin):
        provides = "data_a"
        output_dtype = np.dtype([("v", "i4")])

        def compute(self, context, run_id):
            return np.array([(1,)], dtype=self.output_dtype)

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register_plugin_(PluginA())

    run_id = "run_001"
    _ = ctx.get_data(run_id, "data_a")
    assert ctx._get_data_from_memory(run_id, "data_a") is not None

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cleared = ctx.clear_cache(run_id, "data_a", clear_disk=False, verbose=False)

    assert cleared == 1
    assert ctx._get_data_from_memory(run_id, "data_a") is None
    assert any(issubclass(item.category, DeprecationWarning) for item in caught)


def test_clear_cache_compat_clears_all_registered_data(tmp_path):
    class PluginA(Plugin):
        provides = "data_a"
        output_dtype = np.dtype([("v", "i4")])

        def compute(self, context, run_id):
            return np.array([(1,)], dtype=self.output_dtype)

    class PluginB(Plugin):
        provides = "data_b"
        output_dtype = np.dtype([("v", "i4")])

        def compute(self, context, run_id):
            return np.array([(2,)], dtype=self.output_dtype)

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(PluginA(), PluginB())

    run_id = "run_all"
    _ = ctx.get_data(run_id, "data_a")
    _ = ctx.get_data(run_id, "data_b")
    assert ctx._get_data_from_memory(run_id, "data_a") is not None
    assert ctx._get_data_from_memory(run_id, "data_b") is not None

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        cleared = ctx.clear_cache(run_id, clear_disk=False, verbose=False)

    assert cleared == 2
    assert ctx._get_data_from_memory(run_id, "data_a") is None
    assert ctx._get_data_from_memory(run_id, "data_b") is None
