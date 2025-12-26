from pathlib import Path

import pytest

from tests.utils import make_csv
from waveform_analysis import WaveformDataset


def test_chain_continues_on_error(tmp_path: Path):
    # prepare run with minimal files
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "chain_run"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    make_csv(raw_dir, 6, 0, 1000, 1100, n_samples=10)

    ds = WaveformDataset(char="chain_run", data_root=str(daq_root), use_daq_scan=True)

    # 替换类方法为出错版本并用 chainable_step 包装
    def _bad_structure(self, verbose: bool = True):
        raise RuntimeError("intentional structure error")

    orig = WaveformDataset.structure_waveforms
    WaveformDataset.structure_waveforms = WaveformDataset.chainable_step(_bad_structure)
    try:
        # run chain: load_raw_data then failing structure_waveforms then build_waveform_features
        res = ds.load_raw_data().structure_waveforms().build_waveform_features()
    finally:
        WaveformDataset.structure_waveforms = orig

    assert res is ds

    errors = ds.get_step_errors()
    # the recorded error key may be the wrapper name; just assert some structure-related error exists
    assert any("structure" in k for k in errors.keys())
    assert any("intentional structure error" in v for v in errors.values())

    # clear errors and ensure clear works
    ds.clear_step_errors()
    assert ds.get_step_errors() == {}


def test_fail_on_error_behavior(tmp_path: Path):
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "chain_run2"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    from tests.utils import make_csv

    make_csv(raw_dir, 6, 0, 2000, 2100, n_samples=10)

    ds = WaveformDataset(char="chain_run2", data_root=str(daq_root), use_daq_scan=True)

    # 替换类方法为出错版本并用 chainable_step 包装
    def _bad_build_dataframe(self, verbose: bool = True):
        raise ValueError("build failed")

    orig = WaveformDataset.build_dataframe
    WaveformDataset.build_dataframe = WaveformDataset.chainable_step(_bad_build_dataframe)
    ds.set_raise_on_error(True)
    try:
        ds.load_raw_data()
        with pytest.raises(ValueError):
            ds.build_dataframe()
    finally:
        WaveformDataset.build_dataframe = orig
