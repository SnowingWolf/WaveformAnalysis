import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Option, Plugin


class _GainEchoPlugin(Plugin):
    provides = "feature_table"
    depends_on = []
    options = {
        "gain_adc_per_pe": Option(default=None, type=dict),
    }

    def compute(self, context, run_id, **kwargs):
        return context.get_config(self, "gain_adc_per_pe")


class _GroupingEchoPlugin(Plugin):
    provides = "grouped_table"
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


def test_legacy_events_df_gain_config_no_longer_migrates():
    ctx = Context(config={"events_df.gain_adc_per_pe": {"0": 12.5}})
    ctx.register(_GainEchoPlugin())

    result = ctx.get_data("run_001", "feature_table")

    assert result is None
    assert ctx.config["events_df.gain_adc_per_pe"] == {"0": 12.5}


def test_legacy_events_df_gain_is_ignored_even_when_df_config_exists():
    ctx = Context(
        config={
            "feature_table.gain_adc_per_pe": {"0": 3.0},
            "events_df.gain_adc_per_pe": {"0": 12.5},
        }
    )
    ctx.register(_GainEchoPlugin())

    result = ctx.get_data("run_001", "feature_table")

    assert result == {"0": 3.0}
    assert ctx.config["events_df.gain_adc_per_pe"] == {"0": 12.5}


def test_legacy_removed_events_df_config_keys_are_ignored():
    ctx = Context(config={"events_df.include_event_id": False})
    ctx.register(_GainEchoPlugin())

    result = ctx.get_data("run_001", "feature_table")
    assert result is None


def test_legacy_events_grouped_config_no_longer_migrates():
    ctx = Context(
        config={
            "events_grouped.time_window_ns": 3.5,
            "events_grouped.use_numba": False,
            "events_grouped.n_processes": 4,
        }
    )
    ctx.register(_GroupingEchoPlugin())

    result = ctx.get_data("run_001", "grouped_table")

    assert result["time_window_ns"] == 100.0
    assert result["use_numba"] is None
    assert result["n_processes"] is None
    assert ctx.config["events_grouped.time_window_ns"] == 3.5
    assert ctx.config["events_grouped.use_numba"] is False
    assert ctx.config["events_grouped.n_processes"] == 4
