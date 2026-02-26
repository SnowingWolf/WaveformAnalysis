import numpy as np
import pytest

from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.cpu.events import (
    EventFramePlugin,
    EventsGroupedPlugin,
    EventsPlugin,
    _cleanup_stale_bundles,
    _coerce_range,
    _compute_event_features,
    _flatten_raw_files,
    _resolve_adapter_name,
    _resolve_dt_ns,
    _slice_bounds,
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

    assert np.allclose(df["height"].to_numpy(), np.array([2.0, 4.0]))
    assert np.allclose(df["amp"].to_numpy(), np.array([2.0, 1.0]))
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


def test_event_frame_plugin_fixed_baseline():
    """Verify fixed_baseline overrides dynamic baseline in EventFramePlugin."""
    run_id = "run_fb"
    ctx = FakeContext(
        config={
            "peaks_range": (0, None),
            "charge_range": (0, None),
            "events_df.fixed_baseline": {0: 20.0, 1: 10.0},
        },
        plugins={"events": EventsPlugin()},
    )
    _seed_events_bundle(ctx, run_id)

    plugin = EventFramePlugin()
    df = plugin.compute(ctx, run_id)

    # Record 0: ch=0, baseline overridden to 20.0, wave=[8,9,10]
    #   height = 20 - 8 = 12, amp = 10 - 8 = 2, area = (20-8)+(20-9)+(20-10) = 33
    # Record 1: ch=1, baseline overridden to 10.0, wave=[1,2]
    #   height = 10 - 1 = 9, amp = 2 - 1 = 1, area = (10-1)+(10-2) = 17
    assert np.allclose(df["height"].to_numpy(), np.array([12.0, 9.0]))
    assert np.allclose(df["amp"].to_numpy(), np.array([2.0, 1.0]))
    assert np.allclose(df["area"].to_numpy(), np.array([33.0, 17.0]))


def test_compute_event_features_fixed_baseline_partial():
    """Verify fixed_baseline only affects specified channels."""
    records = np.zeros(2, dtype=EVENTS_DTYPE)
    records["channel"] = [0, 1]
    records["baseline"] = [10.0, 5.0]
    records["wave_offset"] = [0, 3]
    records["event_length"] = [3, 2]

    wave_pool = np.array([8, 9, 10, 1, 2], dtype=np.uint16)

    # Only override channel 0
    heights, amps, areas = _compute_event_features(
        records, wave_pool,
        peaks_range=(0, None),
        charge_range=(0, None),
        fixed_baseline={0: 20.0},
    )

    # ch0: baseline=20 -> height=20-8=12, area=(20-8)+(20-9)+(20-10)=33
    # ch1: baseline=5 (unchanged) -> height=5-1=4, area=(5-1)+(5-2)=7
    assert np.allclose(heights, [12.0, 4.0])
    assert np.allclose(areas, [33.0, 7.0])


# ---------------------------------------------------------------------------
# Parametrized: _compute_event_features baseline scenarios
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixed_baseline,expected_heights,expected_areas", [
    (None, [2.0, 4.0], [3.0, 7.0]),
    ({0: 20.0}, [12.0, 4.0], [33.0, 7.0]),
    ({0: 20.0, 1: 10.0}, [12.0, 9.0], [33.0, 17.0]),
])
def test_compute_event_features_baselines_parametrized(
    fixed_baseline, expected_heights, expected_areas
):
    records = np.zeros(2, dtype=EVENTS_DTYPE)
    records["channel"] = [0, 1]
    records["baseline"] = [10.0, 5.0]
    records["wave_offset"] = [0, 3]
    records["event_length"] = [3, 2]
    wave_pool = np.array([8, 9, 10, 1, 2], dtype=np.uint16)

    heights, amps, areas = _compute_event_features(
        records, wave_pool,
        peaks_range=(0, None),
        charge_range=(0, None),
        fixed_baseline=fixed_baseline,
    )
    np.testing.assert_allclose(heights, expected_heights)
    np.testing.assert_allclose(areas, expected_areas)


