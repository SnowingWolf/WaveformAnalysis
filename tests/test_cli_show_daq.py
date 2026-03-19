from pathlib import Path
import sys

from waveform_analysis import cli


def test_cli_show_daq_returns_zero(tmp_path: Path, monkeypatch):
    daq_root = tmp_path / "DAQ"
    run_dir = daq_root / "cli_run"
    raw_dir = run_dir / "RAW"
    raw_dir.mkdir(parents=True)

    # create minimal CSVs
    n_samples = 50
    "HEADER;X;TIMETAG;" + ";".join(f"S{i}" for i in range(n_samples)) + "\n"

    from tests.utils import make_simple_csv

    make_simple_csv(raw_dir, 6, 0, 1000, n_samples=50)

    # call CLI with args: waveform-process --show-daq cli_run --daq-root <tmp>
    monkeypatch.setattr(
        sys, "argv", ["waveform-process", "--show-daq", "cli_run", "--daq-root", str(daq_root)]
    )
    code = cli.main()
    assert code == 0


def test_cli_show_daq_passes_daq_adapter(monkeypatch):
    captured = {}

    class _FakeAnalyzer:
        def __init__(self, daq_root, daq_adapter=None):
            captured["daq_root"] = daq_root
            captured["daq_adapter"] = daq_adapter

        def scan_all_runs(self):
            return self

        def display_run_channel_details(self, *_args, **_kwargs):
            return self

    monkeypatch.setattr(cli, "DAQAnalyzer", _FakeAnalyzer)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "waveform-process",
            "--show-daq",
            "cli_run",
            "--daq-root",
            "/tmp/daq",
            "--daq-adapter",
            "v1725",
        ],
    )
    code = cli.main()
    assert code == 0
    assert captured["daq_adapter"] == "v1725"


def test_cli_scan_daq_passes_daq_adapter(monkeypatch, tmp_path: Path):
    captured = {}

    class _FakeAnalyzer:
        def __init__(self, daq_root, daq_adapter=None):
            captured["daq_root"] = daq_root
            captured["daq_adapter"] = daq_adapter

        def scan_all_runs(self):
            return self

        def save_to_json(self, out):
            return str(out)

    monkeypatch.setattr(cli, "DAQAnalyzer", _FakeAnalyzer)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "waveform-process",
            "--scan-daq",
            "--daq-root",
            "/tmp/daq",
            "--daq-out",
            str(tmp_path / "out.json"),
            "--daq-adapter",
            "v1725",
        ],
    )
    code = cli.main()
    assert code == 0
    assert captured["daq_adapter"] == "v1725"
