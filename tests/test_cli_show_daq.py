import sys
from pathlib import Path

from waveform_analysis import cli


def test_cli_show_daq_returns_zero(tmp_path: Path, monkeypatch):
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "cli_run"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    # create minimal CSVs
    n_samples = 50
    header = "HEADER;X;TIMETAG;" + ";".join(f"S{i}" for i in range(n_samples)) + "\n"

    from tests.utils import make_simple_csv

    make_simple_csv(raw_dir, 6, 0, 1000, n_samples=50)

    # call CLI with args: waveform-process --show-daq cli_run --daq-root <tmp>
    monkeypatch.setattr(sys, "argv", ["waveform-process", "--show-daq", "cli_run", "--daq-root", str(daq_root)])
    code = cli.main()
    assert code == 0
