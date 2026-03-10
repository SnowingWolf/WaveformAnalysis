import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Option, Plugin


class _DFGainEchoPlugin(Plugin):
    provides = "df"
    depends_on = []
    options = {
        "gain_adc_per_pe": Option(default=None, type=dict),
    }

    def compute(self, context, run_id, **kwargs):
        return context.get_config(self, "gain_adc_per_pe")


class _DFEventsEchoPlugin(Plugin):
    provides = "df_events"
    depends_on = []
    options = {
        "time_window_ns": Option(default=100.0, type=float),
    }

    def compute(self, context, run_id, **kwargs):
        return {
            "time_window_ns": context.get_config(self, "time_window_ns"),
            "use_numba": context.config.get("use_numba"),
            "n_processes": context.config.get("n_processes"),
        }


def test_removed_events_df_data_name_raises_migration_error():
    ctx = Context(config={})
    with pytest.raises(ValueError, match="events_df"):
        ctx.get_data("run_001", "events_df")


def test_removed_events_grouped_data_name_raises_migration_error():
    ctx = Context(config={})
    with pytest.raises(ValueError, match="events_grouped"):
        ctx.get_data("run_001", "events_grouped")


def test_legacy_events_df_gain_config_migrates_to_df():
    ctx = Context(config={"events_df.gain_adc_per_pe": {"0": 12.5}})
    ctx.register(_DFGainEchoPlugin())

    result = ctx.get_data("run_001", "df")

    assert result == {"0": 12.5}
    assert "events_df.gain_adc_per_pe" not in ctx.config
    assert ctx.config["df.gain_adc_per_pe"] == {"0": 12.5}


def test_legacy_events_df_gain_is_ignored_when_df_config_exists():
    ctx = Context(
        config={
            "df.gain_adc_per_pe": {"0": 3.0},
            "events_df.gain_adc_per_pe": {"0": 12.5},
        }
    )
    ctx.register(_DFGainEchoPlugin())

    result = ctx.get_data("run_001", "df")

    assert result == {"0": 3.0}
    assert "events_df.gain_adc_per_pe" not in ctx.config


def test_removed_events_df_config_keys_fail_fast():
    ctx = Context(config={"events_df.include_event_id": False})
    ctx.register(_DFGainEchoPlugin())

    with pytest.raises(ValueError, match="events_df.include_event_id"):
        ctx.get_data("run_001", "df")


def test_legacy_events_grouped_config_migrates_to_df_events_and_globals():
    ctx = Context(
        config={
            "events_grouped.time_window_ns": 3.5,
            "events_grouped.use_numba": False,
            "events_grouped.n_processes": 4,
        }
    )
    ctx.register(_DFEventsEchoPlugin())

    result = ctx.get_data("run_001", "df_events")

    assert result["time_window_ns"] == 3.5
    assert result["use_numba"] is False
    assert result["n_processes"] == 4
    assert "events_grouped.time_window_ns" not in ctx.config
    assert "events_grouped.use_numba" not in ctx.config
    assert "events_grouped.n_processes" not in ctx.config
    assert ctx.config["df_events.time_window_ns"] == 3.5
    assert ctx.config["use_numba"] is False
    assert ctx.config["n_processes"] == 4