# ---------------------------------------------------------------------------
# _compute_event_features edge cases
# ---------------------------------------------------------------------------


class TestComputeEventFeaturesEdgeCases:
    def test_empty_records(self):
        records = np.zeros(0, dtype=EVENTS_DTYPE)
        wave_pool = np.array([], dtype=np.uint16)
        heights, amps, areas = _compute_event_features(
            records, wave_pool, peaks_range=(0, None), charge_range=(0, None),
        )
        assert len(heights) == 0
        assert len(amps) == 0
        assert len(areas) == 0

    def test_zero_event_length_skipped(self):
        records = np.zeros(1, dtype=EVENTS_DTYPE)
        records["event_length"] = 0
        records["baseline"] = 100.0
        wave_pool = np.array([50, 60], dtype=np.uint16)

        heights, amps, areas = _compute_event_features(
            records, wave_pool, peaks_range=(0, None), charge_range=(0, None),
        )
        assert heights[0] == 0.0
        assert amps[0] == 0.0
        assert areas[0] == 0.0

    def test_single_sample_event(self):
        records = np.zeros(1, dtype=EVENTS_DTYPE)
        records["event_length"] = 1
        records["wave_offset"] = 0
        records["baseline"] = 100.0
        wave_pool = np.array([80], dtype=np.uint16)

        heights, amps, areas = _compute_event_features(
            records, wave_pool, peaks_range=(0, None), charge_range=(0, None),
        )
        assert np.isclose(heights[0], 20.0)  # 100 - 80
        assert np.isclose(amps[0], 0.0)      # 80 - 80
        assert np.isclose(areas[0], 20.0)    # 100 - 80


# ---------------------------------------------------------------------------
# EventsPlugin.resolve_depends_on
# ---------------------------------------------------------------------------


class TestEventsPluginResolveDependsOn:
    def test_default_depends_on_st_waveforms(self):
        ctx = FakeContext(config={})
        plugin = EventsPlugin()
        assert plugin.resolve_depends_on(ctx) == ["st_waveforms"]

    def test_v1725_adapter_depends_on_raw_files(self):
        ctx = FakeContext(config={"daq_adapter": "v1725"})
        plugin = EventsPlugin()
        assert plugin.resolve_depends_on(ctx) == ["raw_files"]

    def test_use_filtered_depends_on_filtered(self):
        ctx = FakeContext(config={"use_filtered": True})
        plugin = EventsPlugin()
        assert plugin.resolve_depends_on(ctx) == ["filtered_waveforms"]

    def test_v1725_overrides_use_filtered(self):
        """v1725 adapter takes priority over use_filtered."""
        ctx = FakeContext(config={"daq_adapter": "v1725", "use_filtered": True})
        plugin = EventsPlugin()
        assert plugin.resolve_depends_on(ctx) == ["raw_files"]


# __CONTINUE_EVENTS__


# ---------------------------------------------------------------------------
# EventsPlugin.get_lineage
# ---------------------------------------------------------------------------


class TestEventsPluginGetLineage:
    def test_lineage_without_adapter(self):
        ctx = FakeContext(config={})
        plugin = EventsPlugin()
        lineage = plugin.get_lineage(ctx)

        assert lineage["plugin_class"] == "EventsPlugin"
        assert lineage["plugin_version"] == "2.0.0"
        assert "daq_adapter" not in lineage["config"]

    def test_lineage_with_adapter(self):
        ctx = FakeContext(config={"daq_adapter": "vx2730"})
        plugin = EventsPlugin()
        lineage = plugin.get_lineage(ctx)

        assert lineage["config"]["daq_adapter"] == "vx2730"


# ---------------------------------------------------------------------------
# EventFramePlugin: include_event_id=False
# ---------------------------------------------------------------------------


