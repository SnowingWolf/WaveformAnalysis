from types import SimpleNamespace

import numpy as np

from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.cpu.records import RecordsPlugin


class _RunConfigFakeContext(FakeContext):
    def __init__(self, *args, run_config=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._run_config = run_config or {}

    def get_run_config(self, _run_id: str):
        return self._run_config


def test_records_plugin_builds_directly_from_raw_files(monkeypatch):
    plugin = RecordsPlugin()
    ctx = FakeContext(
        config={
            "show_progress": False,
            "daq_adapter": "vx2730",
            "baseline_samples": [0, 2],
            "records_part_size": 64,
        },
        data={"raw_files": [["f0"], ["f1"]]},
        plugins={"records": plugin},
    )

    fake_records = np.zeros(1, dtype=plugin.output_dtype)
    fake_records["timestamp"] = [100]
    fake_bundle = SimpleNamespace(
        records=fake_records,
        wave_pool=np.array([1, 2, 3, 4], dtype=np.uint16),
    )
    captured = {}

    def _fake_build(raw_files, **kwargs):
        captured["raw_files"] = raw_files
        captured["kwargs"] = kwargs
        return fake_bundle

    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.cpu.records.build_records_from_raw_files",
        _fake_build,
    )

    class _Adapter:
        def get_file_epoch(self, _path):
            return 1234

    monkeypatch.setattr("waveform_analysis.utils.formats.get_adapter", lambda _name: _Adapter())

    records = plugin.compute(ctx, "run_001")

    assert captured["raw_files"] == [["f0"], ["f1"]]
    assert captured["kwargs"]["adapter_name"] == "vx2730"
    assert captured["kwargs"]["part_size"] == 64
    assert captured["kwargs"]["baseline_samples"] == [0, 2]
    assert captured["kwargs"]["epoch_ns"] == 1234
    assert captured["kwargs"]["show_progress"] is False
    np.testing.assert_array_equal(records["timestamp"], np.array([100], dtype=np.int64))


def test_records_plugin_default_parallel_disk_config():
    plugin = RecordsPlugin()
    ctx = FakeContext(config={}, plugins={"records": plugin})

    assert ctx.get_config(plugin, "channel_workers") == 16
    assert ctx.get_config(plugin, "n_jobs") == 16
    assert ctx.get_config(plugin, "v1725_part_size") == 20_000
    assert ctx.get_config(plugin, "use_process_pool") is True
    assert ctx.get_config(plugin, "channel_executor") == "process"
    assert ctx.get_config(plugin, "keep_on_disk") is True


def test_records_plugin_passes_progress_to_v1725_builder(monkeypatch):
    plugin = RecordsPlugin()
    ctx = FakeContext(
        config={
            "show_progress": False,
            "daq_adapter": "v1725",
            "v1725_part_size": 32,
        },
        data={"raw_files": [["f0", "f1"], ["f0"]]},
        plugins={"records": plugin},
    )

    fake_records = np.zeros(1, dtype=plugin.output_dtype)
    fake_records["timestamp"] = [100]
    fake_bundle = SimpleNamespace(
        records=fake_records,
        wave_pool=np.array([1, 2, 3, 4], dtype=np.uint16),
    )
    captured = {}

    def _fake_build(file_paths, **kwargs):
        captured["file_paths"] = file_paths
        captured["kwargs"] = kwargs
        return fake_bundle

    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.cpu.records.build_records_from_v1725_files",
        _fake_build,
    )

    records = plugin.compute(ctx, "run_001")

    assert captured["file_paths"] == ["f0", "f1"]
    assert captured["kwargs"]["dt_ns"] == 4
    assert captured["kwargs"]["v1725_part_size"] == 32
    assert captured["kwargs"]["show_progress"] is False
    np.testing.assert_array_equal(records["timestamp"], np.array([100], dtype=np.int64))


def test_records_plugin_prefers_run_config_start_time_for_epoch(monkeypatch):
    plugin = RecordsPlugin()
    ctx = _RunConfigFakeContext(
        config={
            "show_progress": False,
            "daq_adapter": "vx2730",
        },
        data={"raw_files": [["f0"]]},
        plugins={"records": plugin},
        run_config={"daq": {"start_time": "2024-01-01T00:00:00Z"}},
    )

    fake_records = np.zeros(1, dtype=plugin.output_dtype)
    fake_bundle = SimpleNamespace(
        records=fake_records,
        wave_pool=np.array([1, 2], dtype=np.uint16),
    )
    captured = {}

    def _fake_build(raw_files, **kwargs):
        captured["raw_files"] = raw_files
        captured["kwargs"] = kwargs
        return fake_bundle

    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.cpu.records.build_records_from_raw_files",
        _fake_build,
    )

    class _Adapter:
        def get_file_epoch(self, _path):
            return 1234

    monkeypatch.setattr("waveform_analysis.utils.formats.get_adapter", lambda _name: _Adapter())

    plugin.compute(ctx, "run_001")

    assert captured["raw_files"] == [["f0"]]
    assert captured["kwargs"]["epoch_ns"] == 1_704_067_200_000_000_000


def test_records_plugin_falls_back_to_file_epoch_without_run_start_time(monkeypatch):
    plugin = RecordsPlugin()
    ctx = _RunConfigFakeContext(
        config={"show_progress": False, "daq_adapter": "vx2730"},
        data={"raw_files": [["f0"]]},
        plugins={"records": plugin},
        run_config={"daq": {}},
    )

    fake_records = np.zeros(1, dtype=plugin.output_dtype)
    fake_bundle = SimpleNamespace(
        records=fake_records,
        wave_pool=np.array([1, 2], dtype=np.uint16),
    )
    captured = {}

    def _fake_build(raw_files, **kwargs):
        captured["raw_files"] = raw_files
        captured["kwargs"] = kwargs
        return fake_bundle

    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.cpu.records.build_records_from_raw_files",
        _fake_build,
    )

    class _Adapter:
        def get_file_epoch(self, _path):
            return 1234

    monkeypatch.setattr("waveform_analysis.utils.formats.get_adapter", lambda _name: _Adapter())

    plugin.compute(ctx, "run_001")

    assert captured["raw_files"] == [["f0"]]
    assert captured["kwargs"]["epoch_ns"] == 1234


def test_records_plugin_uses_none_epoch_when_file_epoch_lookup_fails(monkeypatch):
    plugin = RecordsPlugin()
    ctx = FakeContext(
        config={"show_progress": False, "daq_adapter": "vx2730"},
        data={"raw_files": [["f0"]]},
        plugins={"records": plugin},
    )

    fake_records = np.zeros(1, dtype=plugin.output_dtype)
    fake_bundle = SimpleNamespace(
        records=fake_records,
        wave_pool=np.array([1, 2], dtype=np.uint16),
    )
    captured = {}

    def _fake_build(raw_files, **kwargs):
        captured["raw_files"] = raw_files
        captured["kwargs"] = kwargs
        return fake_bundle

    monkeypatch.setattr(
        "waveform_analysis.core.plugins.builtin.cpu.records.build_records_from_raw_files",
        _fake_build,
    )

    class _Adapter:
        def get_file_epoch(self, _path):
            raise FileNotFoundError("missing")

    monkeypatch.setattr("waveform_analysis.utils.formats.get_adapter", lambda _name: _Adapter())

    plugin.compute(ctx, "run_001")

    assert captured["raw_files"] == [["f0"]]
    assert captured["kwargs"]["epoch_ns"] is None
