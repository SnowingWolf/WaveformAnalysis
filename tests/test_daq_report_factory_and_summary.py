from pathlib import Path

import pytest

from waveform_analysis import WaveformDataset
from waveform_analysis.utils.daq import DAQAnalyzer


def test_summary_includes_daq_info(tmp_path: Path, make_csv_fn):
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "summ_run"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    # create channel files
    make_csv_fn(raw_dir, 6, 0, 1000, 2000)
    make_csv_fn(raw_dir, 7, 0, 1500, 2500)

    ds = WaveformDataset(char="summ_run", data_root=str(daq_root), use_daq_scan=True)
    ds.check_daq_status()
    summary = ds.summary()

    assert "daq" in summary
    assert summary["daq"]["found"] is True
    assert "6" in summary["daq"]["channels_summary"]


def test_from_daq_report_runs_pipeline(tmp_path: Path, make_csv_fn):
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "factory_run"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    # create minimal CSVs
    make_csv_fn(raw_dir, 6, 0, 1000, 2000)
    make_csv_fn(raw_dir, 7, 0, 1500, 2500)

    analyzer = DAQAnalyzer(str(daq_root))
    analyzer.scan_all_runs()
    out = tmp_path / "report.json"
    analyzer.save_to_json(out)

    # factory run creates dataset and runs pipeline
    ds = WaveformDataset.from_daq_report(
        "factory_run", daq_report=str(out), data_root=str(daq_root), load_waveforms=True, run_pipeline=True
    )

    # basic checks
    assert ds.df is not None
    assert isinstance(ds.summary(), dict)
    assert ds.daq_info is not None or ds.daq_run is not None
