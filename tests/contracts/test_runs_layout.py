"""Run-management implementations remain shared across legacy entry points."""

from importlib import import_module
import pickle
import subprocess
import sys

import pytest


@pytest.mark.parametrize("first", ["runs", "daq", "utils"])
def test_run_import_orders_in_fresh_process(first):
    code = r"""
from importlib import import_module
import pickle
import sys

prefixes = {
    "runs": "waveform_analysis.acquisition.runs",
    "daq": "waveform_analysis.acquisition.daq",
    "utils": "waveform_analysis.utils.daq",
}
names = {"run": "daq_run", "analyzer": "daq_analyzer", "adapters": "daq", "discovery": "discovery"}
first = sys.argv[1]
for new, old in names.items():
    import_module(prefixes[first] + "." + (new if first == "runs" else old))
for new, old in names.items():
    canonical = import_module(prefixes["runs"] + "." + new)
    assert import_module(prefixes["daq"] + "." + old) is canonical
    assert import_module(prefixes["utils"] + "." + old) is canonical
    assert canonical.__name__ == prefixes["runs"] + "." + new

runs = import_module(prefixes["runs"])
daq = import_module(prefixes["daq"])
assert import_module(prefixes["utils"]) is daq
for name in ("DAQRun", "DAQAnalyzer", "adapt_daq_run"):
    value = getattr(runs, name)
    assert value is getattr(daq, name)
    assert pickle.loads(pickle.dumps(value)) is value
assert pickle.loads(b"cwaveform_analysis.utils.daq.daq_run\nDAQRun\n.") is runs.DAQRun
assert pickle.loads(b"cwaveform_analysis.utils.daq.daq_analyzer\nDAQAnalyzer\n.") is runs.DAQAnalyzer
assert import_module(prefixes["daq"] + ".models").DAQRun is runs.DAQRun
assert import_module(prefixes["daq"] + ".service").DAQAnalyzer is runs.DAQAnalyzer
presentation = import_module(prefixes["daq"] + ".presentation")
assert presentation.display_overview is runs.DAQAnalyzer.display_overview
assert presentation.display_run_channel_details is runs.DAQAnalyzer.display_run_channel_details
discovery = import_module(prefixes["runs"] + ".discovery")
assert runs.DAQAnalyzer.scan_all_runs is discovery.scan_all_runs
assert runs.DAQRun._scan_channel_files is discovery.scan_channel_files
assert runs.DAQRun._scan_default is discovery.scan_default
assert runs.DAQRun._scan_with_layout is discovery.scan_with_layout
"""
    result = subprocess.run(
        [sys.executable, "-c", code, first], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_run_instances_keep_historical_pickle_paths(tmp_path):
    from waveform_analysis.acquisition.runs import DAQAnalyzer, DAQRun, adapt_daq_run

    run = DAQRun("empty", tmp_path)
    analyzer = DAQAnalyzer(tmp_path)
    analyzer.runs["empty"] = run
    adapter = adapt_daq_run({0: ["wave.csv"]})
    restored = pickle.loads(pickle.dumps((run, analyzer, adapter)))
    assert type(restored[0]) is DAQRun
    assert restored[0].run_name == "empty"
    assert type(restored[1]) is DAQAnalyzer
    assert restored[1].runs["empty"] is restored[0]
    assert type(restored[2]) is type(adapter)
    assert restored[2].get_channel_paths(1) == [["wave.csv"]]
    for value in (DAQRun, DAQAnalyzer, type(adapter), adapt_daq_run):
        assert value.__module__.startswith("waveform_analysis.utils.daq.")


@pytest.mark.parametrize(
    "module_name",
    ["waveform_analysis.utils.daq.daq_analyzer", "waveform_analysis.acquisition.daq.daq_analyzer"],
)
def test_legacy_display_monkeypatch_reaches_actual_run_display(tmp_path, monkeypatch, module_name):
    from waveform_analysis.acquisition.runs import DAQAnalyzer, DAQRun

    legacy = import_module(module_name)
    displayed = []
    monkeypatch.setattr(legacy, "_ipydisplay", displayed.append)
    run = DAQRun("empty", tmp_path)
    run.channel_files[0] = [{"filename": "wave.csv", "index": 0, "size_bytes": 12}]
    DAQAnalyzer(tmp_path)._display_file_details_for_channel(run, 0)
    assert len(displayed) == 1
    assert displayed[0].loc[0, "filename"] == "wave.csv"
