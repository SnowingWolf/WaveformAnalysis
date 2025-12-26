from pathlib import Path

import pytest

from waveform_analysis import WaveformDataset


def test_summary_from_daq_scan_includes_fields(tmp_path: Path, make_csv_fn):
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "scan_run"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    make_csv_fn(raw_dir, 6, 0, 1000, 2000)
    make_csv_fn(raw_dir, 7, 0, 1500, 2500)

    ds = WaveformDataset(char="scan_run", data_root=str(daq_root), use_daq_scan=True, daq_root=str(daq_root))
    info = ds.check_daq_status()
    assert info is not None

    summary = ds.summary()
    assert "daq" in summary
    assert summary["daq"]["found"] is True
    assert summary["daq"]["run_path"] == str(run_dir)
    assert isinstance(summary["daq"]["channels"], list)
    assert summary["daq"]["channel_count"] >= 1
    assert "channels_summary" in summary["daq"]
    assert "6" in summary["daq"]["channels_summary"]
