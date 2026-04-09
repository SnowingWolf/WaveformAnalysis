from unittest.mock import patch

import numpy as np
from numpy.lib import recfunctions as rfn
import pytest

from tests.utils import FakeContext
from waveform_analysis.core.data.records_view import RecordsView
from waveform_analysis.core.plugins.builtin.cpu.dataframe import DataFramePlugin
from waveform_analysis.core.processing.records_builder import RECORDS_DTYPE


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
    fields = [("timestamp", "i8"), ("record_id", "i8")]
    if include_board:
        fields.append(("board", "i2"))
    fields.append(("channel", "i2"))
    dtype = np.dtype(fields)
    data = np.zeros(3, dtype=dtype)
    data["timestamp"] = [300, 100, 200]
    data["record_id"] = [30, 10, 20]
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


def _make_records_view():
    records = np.zeros(3, dtype=RECORDS_DTYPE)
    records["timestamp"] = [300, 100, 200]
    records["pid"] = [0, 0, 0]
    records["board"] = [2, 1, 2]
    records["channel"] = [0, 1, 0]
    records["record_id"] = [30, 10, 20]
    records["baseline"] = [100.0, 100.0, 100.0]
    records["wave_offset"] = [0, 2, 4]
    records["event_length"] = [2, 2, 2]
    records["time"] = [0, 0, 0]
    wave_pool = np.array([100, 99, 100, 98, 100, 97], dtype=np.uint16)
    return RecordsView(records, wave_pool)


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
    assert list(df["record_id"]) == [10, 20, 30]
    assert list(df["timestamp"]) == [100, 200, 300]


def test_dataframe_plugin_gain_columns_with_partial_map():
    ctx = FakeContext(
        config={"df.gain_adc_per_pe": {"2:0": 10.0}},
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


def test_dataframe_plugin_invalid_gain_key_raises(caplog):
    ctx = FakeContext(
        config={"gain_adc_per_pe": {"2:0": 0.0, "1:1": -1.0, "bad": "x"}},
        data={
            "st_waveforms": _make_st_waveforms(),
            "basic_features": _make_basic_features(),
        },
    )
    plugin = DataFramePlugin()
    with pytest.raises(ValueError, match="Invalid channel key 'bad'"):
        plugin.compute(ctx, "run_001")
    assert "non-positive" in caplog.text


def test_dataframe_plugin_gain_from_run_config():
    ctx = _RunConfigContext(
        data={
            "st_waveforms": _make_st_waveforms(),
            "basic_features": _make_basic_features(),
        },
        run_config_payload={"calibration": {"gain_adc_per_pe": {"2:0": 10.0}}},
    )
    plugin = DataFramePlugin()
    df = plugin.compute(ctx, "run_001")

    assert "area_pe" in df.columns
    assert "height_pe" in df.columns
    np.testing.assert_allclose(df["area_pe"].to_numpy(), [np.nan, 2.0, 3.0], equal_nan=True)
    np.testing.assert_allclose(df["height_pe"].to_numpy(), [np.nan, 1.0, 1.5], equal_nan=True)


def test_dataframe_plugin_explicit_gain_overrides_run_config():
    ctx = _RunConfigContext(
        config={"df.gain_adc_per_pe": {"2:0": 5.0}},
        data={
            "st_waveforms": _make_st_waveforms(),
            "basic_features": _make_basic_features(),
        },
        run_config_payload={"calibration": {"gain_adc_per_pe": {"2:0": 10.0}}},
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


def test_dataframe_plugin_fallback_record_id_when_field_missing():
    waveform_data = _make_st_waveforms()
    waveform_data = rfn.drop_fields(waveform_data, ["record_id"], usemask=False)
    ctx = FakeContext(
        data={
            "st_waveforms": waveform_data,
            "basic_features": _make_basic_features(),
        }
    )
    plugin = DataFramePlugin()
    df = plugin.compute(ctx, "run_001")

    np.testing.assert_array_equal(df["record_id"].to_numpy(), np.array([1, 2, 0], dtype=np.int64))


def test_dataframe_plugin_wave_source_records_depends_on_records_wave_pool_and_basic_features():
    ctx = FakeContext(config={"wave_source": "records", "use_filtered": True})
    plugin = DataFramePlugin()

    assert plugin.resolve_depends_on(ctx) == ["records", "wave_pool", "basic_features"]


def test_dataframe_plugin_reads_records_view_when_wave_source_records():
    ctx = FakeContext(
        config={
            "df.wave_source": "records",
            "basic_features.wave_source": "records",
        },
        data={"basic_features": _make_basic_features()},
    )
    plugin = DataFramePlugin()
    rv = _make_records_view()

    with patch("waveform_analysis.core.records_view", return_value=rv) as mocked:
        df = plugin.compute(ctx, "run_001")

    mocked.assert_called_once_with(ctx, "run_001")
    assert list(df["timestamp"]) == [100, 200, 300]
    assert list(df["record_id"]) == [10, 20, 30]
    assert list(df["channel"]) == [1, 0, 0]
    assert list(df["area"]) == [10.0, 20.0, 30.0]
    np.testing.assert_array_equal(df["board"].to_numpy(), np.array([1, 2, 2], dtype=np.int16))


def test_dataframe_plugin_records_requires_basic_features_records_source():
    ctx = FakeContext(
        config={
            "df.wave_source": "records",
            "basic_features.wave_source": "st_waveforms",
        },
        data={"basic_features": _make_basic_features()},
    )
    plugin = DataFramePlugin()

    try:
        plugin.compute(ctx, "run_001")
    except ValueError as exc:
        assert "basic_features.wave_source=records" in str(exc)
    else:
        raise AssertionError("Expected ValueError for mismatched basic_features source")


def test_dataframe_plugin_records_empty_returns_empty_df():
    empty_features = np.zeros(0, dtype=_make_basic_features().dtype)
    empty_records = np.zeros(0, dtype=RECORDS_DTYPE)
    rv = RecordsView(empty_records, np.zeros(0, dtype=np.uint16))
    ctx = FakeContext(
        config={
            "df.wave_source": "records",
            "basic_features.wave_source": "records",
        },
        data={"basic_features": empty_features},
    )
    plugin = DataFramePlugin()

    with patch("waveform_analysis.core.records_view", return_value=rv):
        df = plugin.compute(ctx, "run_001")

    assert list(df.columns) == [
        "timestamp",
        "record_id",
        "area",
        "height",
        "amp",
        "board",
        "channel",
    ]
    assert df.empty
