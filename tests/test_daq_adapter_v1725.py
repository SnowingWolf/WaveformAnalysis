"""V1725 reader tests."""

from pathlib import Path

import numpy as np

from tests.daq_adapter_helpers import make_v1725_single_wave_blob
from waveform_analysis.core.processing.records_builder import build_records_from_v1725_files
from waveform_analysis.utils.formats import RawTimestampMode, V1725Reader, get_adapter


class TestV1725Reader:
    def test_v1725_spec_marks_sample_index_timestamps(self):
        assert get_adapter("v1725").format_spec.raw_timestamp_mode == RawTimestampMode.SAMPLE_INDEX

    def test_iter_waves_extracts_board_from_bseg_filename(self, tmp_path: Path):
        raw = tmp_path / "test_raw_b7_seg0.bin"
        raw.write_bytes(make_v1725_single_wave_blob(channel=1, timestamp=77, baseline=555))

        waves = list(V1725Reader().iter_waves([raw]))

        assert len(waves) == 1
        assert waves[0].board == 7
        assert waves[0].channel == 1
        assert waves[0].timestamp == 77
        assert waves[0].baseline == 555

    def test_iter_waves_legacy_name_defaults_board_zero(self, tmp_path: Path):
        raw = tmp_path / "CH1_0.bin"
        raw.write_bytes(make_v1725_single_wave_blob(channel=1, timestamp=88, baseline=444))

        waves = list(V1725Reader().iter_waves([raw]))

        assert len(waves) == 1
        assert waves[0].board == 0

    def test_build_records_from_v1725_files_keeps_board_from_filename(self, tmp_path: Path):
        raw0 = tmp_path / "test_raw_b3_seg0.bin"
        raw1 = tmp_path / "test_raw_b4_seg1.bin"
        raw0.write_bytes(make_v1725_single_wave_blob(channel=0, timestamp=10, baseline=100))
        raw1.write_bytes(make_v1725_single_wave_blob(channel=1, timestamp=20, baseline=200))

        bundle = build_records_from_v1725_files([str(raw0), str(raw1)], dt_ns=4)

        assert len(bundle.records) == 2
        np.testing.assert_array_equal(bundle.records["board"], np.array([3, 4], dtype=np.int16))
        np.testing.assert_array_equal(bundle.records["channel"], np.array([0, 1], dtype=np.int16))
