import logging
from types import SimpleNamespace

import numpy as np

from waveform_analysis.core.plugins.builtin.cpu.waveforms import (
    WaveformStructConfig,
    _structure_waveforms_streaming,
)
from waveform_analysis.core.processing.dtypes import create_record_dtype
from waveform_analysis.core.processing.records_builder import (
    build_records_from_st_waveforms_sharded,
)


class _FakeReader:
    def __init__(self, raw_arr: np.ndarray):
        self._raw_arr = raw_arr

    def read_files_streaming(
        self,
        file_paths,
        output_dtype,
        output_path,
        structurizer,
        show_progress,
    ):
        output = np.memmap(output_path, dtype=output_dtype, mode="w+", shape=(len(self._raw_arr),))
        n_written = structurizer(self._raw_arr, output, 0)
        output.flush()
        return np.memmap(output_path, dtype=output_dtype, mode="r+", shape=(n_written,))


class _FakeAdapter:
    def __init__(self, raw_arr: np.ndarray):
        self.format_reader = _FakeReader(raw_arr)


def test_structure_waveforms_streaming_works_without_time_field(monkeypatch):
    raw_arr = np.array(
        [
            [0, 3, 1000, 0, 0, 0, 0, 10, 11, 12, 13],
            [0, 3, 2000, 0, 0, 0, 0, 20, 21, 22, 23],
        ],
        dtype=np.int64,
    )

    monkeypatch.setattr(
        "waveform_analysis.utils.formats.get_adapter",
        lambda name: _FakeAdapter(raw_arr),
    )

    context = SimpleNamespace(logger=logging.getLogger(__name__))
    config = WaveformStructConfig.default_vx2730()
    config.wave_length = 4
    output = _structure_waveforms_streaming(
        context=context,
        run_id="run_001",
        raw_files=[["fake.csv"]],
        config=config,
        baseline_samples=None,
        upstream_baselines=None,
        show_progress=False,
    )

    assert "time" not in output.dtype.names
    assert np.array_equal(output["event_length"], np.array([4, 4], dtype=np.int32))
    assert np.array_equal(
        output["wave"], np.array([[10, 11, 12, 13], [20, 21, 22, 23]], dtype=np.int16)
    )


def test_build_records_from_st_waveforms_sharded_accepts_none_part_size():
    st_waveforms = np.zeros(1, dtype=create_record_dtype(4))
    st_waveforms["timestamp"] = 123
    st_waveforms["board"] = 0
    st_waveforms["channel"] = 1
    st_waveforms["baseline"] = 42.0
    st_waveforms["event_length"] = 4
    st_waveforms["wave"] = np.array([[1, 2, 3, 4]], dtype=np.int16)

    bundle = build_records_from_st_waveforms_sharded(
        st_waveforms,
        part_size=None,
        default_dt_ns=2,
    )

    assert len(bundle.records) == 1
    assert int(bundle.records["event_length"][0]) == 4
    assert float(bundle.records["baseline"][0]) == 42.0
