# -*- coding: utf-8 -*-
import numpy as np

from waveform_analysis.core.plugins.builtin.cpu.filtering import FilteredWaveformsPlugin
from waveform_analysis.core.plugins.builtin.cpu.standard import (
    HitFinderPlugin,
    StWaveformsPlugin,
    WaveformsPlugin,
)
from waveform_analysis.core.processing.processor import PEAK_DTYPE, create_record_dtype
from waveform_analysis.utils.formats import (
    ColumnMapping,
    DAQAdapter,
    FLAT_LAYOUT,
    FormatSpec,
    GenericCSVReader,
    TimestampUnit,
    register_adapter,
    unregister_adapter,
)


class DummyContext:
    def __init__(self, config, data=None):
        self.config = config
        self._data = data or {}

    def get_config(self, plugin, name):
        provides = plugin.provides
        if provides in self.config and isinstance(self.config[provides], dict):
            if name in self.config[provides]:
                return self.config[provides][name]
        namespaced_key = f"{provides}.{name}"
        if namespaced_key in self.config:
            return self.config[namespaced_key]
        if name in self.config:
            return self.config[name]
        return plugin.options[name].default

    def get_data(self, _run_id, name):
        return self._data[name]

    def get_lineage(self, _name):
        return {}


def _register_test_adapter(name, expected_samples, sampling_rate_hz=1e9):
    spec = FormatSpec(
        name=f"{name}_spec",
        columns=ColumnMapping(),
        timestamp_unit=TimestampUnit.NANOSECONDS,
        expected_samples=expected_samples,
        sampling_rate_hz=sampling_rate_hz,
    )
    adapter = DAQAdapter(
        name=name,
        format_reader=GenericCSVReader(spec),
        directory_layout=FLAT_LAYOUT,
    )
    register_adapter(adapter)


def test_hitfinder_empty_dtype():
    dtype = create_record_dtype(5)
    st_waveforms = [np.zeros(0, dtype=dtype)]
    ctx = DummyContext({}, {"st_waveforms": st_waveforms})
    plugin = HitFinderPlugin()
    hits = plugin.compute(ctx, "run_001", threshold=1.0)
    assert len(hits) == 1
    assert hits[0].dtype == np.dtype(PEAK_DTYPE)


def test_waveforms_plugin_prefers_plugin_n_channels(monkeypatch):
    raw_files = [["f0"], ["f1"], ["f2"], ["f3"]]
    called = {}

    def fake_get_waveforms(raw_filess, **_kwargs):
        called["raw_filess_len"] = len(raw_filess)
        return [np.zeros((0, 0)) for _ in raw_filess]

    monkeypatch.setattr("waveform_analysis.utils.loader.get_waveforms", fake_get_waveforms)

    plugin = WaveformsPlugin()
    config = {
        "n_channels": 4,
        "waveforms": {"n_channels": 1, "start_channel_slice": 0},
        "show_progress": False,
    }
    ctx = DummyContext(config, {"raw_files": raw_files})

    plugin.compute(ctx, "run_001")

    assert called["raw_filess_len"] == 1


def test_st_waveforms_lineage_uses_adapter_dtype():
    adapter_name = "test_adapter_lineage"
    _register_test_adapter(adapter_name, expected_samples=16)
    try:
        plugin = StWaveformsPlugin()
        config = {"st_waveforms": {"daq_adapter": adapter_name}}
        ctx = DummyContext(config)
        lineage = plugin.get_lineage(ctx)
        wave_field = next(item for item in lineage["dtype"] if item[0] == "wave")
        assert wave_field[2] == (16,)
    finally:
        unregister_adapter(adapter_name)


def test_filtered_waveforms_fs_auto_from_adapter():
    adapter_name = "test_adapter_filter"
    _register_test_adapter(adapter_name, expected_samples=64, sampling_rate_hz=1e9)
    try:
        dtype = create_record_dtype(64)
        st_waveforms = [np.zeros(1, dtype=dtype)]
        st_waveforms[0]["wave"][0] = np.linspace(0, 1, 64)
        config = {
            "filtered_waveforms": {
                "filter_type": "BW",
                "lowcut": 0.1,
                "highcut": 0.4,
                "daq_adapter": adapter_name,
            }
        }
        ctx = DummyContext(config, {"st_waveforms": st_waveforms})
        plugin = FilteredWaveformsPlugin()

        result = plugin.compute(ctx, "run_001")

        assert isinstance(result, list)
        assert result[0].shape[0] == 1
    finally:
        unregister_adapter(adapter_name)
