from pathlib import Path

from tests.utils import make_csv
from waveform_analysis import WaveformDataset
from waveform_analysis.utils.daq import DAQAnalyzer


def test_waveformdataset_loads_using_daq_scan(tmp_path: Path):
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "my_run"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    # create CH6/CH7 files to match start_channel_slice default 6
    make_csv(raw_dir, 6, 0, 1000, 2000)
    make_csv(raw_dir, 7, 0, 1500, 2500)

    # Use DAQ scan integration
    ds = WaveformDataset(char="my_run", data_root=str(daq_root), use_daq_scan=True)
    # load_raw_data should use daq scan info and populate raw_files
    ds.load_raw_data(verbose=True)

    # Expect that raw_files list contains our files at indices 6 and 7
    assert len(ds.raw_files) >= 8
    assert any("RUN_CH6_0.CSV" in p for p in ds.raw_files[6])
    assert any("RUN_CH7_0.CSV" in p for p in ds.raw_files[7])


def test_waveformdataset_loads_using_daq_report(tmp_path: Path):
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "report_run"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    make_csv(raw_dir, 6, 0, 1000, 2000)

    # create json report
    analyzer = DAQAnalyzer(str(daq_root))
    analyzer.scan_all_runs()
    out = tmp_path / "report.json"
    analyzer.save_to_json(out)

    ds = WaveformDataset(char="report_run", data_root=str(daq_root), use_daq_scan=True, daq_report=str(out))
    ds.load_raw_data(verbose=True)

    assert len(ds.raw_files) >= 7
    assert any("RUN_CH6_0.CSV" in p for p in ds.raw_files[6])
