import os
import pickle
import time
from pathlib import Path

import pytest

from waveform_analysis import WaveformDataset


def test_persistent_cache_invalidates_on_file_change(tmp_path: Path, make_csv_fn):
    # Set up a DAQ-like run structure
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "inv_run"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    # create a CSV file for channel 6
    make_csv_fn(raw_dir, 6, 0, 1000, 2000)

    cache_path = tmp_path / "load_cache.pkl"

    ds = WaveformDataset(char="inv_run", data_root=str(daq_root), use_daq_scan=True)
    # enable cache for load_raw_data, watching raw_files attribute
    ds.set_step_cache(
        "load_raw_data", enabled=True, attrs=["raw_files"], persist_path=str(cache_path), watch_attrs=["raw_files"]
    )

    # first run should create the cache file with signature
    ds.load_raw_data(verbose=False)
    assert cache_path.exists()

    with open(cache_path, "rb") as f:
        data = pickle.load(f)

    assert "__watch_sig__" in data
    sig_before = data["__watch_sig__"]
    assert sig_before is not None

    # modify the raw file to change its mtime/size
    # find the created file path
    ch_files = ds.raw_files[6]
    assert ch_files
    fp = ch_files[0]
    # append a newline to change size
    with open(fp, "a") as f:
        f.write("\n")
    # ensure filesystem mtime changes
    time.sleep(0.01)

    # create a fresh dataset instance (simulating a new process)
    ds2 = WaveformDataset(char="inv_run", data_root=str(daq_root), use_daq_scan=True)
    ds2.set_step_cache(
        "load_raw_data", enabled=True, attrs=["raw_files"], persist_path=str(cache_path), watch_attrs=["raw_files"]
    )

    # run load_raw_data again; because file changed, cache should be invalidated and overwritten
    ds2.load_raw_data(verbose=False)

    with open(cache_path, "rb") as f:
        data2 = pickle.load(f)

    sig_after = data2.get("__watch_sig__")
    assert sig_after is not None
    assert sig_after != sig_before
