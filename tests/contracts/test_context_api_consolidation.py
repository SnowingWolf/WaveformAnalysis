"""Behavior at the unified Context configuration and time-query boundaries."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import numpy as np
import pytest

from waveform_analysis import Context
from waveform_analysis.core.config import CompatManager, ConfigSource, ConfigValue, ResolvedConfig
from waveform_analysis.plugins import Option, Plugin

pytestmark = pytest.mark.contract


class Settings(Plugin):
    provides = "settings"
    options = {
        "threshold": Option(default=10, type=int, help="Signal threshold"),
        "other": Option(default=20, type=int),
        "daq_adapter": Option(default=None),
        "dt_ns": Option(default=8, type=int),
        "duration": Option(default=1.0, type=float, unit="ns", internal_unit="ps"),
    }

    def compute(self, context, run_id):
        return np.array([context.get_config(self, "threshold")])


@pytest.fixture
def settings(tmp_path):
    ctx = Context(storage_dir=str(tmp_path / "cache"))
    ctx.register(Settings)
    return ctx


def test_single_value_source_and_full_config(settings):
    settings.set_config({"threshold": "30"}, plugin_name="settings")
    for plugin in ("settings", settings.get_plugin("settings")):
        assert settings.get_config(plugin, "threshold") == 30
        value = settings.get_config(plugin, "threshold", with_source=True)
        assert isinstance(value, ConfigValue)
        assert value.value == 30 and value.source is ConfigSource.EXPLICIT
        full = settings.get_config(plugin)
        assert isinstance(full, ResolvedConfig)
        assert full["threshold"] == value.value
        assert full["duration"] == settings.get_config(plugin, "duration") == 1000.0
    assert settings.config["settings"]["threshold"] == "30"


def test_single_lookup_preserves_alias_and_validation_boundary(settings):
    settings.set_config({"other": "invalid"}, plugin_name="settings")
    CompatManager.register_alias("old_threshold", "threshold", "settings")
    try:
        assert settings.get_config("settings", "old_threshold") == 10
        with pytest.raises(TypeError):
            settings.get_config("settings")
        with pytest.raises(KeyError, match="missing"):
            settings.get_config("settings", "missing")
        with pytest.raises(KeyError, match="unknown"):
            settings.get_config("unknown")
    finally:
        CompatManager.unregister_alias("old_threshold", "settings")


def test_adapter_sources_follow_plugin_overrides_and_query_does_not_mutate(settings, monkeypatch):
    class OtherSettings(Settings):
        provides = "other_settings"

    settings.register(OtherSettings)
    adapters = {
        name: SimpleNamespace(name=name, dt_ns=dt)
        for name, dt in [("global", 2), ("local", 4), ("query", 6)]
    }
    monkeypatch.setattr("waveform_analysis.core.config.resolver.get_adapter_info", adapters.get)
    settings.set_config({"daq_adapter": "global", "settings": {"daq_adapter": "local"}})
    before = deepcopy(settings.config)
    info = settings.show_config(show_source=True, output="dict")
    assert info["settings"]["adapter_name"] == "local"
    assert info["settings"]["options"]["dt_ns"]["current_value"] == 4
    assert info["settings"]["options"]["dt_ns"]["source"] == "adapter_inferred"
    assert info["other_settings"]["adapter_name"] == "global"
    assert info["other_settings"]["options"]["dt_ns"]["current_value"] == 2
    assert settings.get_config("settings", "dt_ns", adapter_name="query") == 6
    assert settings.config == before
    settings.set_config({"dt_ns": 9}, plugin_name="settings")
    assert settings.get_config("settings", "dt_ns", adapter_name="query") == 9


def test_metadata_dict_is_silent_and_default_only_skips_invalid_values(settings, capsys):
    settings.set_config({"other": "invalid"}, plugin_name="settings")
    info = settings.show_config("settings", output="dict", show_current_values=False)
    assert capsys.readouterr().out == ""
    assert info["settings"]["options"]["threshold"] == {
        "default": 10,
        "type": "int",
        "help": "Signal threshold",
        "track": True,
    }
    with pytest.raises(KeyError):
        settings.show_config("unknown")
    with pytest.raises(ValueError, match="options view"):
        settings.show_config(output="dict")
    with pytest.raises(ValueError, match="show_current_values"):
        settings.show_config(show_source=True, show_current_values=False)


def test_source_display_returns_none_and_exposes_explicit_default(settings, monkeypatch):
    import IPython.display

    displayed = []
    monkeypatch.setattr(IPython.display, "display", displayed.append)
    settings.set_config({"threshold": 10}, plugin_name="settings")
    assert settings.show_config("settings", show_source=True) is None
    row = displayed[1].data.loc[("settings", "threshold")]
    assert row["source"] == "explicit"
    assert row["current"] == "10"


@pytest.mark.parametrize("snapshot", [False, True])
@pytest.mark.parametrize("as_string", [False, True])
def test_json_path_uses_same_update_rules_and_preserves_other_keys(
    settings, tmp_path, snapshot, as_string
):
    settings.set_config({"other": 33}, plugin_name="settings")
    payload = {"threshold": 40}
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"custom_config": payload} if snapshot else payload))
    settings.set_config(str(path) if as_string else path, plugin_name="settings")
    assert settings.config["settings"] == {"other": 33, "threshold": 40}
    settings.set_config({"settings": {"threshold": 50}})
    assert settings.config["settings"] == {"threshold": 50}


@pytest.mark.parametrize("content", ["[1, 2]", "{invalid"])
def test_invalid_json_keeps_configuration_and_planning_cache(settings, tmp_path, content):
    path = tmp_path / "invalid.json"
    path.write_text(content)
    before = deepcopy(settings.config)
    settings._lineage_cache["sentinel"] = {"unchanged": True}
    with pytest.raises(ValueError):
        settings.set_config(path)
    assert settings.config == before
    assert settings._lineage_cache["sentinel"] == {"unchanged": True}


@pytest.fixture
def timed(tmp_path, monkeypatch):
    ctx = Context(storage_dir=str(tmp_path / "cache"))
    dtype = [
        ("time", "i8"),
        ("timestamp", "i8"),
        ("shifted", "i8"),
        ("board", "i2"),
        ("channel", "i2"),
    ]
    data = np.array(
        [(n * 10**9, n * 10**12, (n + 10) * 10**9, 0, n % 2) for n in range(1, 6)], dtype=dtype
    )
    monkeypatch.setattr(ctx, "get_data", lambda run_id, data_name: data)
    return ctx, data


@pytest.mark.parametrize("time_domain,scale", [("system_ns", 10**9), ("raw_ps", 10**12)])
@pytest.mark.parametrize("indexed", [True, False])
def test_datetime_and_integer_queries_agree_with_channels_and_open_bounds(
    timed, time_domain, scale, indexed
):
    ctx, data = timed
    epoch = datetime(2024, 1, 1, tzinfo=timezone(timedelta(hours=8)))
    ctx.set_epoch("run", epoch)
    kwargs = {"time_domain": time_domain, "auto_build_index": indexed, "channel": "0:0"}
    expected = ctx.time_range("run", "timed", 2 * scale, 4 * scale, **kwargs)
    actual = ctx.time_range(
        "run", "timed", epoch + timedelta(seconds=2), epoch + timedelta(seconds=4), **kwargs
    )
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(actual, data[[1]])
    for start, end in [(None, epoch + timedelta(seconds=4)), (epoch + timedelta(seconds=2), None)]:
        result = ctx.time_range("run", "timed", start, end, **kwargs)
        assert len(result) >= len(actual)
    # Naive datetimes retain the established epoch-timezone interpretation.
    naive = ctx.time_range(
        "run",
        "timed",
        (epoch + timedelta(seconds=2)).replace(tzinfo=None),
        (epoch + timedelta(seconds=4)).replace(tzinfo=None),
        **kwargs,
    )
    np.testing.assert_array_equal(naive, expected)


def test_time_axis_indices_are_not_reused_across_units_or_fields(timed):
    ctx, data = timed
    ctx.build_time_index("run", "timed", time_domain="system_ns")
    np.testing.assert_array_equal(
        ctx.time_range("run", "timed", 2 * 10**12, 3 * 10**12, time_domain="raw_ps"), data[[1]]
    )
    np.testing.assert_array_equal(
        ctx.time_range("run", "timed", 12 * 10**9, 13 * 10**9, time_field="shifted"), data[[1]]
    )
    np.testing.assert_array_equal(ctx.time_range("run", "timed", 2 * 10**9, 3 * 10**9), data[[1]])


@pytest.mark.parametrize("epoch_unit", ["ps", "us"])
@pytest.mark.parametrize("time_domain", ["system_ns", "raw_ps"])
def test_datetime_conversion_respects_epoch_unit(timed, epoch_unit, time_domain):
    ctx, data = timed
    epoch = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ctx.set_epoch("run", epoch, time_unit=epoch_unit)
    actual = ctx.time_range(
        "run",
        "timed",
        epoch + timedelta(seconds=2),
        epoch + timedelta(seconds=3),
        time_domain=time_domain,
    )
    np.testing.assert_array_equal(actual, data[[1]])


@pytest.mark.parametrize("indexed", [False, True])
def test_empty_time_query_preserves_output_dtype(timed, monkeypatch, indexed):
    ctx, data = timed
    monkeypatch.setattr(ctx, "get_data", lambda run_id, data_name: data[:0])
    epoch = datetime(2024, 1, 1, tzinfo=timezone.utc)
    ctx.set_epoch("run", epoch)
    for start in (0, epoch):
        actual = ctx.time_range("run", "timed", start, auto_build_index=indexed)
        assert actual.size == 0 and actual.dtype == data.dtype


def test_legacy_channel_indices_are_also_scoped_by_axis(timed, monkeypatch):
    ctx, data = timed
    monkeypatch.setattr(ctx, "get_data", lambda run_id, data_name: [data, data])
    ctx.time_range("run", "legacy", 2 * 10**9, 3 * 10**9)
    np.testing.assert_array_equal(
        ctx.time_range("run", "legacy", 2 * 10**12, 3 * 10**12, channel=1, time_domain="raw_ps"),
        data[[1]],
    )


def test_epoch_is_only_required_for_datetime_bounds(timed, monkeypatch):
    ctx, data = timed
    calls = []
    epoch = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def extract(run_id, strategy=None):
        calls.append(run_id)
        ctx.set_epoch(run_id, epoch)
        return ctx.get_epoch(run_id)

    monkeypatch.setattr(ctx._time_domain, "auto_extract_epoch", extract)
    np.testing.assert_array_equal(ctx.time_range("run", "timed"), data)
    assert calls == []
    with pytest.raises(ValueError, match="epoch"):
        ctx.time_range("run", "timed", epoch, auto_extract_epoch=False)
    ctx.time_range("run", "timed", epoch)
    assert calls == ["run"]
    ctx.set_config({"auto_extract_epoch": False})
    with pytest.raises(ValueError, match="epoch"):
        ctx.time_range("other_run", "timed", epoch)


@pytest.mark.parametrize(
    "start,end", [(1, datetime(2024, 1, 1)), (True, 2), (1.5, None), ("2024-01-01", None)]
)
def test_invalid_time_bounds_fail_before_reading_data(timed, monkeypatch, start, end):
    ctx, _ = timed

    def fail_read(*args, **kwargs):
        pytest.fail("invalid bounds must fail before requesting data")

    monkeypatch.setattr(ctx, "get_data", fail_read)
    with pytest.raises(TypeError):
        ctx.time_range("run", "timed", start, end)
