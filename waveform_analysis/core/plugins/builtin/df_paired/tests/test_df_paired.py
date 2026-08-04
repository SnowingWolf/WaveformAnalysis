import pandas as pd

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.df_paired import PairedEventsPlugin


def _grouped_events_frame():
    return pd.DataFrame(
        {
            "event_id": [0, 1],
            "timestamp": [1000000, 2000000],
            "timestamps": [[1000000, 1000010], [2000000, 2000010]],
            "dt/ns": [50.0, 50.0],
            "areas": [[100, 200], [300, 400]],
            "heights": [[10, 20], [30, 40]],
            "n_hits": [2, 2],
        }
    )


def test_df_paired_filters_within_time_window():
    df_events = _grouped_events_frame()
    plugin = PairedEventsPlugin()
    ctx = DummyContext(
        {"n_channels": 2, "start_channel_slice": 6, "time_window_ns": 100.0},
        {"df_events": df_events},
    )

    out = plugin.compute(ctx, "run_001")

    assert isinstance(out, pd.DataFrame)
    assert len(out) == 2
    assert "delta_t" in out.columns


def test_df_paired_excludes_events_over_time_window():
    df_events = _grouped_events_frame()
    plugin = PairedEventsPlugin()
    # 窗口小于事件 dt/ns=50，应当排除全部事件
    ctx = DummyContext(
        {"n_channels": 2, "start_channel_slice": 6, "time_window_ns": 10.0},
        {"df_events": df_events},
    )

    out = plugin.compute(ctx, "run_001")

    assert isinstance(out, pd.DataFrame)
    assert len(out) == 0


def test_df_paired_has_expected_metadata():
    plugin = PairedEventsPlugin()
    assert plugin.provides == "df_paired"
    assert plugin.depends_on == ["df_events"]
    assert plugin.version == "0.0.1"
