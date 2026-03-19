import numpy as np

from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.cpu.dataframe import DataFramePlugin


class _RunConfigContext(FakeContext):
    def __init__(self, *args, **kwargs):
        self._run_config_payload = kwargs.pop("run_config_payload", {})
        super().__init__(*args, **kwargs)

    def get_run_config(self, run_id: str, refresh: bool = False):
        return self._run_config_payload

    def has_explicit_config(self, plugin, name: str):
        provides = plugin.provides
        nested = self.config.get(provides)
        if isinstance(nested, dict) and name in nested:
            return True
        return f"{provides}.{name}" in self.config


def _make_st_waveforms(include_board: bool = True):
    fields = [("timestamp", "i8")]
    if include_board:
        fields.append(("board", "i2"))
    fields.append(("channel", "i2"))
    dtype = np.dtype(fields)
    data = np.zeros(3, dtype=dtype)
    data["timestamp"] = [300, 100, 200]
    if include_board:
        data["board"] = [2, 1, 2]
    data["channel"] = [0, 1, 0]
    return data


def _make_basic_features():
    dtype = np.dtype(
        [
            ("area", "f4"),
            ("height", "f4"),
            ("amp", "f4"),
        ]
    )
    data = np.zeros(3, dtype=dtype)
    data["area"] = [30.0, 10.0, 20.0]
    data["height"] = [15.0, 5.0, 10.0]
    data["amp"] = [4.0, 2.0, 3.0]
    return data


def test_dataframe_plugin_no_gain_columns_by_default():
    ctx = FakeContext(
        data={
            "st_waveforms": _make_st_waveforms(),
            "basic_features": _make_basic_features(),
        }
    )
    plugin = DataFramePlugin()
    df = plugin.compute(ctx, "run_001")

    assert "area_pe" not in df.columns
    assert "height_pe" not in df.columns
    assert list(df["board"]) == [1, 2, 2]
    assert list(df["timestamp"]) == [100, 200, 300]


def test_dataframe_plugin_gain_columns_with_partial_map():
    ctx = FakeContext(
        config={"df.gain_adc_per_pe": {0: 10.0}},
        data={
            "st_waveforms": _make_st_waveforms(),
            "basic_features": _make_basic_features(),
        },
    )
    plugin = DataFramePlugin()
    df = plugin.compute(ctx, "run_001")

    assert "area_pe" in df.columns
    assert "height_pe" in df.columns
    np.testing.assert_allclose(df["area_pe"].to_numpy(), [np.nan, 2.0, 3.0], equal_nan=True)
    np.testing.assert_allclose(df["height_pe"].to_numpy(), [np.nan, 1.0, 1.5], equal_nan=True)


def test_dataframe_plugin_invalid_gain_warns_and_yields_nan(caplog):
    ctx = FakeContext(
        config={"gain_adc_per_pe": {0: 0.0, 1: -1.0, "bad": "x"}},
        data={
            "st_waveforms": _make_st_waveforms(),
            "basic_features": _make_basic_features(),
        },
    )
    plugin = DataFramePlugin()
    df = plugin.compute(ctx, "run_001")

    assert "area_pe" in df.columns
    assert "height_pe" in df.columns
    assert np.isnan(df["area_pe"]).all()
    assert np.isnan(df["height_pe"]).all()
    assert "non-positive" in caplog.text


def test_dataframe_plugin_gain_from_run_config():
    ctx = _RunConfigContext(
        data={
            "st_waveforms": _make_st_waveforms(),
            "basic_features": _make_basic_features(),
        },
        run_config_payload={"calibration": {"gain_adc_per_pe": {"0": 10.0}}},
    )
    plugin = DataFramePlugin()
    df = plugin.compute(ctx, "run_001")

    assert "area_pe" in df.columns
    assert "height_pe" in df.columns
    np.testing.assert_allclose(df["area_pe"].to_numpy(), [np.nan, 2.0, 3.0], equal_nan=True)
    np.testing.assert_allclose(df["height_pe"].to_numpy(), [np.nan, 1.0, 1.5], equal_nan=True)


def test_dataframe_plugin_explicit_gain_overrides_run_config():
    ctx = _RunConfigContext(
        config={"df.gain_adc_per_pe": {0: 5.0}},
        data={
            "st_waveforms": _make_st_waveforms(),
            "basic_features": _make_basic_features(),
        },
        run_config_payload={"calibration": {"gain_adc_per_pe": {"0": 10.0}}},
    )
    plugin = DataFramePlugin()
    df = plugin.compute(ctx, "run_001")

    np.testing.assert_allclose(df["area_pe"].to_numpy(), [np.nan, 4.0, 6.0], equal_nan=True)
    np.testing.assert_allclose(df["height_pe"].to_numpy(), [np.nan, 2.0, 3.0], equal_nan=True)


def test_dataframe_plugin_fallback_board_when_field_missing():
    ctx = FakeContext(
        data={
            "st_waveforms": _make_st_waveforms(include_board=False),
            "basic_features": _make_basic_features(),
        }
    )
    plugin = DataFramePlugin()
    df = plugin.compute(ctx, "run_001")

    np.testing.assert_array_equal(df["board"].to_numpy(), np.zeros(3, dtype=np.int16))
