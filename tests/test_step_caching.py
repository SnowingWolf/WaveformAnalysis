import os
import pickle
from pathlib import Path

from tests.utils import make_csv
from waveform_analysis import WaveformDataset


def test_memory_cache(tmp_path: Path):
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "cache_run"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    from tests.utils import make_simple_csv

    make_simple_csv(raw_dir, 6, 0, 1000)

    ds = WaveformDataset(char="cache_run", data_root=str(daq_root), use_daq_scan=True)

    # enable caching for structure_waveforms to store st_waveforms and pair_len
    ds.set_step_cache("structure_waveforms", enabled=True, attrs=["st_waveforms", "pair_len"])

    # run first time: should execute and create cache
    ds.load_raw_data()
    ds.extract_waveforms()
    ds.structure_waveforms()
    assert ds.get_cached_result("structure_waveforms") is not None

    # monkeypatch class method to raise, but keep chainable decorator so cache-loading logic runs
    def bad_struct(self, verbose=True):
        raise RuntimeError("should not be called")

    orig = WaveformDataset.structure_waveforms
    WaveformDataset.structure_waveforms = WaveformDataset.chainable_step(bad_struct)
    try:
        ds.structure_waveforms()
    finally:
        WaveformDataset.structure_waveforms = orig

    # still should have st_waveforms restored
    assert ds.st_waveforms is not None


def test_persistent_cache(tmp_path: Path):
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "cache_run2"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    from tests.utils import make_simple_csv

    make_simple_csv(raw_dir, 6, 0, 2000)

    ds = WaveformDataset(char="cache_run2", data_root=str(daq_root), use_daq_scan=True)
    cache_file = tmp_path / "struct_cache.pkl"
    ds.set_step_cache(
        "structure_waveforms", enabled=True, attrs=["st_waveforms", "pair_len"], persist_path=str(cache_file)
    )

    ds.load_raw_data()
    ds.extract_waveforms()
    ds.structure_waveforms()

    assert cache_file.exists()

    # create new dataset instance and ensure loading from disk cache works
    ds2 = WaveformDataset(char="cache_run2", data_root=str(daq_root), use_daq_scan=True)
    ds2.set_step_cache(
        "structure_waveforms", enabled=True, attrs=["st_waveforms", "pair_len"], persist_path=str(cache_file)
    )
    ds2.load_raw_data()
    # calling structure_waveforms should load cache instead of executing
    ds2.structure_waveforms()
    assert ds2.st_waveforms is not None
