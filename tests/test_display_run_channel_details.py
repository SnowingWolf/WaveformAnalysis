from pathlib import Path

from tests.utils import make_csv
from waveform_analysis.utils.daq import DAQAnalyzer


def test_display_run_channel_details_prints(tmp_path: Path):
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "disp_run"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    make_csv(raw_dir, 6, 0, 1000, 2000)
    make_csv(raw_dir, 7, 0, 1500, 2500)

    analyzer = DAQAnalyzer(str(daq_root))
    analyzer.scan_all_runs()

    # ensure it doesn't raise and returns self
    result = analyzer.display_run_channel_details("disp_run")
    assert result is analyzer

    # and with file details
    result2 = analyzer.display_run_channel_details("disp_run", show_files=True)
    assert result2 is analyzer
