# -*- coding: utf-8 -*-

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu.events import (
    EventFramePlugin,
    EventsPlugin,
)
from waveform_analysis.core.processing.records_builder import EVENTS_DTYPE, RecordsBundle


class _FakeContext:
    def __init__(self, config=None):
        self.config = config or {}
        self._results = {}
        self._plugins = {"events": EventsPlugin()}

    def get_plugin(self, name):
        return self._plugins[name]

    def get_config(self, plugin, name):
        if name in self.config:
            return self.config[name]
        scoped = f"{plugin.provides}.{name}"
        if scoped in self.config:
            return self.config[scoped]
        option = plugin.options.get(name) if hasattr(plugin, "options") else None
        return option.default if option is not None else None

    def key_for(self, run_id, data_name):
        return f"{run_id}-{data_name}-key"

    def _set_data(self, run_id, name, data):
        self._results[(run_id, name)] = data


def _seed_events_bundle(ctx, run_id):
    records = np.zeros(2, dtype=EVENTS_DTYPE)
    records["timestamp"] = [100, 200]
    records["pid"] = 0
    records["channel"] = [0, 1]
    records["baseline"] = [10.0, 5.0]
    records["event_id"] = [0, 1]
    records["dt"] = [1, 1]
    records["trigger_type"] = 0
    records["flags"] = 0
    records["wave_offset"] = [0, 3]
    records["event_length"] = [3, 2]
    records["time"] = [0, 0]

    wave_pool = np.array([8, 9, 10, 1, 2], dtype=np.uint16)
    bundle = RecordsBundle(records=records, wave_pool=wave_pool)
    cache_key = f"_events_bundle-{ctx.key_for(run_id, 'events')}"
    ctx._results[(run_id, cache_key)] = bundle


def test_event_frame_plugin_basic_features():
    run_id = "run_001"
    ctx = _FakeContext(config={"peaks_range": (0, None), "charge_range": (0, None)})
    _seed_events_bundle(ctx, run_id)

    plugin = EventFramePlugin()
    df = plugin.compute(ctx, run_id)

    assert list(df["timestamp"]) == [100, 200]
    assert list(df["channel"]) == [0, 1]
    assert list(df["event_id"]) == [0, 1]

    assert np.allclose(df["peak"].to_numpy(), np.array([2.0, 1.0]))
    assert np.allclose(df["charge"].to_numpy(), np.array([3.0, 7.0]))
