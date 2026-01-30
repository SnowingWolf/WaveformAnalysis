import numpy as np

from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.cpu.events import (
    EventFramePlugin,
    EventsGroupedPlugin,
    EventsPlugin,
)
from waveform_analysis.core.processing.records_builder import EVENTS_DTYPE, RecordsBundle


def _seed_events_bundle(ctx, run_id):
    records = np.zeros(2, dtype=EVENTS_DTYPE)
    records["timestamp"] = [100, 200]
    records["pid"] = 0
    records["channel"] = [0, 1]
    records["baseline"] = [10.0, 5.0]
    records["event_id"] = [0, 1]
    records["dt"] = [1, 1]
    records["trigger_type"] = 0
    records["flags"] = 0
    records["wave_offset"] = [0, 3]
    records["event_length"] = [3, 2]
    records["time"] = [0, 0]

    wave_pool = np.array([8, 9, 10, 1, 2], dtype=np.uint16)
    bundle = RecordsBundle(records=records, wave_pool=wave_pool)
    cache_key = f"_events_bundle-{ctx.key_for(run_id, 'events')}"
    ctx._results[(run_id, cache_key)] = bundle


def test_event_frame_plugin_basic_features():
    run_id = "run_001"
    ctx = FakeContext(
        config={"peaks_range": (0, None), "charge_range": (0, None)},
        plugins={"events": EventsPlugin()},
    )
    _seed_events_bundle(ctx, run_id)

    plugin = EventFramePlugin()
    df = plugin.compute(ctx, run_id)

    assert list(df["timestamp"]) == [100, 200]
    assert list(df["channel"]) == [0, 1]
    assert list(df["event_id"]) == [0, 1]

    assert np.allclose(df["height"].to_numpy(), np.array([2.0, 1.0]))
    assert np.allclose(df["area"].to_numpy(), np.array([3.0, 7.0]))


def test_events_grouped_plugin_chain():
    run_id = "run_002"
    ctx = FakeContext(
        config={"events_grouped.time_window_ns": 0.05},
        plugins={"events": EventsPlugin()},
    )
    _seed_events_bundle(ctx, run_id)

    # Manually compute events_df first since FakeContext doesn't auto-resolve
    events_df_plugin = EventFramePlugin()
    events_df = events_df_plugin.compute(ctx, run_id)
    ctx._results[(run_id, "events_df")] = events_df

    plugin = EventsGroupedPlugin()
    df_events = plugin.compute(ctx, run_id)

    assert (run_id, "events_df") in ctx._results
    assert len(df_events) == 2
    assert list(df_events["n_hits"]) == [1, 1]
    assert list(df_events["channels"].iloc[0]) == [0]
    assert list(df_events["channels"].iloc[1]) == [1]