class TestEventFrameIncludeEventId:
    def test_include_event_id_true(self):
        run_id = "run_eid"
        ctx = FakeContext(
            config={"peaks_range": (0, None), "charge_range": (0, None)},
            plugins={"events": EventsPlugin()},
        )
        _seed_events_bundle(ctx, run_id)
        plugin = EventFramePlugin()
        df = plugin.compute(ctx, run_id)
        assert "event_id" in df.columns

    def test_include_event_id_false(self):
        run_id = "run_no_eid"
        ctx = FakeContext(
            config={
                "peaks_range": (0, None),
                "charge_range": (0, None),
                "events_df.include_event_id": False,
            },
            plugins={"events": EventsPlugin()},
        )
        _seed_events_bundle(ctx, run_id)
        plugin = EventFramePlugin()
        df = plugin.compute(ctx, run_id)
        assert "event_id" not in df.columns


# ---------------------------------------------------------------------------
# _flatten_raw_files
# ---------------------------------------------------------------------------


class TestFlattenRawFiles:
    def test_basic_flatten(self):
        raw = [["a.csv", "b.csv"], ["c.csv"]]
        assert _flatten_raw_files(raw) == ["a.csv", "b.csv", "c.csv"]

    def test_deduplication(self):
        raw = [["a.csv", "b.csv"], ["b.csv", "c.csv"]]
        assert _flatten_raw_files(raw) == ["a.csv", "b.csv", "c.csv"]

    def test_empty_groups(self):
        raw = [[], ["a.csv"], [], ["b.csv"]]
        assert _flatten_raw_files(raw) == ["a.csv", "b.csv"]

    def test_all_empty(self):
        assert _flatten_raw_files([[], [], []]) == []

    def test_none_groups_skipped(self):
        raw = [None, ["a.csv"], None]
        assert _flatten_raw_files(raw) == ["a.csv"]


# __CONTINUE_EVENTS_2__


# ---------------------------------------------------------------------------
# _cleanup_stale_bundles
# ---------------------------------------------------------------------------


class TestCleanupStaleBundles:
    def test_removes_old_bundles(self):
        ctx = FakeContext(config={}, plugins={"events": EventsPlugin()})
        run_id = "run_clean"
        keep_key = "_events_bundle-current"

        # Seed a stale bundle and the current one
        stale_bundle = RecordsBundle(
            records=np.zeros(0, dtype=EVENTS_DTYPE),
            wave_pool=np.array([], dtype=np.uint16),
        )
        ctx._results[(run_id, "_events_bundle-old")] = stale_bundle
        ctx._results[(run_id, keep_key)] = stale_bundle
        ctx._results[(run_id, "other_data")] = "not a bundle"

        _cleanup_stale_bundles(ctx, run_id, keep_key)

        assert (run_id, keep_key) in ctx._results
        assert (run_id, "_events_bundle-old") not in ctx._results
        assert (run_id, "other_data") in ctx._results  # non-bundle untouched

    def test_no_stale_bundles(self):
        ctx = FakeContext(config={})
        run_id = "run_ok"
        keep_key = "_events_bundle-current"
        ctx._results[(run_id, keep_key)] = RecordsBundle(
            records=np.zeros(0, dtype=EVENTS_DTYPE),
            wave_pool=np.array([], dtype=np.uint16),
        )
        _cleanup_stale_bundles(ctx, run_id, keep_key)
        assert (run_id, keep_key) in ctx._results

    def test_different_run_id_untouched(self):
        ctx = FakeContext(config={})
        bundle = RecordsBundle(
            records=np.zeros(0, dtype=EVENTS_DTYPE),
            wave_pool=np.array([], dtype=np.uint16),
        )
        ctx._results[("other_run", "_events_bundle-x")] = bundle
        _cleanup_stale_bundles(ctx, "run_001", "_events_bundle-y")
        assert ("other_run", "_events_bundle-x") in ctx._results


