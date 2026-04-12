from types import SimpleNamespace

import numpy as np

from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.cpu.records import RecordsPlugin


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
