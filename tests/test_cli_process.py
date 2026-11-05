"""CLI target selection and scalar table export contracts."""

import sys

import numpy as np
import pandas as pd
import pytest

from waveform_analysis import cli


@pytest.fixture
def processing_runtime(monkeypatch):
    captured = {}

    class FakeContext:
        def __init__(self, config):
            captured["config"] = config

        def register(self, *plugins):
            captured["plugins"] = plugins

        def get_data(self, run_id, target):
            captured["request"] = (run_id, target)
            return captured["data"]

    class FakeProfiles:
        @staticmethod
        def get_profile(name):
            captured["profile"] = name
            return lambda: ("fake-plugin",)

    monkeypatch.setitem(vars(cli), "Context", FakeContext)
    monkeypatch.setitem(vars(cli), "profiles", FakeProfiles)
    return captured


@pytest.mark.parametrize("rows", [[], [(1, 6, 12.5), (1, 7, 20.0)]])
def test_explicit_target_writes_csv_with_headers(rows, processing_runtime, monkeypatch, tmp_path):
    processing_runtime["data"] = np.array(
        rows, dtype=[("board", "i2"), ("channel", "i2"), ("height", "f8")]
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "waveform-process",
            "--run-name",
            "run_001",
            "--target",
            "basic_features",
            "--daq-root",
            "/data/DAQ",
            "--daq-adapter",
            "v1725",
            "--n-channels",
            "4",
        ],
    )

    assert cli.main() == 0

    output = pd.read_csv(tmp_path / "outputs" / "run_001_basic_features.csv")
    assert list(output.columns) == ["board", "channel", "height"]
    assert output.to_records(index=False).tolist() == rows
    assert processing_runtime["request"] == ("run_001", "basic_features")
    assert processing_runtime["config"] == {
        "data_root": "/data/DAQ",
        "daq_adapter": "v1725",
        "n_channels": 4,
    }
    assert processing_runtime["profile"] == "cpu"
    assert processing_runtime["plugins"] == ("fake-plugin",)


def test_explicit_output_uses_parquet_without_index(processing_runtime, monkeypatch, tmp_path):
    data = np.array([(3, 14.0)], dtype=[("record_index", "i8"), ("height", "f8")])
    processing_runtime["data"] = data
    output = tmp_path / "exports" / "hits.parquet"
    captured = {}

    def capture_parquet(frame, path, *, index):
        captured.update(frame=frame, path=path, index=index)

    monkeypatch.setattr(pd.DataFrame, "to_parquet", capture_parquet)
    monkeypatch.setattr(
        sys,
        "argv",
        ["waveform-process", "--run-name", "run_001", "--target", "hit", "--output", str(output)],
    )

    assert cli.main() == 0
    assert processing_runtime["request"] == ("run_001", "hit")
    assert captured["path"] == output
    assert captured["index"] is False
    pd.testing.assert_frame_equal(captured["frame"], pd.DataFrame.from_records(data))


@pytest.mark.parametrize(
    "arguments, message",
    [
        (["--run-name", "run_001"], "--target 是必需的"),
        *[
            (["--run-name", "run_001", "--target", name], "已退役")
            for name in ("df", "df_events", "df_paired")
        ],
        (["--run-name", "run_001", "--time-window", "100"], "unrecognized arguments"),
        (["--run-name", "run_001", "--start-channel", "6"], "unrecognized arguments"),
    ],
)
def test_invalid_processing_arguments_fail_before_runtime(arguments, message, monkeypatch, capsys):
    def fail_load(*names):
        pytest.fail(f"Unexpected runtime load: {names}")

    monkeypatch.setattr(cli, "_load_runtime", fail_load)
    monkeypatch.setattr(sys, "argv", ["waveform-process", *arguments])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    "data",
    [
        np.zeros(3),
        np.zeros((2, 2), dtype=[("height", "f8")]),
        np.zeros(1, dtype=[("waveform", "f8", (4,))]),
        np.zeros(1, dtype=[("nested", [("height", "f8")])]),
        np.zeros(1, dtype=[("payload", object)]),
    ],
)
def test_non_scalar_table_target_fails_without_output(
    data, processing_runtime, monkeypatch, tmp_path, capsys
):
    processing_runtime["data"] = data
    output = tmp_path / "result.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "waveform-process",
            "--run-name",
            "run_001",
            "--target",
            "records",
            "--output",
            str(output),
        ],
    )

    assert cli.main() == 1
    assert "不是可导出的" in capsys.readouterr().err
    assert not output.exists()