# ---------------------------------------------------------------------------
# _coerce_range
# ---------------------------------------------------------------------------


class TestCoerceRange:
    def test_none_uses_default(self):
        assert _coerce_range(None, (10, 20)) == (10, 20)

    def test_explicit_value(self):
        assert _coerce_range((5, 15), (10, 20)) == (5, 15)

    def test_none_end(self):
        assert _coerce_range((0, None), (10, 20)) == (0, None)

    def test_none_start_becomes_zero(self):
        assert _coerce_range((None, 10), (0, 20)) == (0, 10)

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError, match="range must be a tuple"):
            _coerce_range((1, 2, 3), (0, 10))


# ---------------------------------------------------------------------------
# _slice_bounds
# ---------------------------------------------------------------------------


class TestSliceBounds:
    def test_normal(self):
        assert _slice_bounds(100, 10, 50) == (10, 50)

    def test_end_none(self):
        assert _slice_bounds(100, 0, None) == (0, 100)

    def test_end_exceeds_length(self):
        assert _slice_bounds(50, 0, 100) == (0, 50)

    def test_negative_start_clamped(self):
        assert _slice_bounds(100, -5, 50) == (0, 50)

    def test_start_exceeds_length(self):
        assert _slice_bounds(10, 20, 30) == (10, 10)


# ---------------------------------------------------------------------------
# _resolve_adapter_name
# ---------------------------------------------------------------------------


class TestResolveAdapterName:
    def test_string_adapter(self):
        ctx = FakeContext(config={"daq_adapter": "VX2730"})
        assert _resolve_adapter_name(ctx) == "vx2730"

    def test_none_adapter(self):
        ctx = FakeContext(config={})
        assert _resolve_adapter_name(ctx) is None

    def test_non_string_adapter(self):
        ctx = FakeContext(config={"daq_adapter": 123})
        assert _resolve_adapter_name(ctx) is None


# __CONTINUE_EVENTS_3__


# ---------------------------------------------------------------------------
# _resolve_dt_ns
# ---------------------------------------------------------------------------


class TestResolveDtNs:
    def test_explicit_config(self):
        ctx = FakeContext(config={"events_dt_ns": 2})
        plugin = EventsPlugin()
        assert _resolve_dt_ns(ctx, plugin) == 2

    def test_fallback_to_one(self):
        ctx = FakeContext(config={})
        plugin = EventsPlugin()
        assert _resolve_dt_ns(ctx, plugin) == 1

    def test_negative_raises(self):
        ctx = FakeContext(config={"events_dt_ns": -1})
        plugin = EventsPlugin()
        with pytest.raises(ValueError, match="out of int32 range"):
            _resolve_dt_ns(ctx, plugin)

    def test_overflow_raises(self):
        ctx = FakeContext(config={"events_dt_ns": int(np.iinfo(np.int32).max) + 1})
        plugin = EventsPlugin()
        with pytest.raises(ValueError, match="out of int32 range"):
            _resolve_dt_ns(ctx, plugin)

    def test_adapter_name_fallback(self):
        """When events_dt_ns is None and adapter lookup fails, falls back to 1."""
        ctx = FakeContext(config={"daq_adapter": "nonexistent_adapter"})
        plugin = EventsPlugin()
        # Should not raise, falls back to 1
        assert _resolve_dt_ns(ctx, plugin) == 1


# ---------------------------------------------------------------------------
# Parametrized: _slice_bounds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("length,start,end,expected", [
    (100, 10, 50, (10, 50)),
    (100, 0, None, (0, 100)),
    (50, 0, 100, (0, 50)),
    (100, -5, 50, (0, 50)),
    (10, 20, 30, (10, 10)),
    (0, 0, None, (0, 0)),
])
def test_slice_bounds_parametrized(length, start, end, expected):
    assert _slice_bounds(length, start, end) == expected
