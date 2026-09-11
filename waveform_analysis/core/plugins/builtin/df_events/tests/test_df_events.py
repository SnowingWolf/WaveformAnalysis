import pandas as pd

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.df_events import GroupedEventsPlugin


def test_df_events_groups_within_time_window():
    df = pd.DataFrame(
        {
            "timestamp": [1000000, 1000010, 1000020],  # 在 100ns 窗口内
            "area": [100, 200, 300],
            "height": [10, 20, 30],
            "channel": [0, 1, 0],
        }
    )
    plugin = GroupedEventsPlugin()
    ctx = DummyContext({"time_window_ns": 100}, {"df": df})

    out = plugin.compute(ctx, "run_001")

    assert isinstance(out, pd.DataFrame)
    assert "event_id" in out.columns
    assert len(out) == 1


def test_df_events_empty_input():
    df = pd.DataFrame(columns=["timestamp", "area", "height", "channel"])
    plugin = GroupedEventsPlugin()
    ctx = DummyContext({"time_window_ns": 100}, {"df": df})

    out = plugin.compute(ctx, "run_001")

    assert isinstance(out, pd.DataFrame)
    assert len(out) == 0
    assert "event_id" in out.columns


def test_df_events_has_expected_metadata():
    plugin = GroupedEventsPlugin()
    assert plugin.provides == "df_events"
    assert plugin.depends_on == ["df"]
    assert plugin.version == "0.0.1"
