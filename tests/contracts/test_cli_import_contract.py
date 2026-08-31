"""Fresh-process import contracts for the command-line entry points."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).parents[2]
_OBSERVE_LOADED = """
import json
import sys

PREFIXES = (
    "waveform_analysis.acquisition.daq",
    "waveform_analysis.core.context",
    "waveform_analysis.core.plugins",
    "numpy",
    "scipy",
    "pandas",
    "numba",
    "jax",
)
print(json.dumps({
    "loaded": sorted(
        name
        for name in sys.modules
        if any(name == prefix or name.startswith(prefix + ".") for prefix in PREFIXES)
    ),
}, sort_keys=True))
"""


def _run_fresh(source: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.splitlines()[-1])


def _run_cli_fresh(arguments: list[str]) -> dict:
    source = f"""
import json
import sys

import waveform_analysis.cli as cli

sys.argv = ["waveform-process", *{arguments!r}]
try:
    exit_code = cli.main()
except SystemExit as exc:
    exit_code = exc.code

PREFIXES = (
    "waveform_analysis.acquisition.daq",
    "waveform_analysis.core.context",
    "waveform_analysis.core.plugins",
    "numpy",
    "scipy",
    "pandas",
    "numba",
    "jax",
)
print("CLI_MARKER " + json.dumps({{
    "exit_code": exit_code,
    "loaded": sorted(
        name
        for name in sys.modules
        if any(name == prefix or name.startswith(prefix + ".") for prefix in PREFIXES)
    ),
}}, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    marker = next(line for line in result.stdout.splitlines() if line.startswith("CLI_MARKER "))
    return json.loads(marker.removeprefix("CLI_MARKER "))


def test_cli_module_import_is_runtime_light_and_keeps_lazy_attributes():
    observed = _run_fresh(
        """
import json
import sys

import waveform_analysis.cli as cli

print(json.dumps({
    "missing_runtime_attrs": [
        name for name in ("Context", "DAQAnalyzer", "profiles") if name not in vars(cli)
    ],
    "visible_runtime_attrs": [name for name in ("Context", "DAQAnalyzer", "profiles") if name in dir(cli)],
    "loaded": sorted(
        name for name in sys.modules
        if name.startswith((
            "waveform_analysis.acquisition.daq",
            "waveform_analysis.core.context",
            "waveform_analysis.core.plugins",
            "numpy",
            "scipy",
            "pandas",
            "numba",
            "jax",
        ))
    ),
}, sort_keys=True))
"""
    )
    assert observed == {
        "missing_runtime_attrs": ["Context", "DAQAnalyzer", "profiles"],
        "visible_runtime_attrs": ["Context", "DAQAnalyzer", "profiles"],
        "loaded": [],
    }


@pytest.mark.parametrize(
    "arguments",
    (
        ["--help"],
        ["--version"],
        ["--not-an-option"],
        [],
    ),
)
def test_cli_parser_only_paths_do_not_load_runtime_modules(arguments):
    observed = _run_cli_fresh(arguments)
    assert observed["loaded"] == []
    if arguments == ["--help"] or arguments == ["--version"]:
        assert observed["exit_code"] == 0
    elif arguments == ["--not-an-option"]:
        assert observed["exit_code"] == 2
    else:
        assert observed["exit_code"] == 2


@pytest.mark.parametrize(
    "arguments",
    (
        ["--scan-daq", "--daq-root", "/tmp/missing"],
        ["--show-daq", "run", "--daq-root", "/tmp/missing"],
    ),
)
def test_daq_cli_paths_load_only_daq_runtime(arguments):
    observed = _run_cli_fresh(arguments)
    assert any(name.startswith("waveform_analysis.acquisition.daq") for name in observed["loaded"])
    assert not any(name.startswith("waveform_analysis.core.context") for name in observed["loaded"])
    assert not any(name.startswith("waveform_analysis.core.plugins") for name in observed["loaded"])
    assert not any(
        name.startswith(("numpy", "scipy", "pandas", "numba", "jax")) for name in observed["loaded"]
    )


@pytest.mark.parametrize(
    "arguments",
    (
        ["--show-config"],
        ["--run-name", "run", "--output", "/tmp/cli-import-contract.csv"],
    ),
)
def test_context_cli_paths_request_only_context_and_profiles(arguments):
    source = f"""
import json
import sys
import types

import waveform_analysis.cli as cli

calls = []

class FakeContext:
    def __init__(self, config):
        self.config = config

    def register(self, *plugins):
        return None

    def set_config(self, config):
        return None

    def get_adapter_info(self):
        return None

    def show_resolved_config(self, **kwargs):
        return None

    def get_data(self, run_id, data_name):
        class FakeFrame:
            def __len__(self):
                return 0

            def to_csv(self, *args, **kwargs):
                return None

        return FakeFrame()

class FakeProfiles:
    @staticmethod
    def get_profile(name):
        return lambda: ()

def fake_import(module_name):
    calls.append(module_name)
    modules = {{
        "waveform_analysis.core.context": types.SimpleNamespace(Context=FakeContext),
        "waveform_analysis.core.plugins": types.SimpleNamespace(profiles=FakeProfiles),
    }}
    return modules[module_name]

cli._import_module = fake_import
sys.argv = ["waveform-process", *{arguments!r}]
exit_code = cli.main()
print("CLI_MARKER " + json.dumps({{"exit_code": exit_code, "calls": calls}}, sort_keys=True))
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    marker = next(line for line in result.stdout.splitlines() if line.startswith("CLI_MARKER "))
    observed = json.loads(marker.removeprefix("CLI_MARKER "))
    assert observed == {
        "exit_code": 0,
        "calls": ["waveform_analysis.core.context", "waveform_analysis.core.plugins"],
    }


@pytest.mark.parametrize(
    "module_name", ("waveform_analysis.cli_cache", "waveform_analysis.documentation.cli")
)
def test_other_cli_modules_remain_light_in_fresh_process(module_name):
    observed = _run_fresh(
        f"import importlib\nimportlib.import_module({module_name!r})\n{_OBSERVE_LOADED}"
    )
    assert observed["loaded"] == []
