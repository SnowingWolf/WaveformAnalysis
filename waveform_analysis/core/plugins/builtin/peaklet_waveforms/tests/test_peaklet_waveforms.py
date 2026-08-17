import numpy as np
import pytest

from tests.utils import DummyContext, make_hit, make_records
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu.peaklets import (
    PEAKLET_WAVEFORMS_DTYPE,
    PeakletComponentsPlugin,
    PeakletPlugin,
    PeakletWaveformPlugin,
    PeakletWaveformPoolPlugin,
)
from waveform_analysis.core.plugins.builtin.hit.hit_finder import THRESHOLD_HIT_DTYPE
from waveform_analysis.core.plugins.builtin.hit.hit_merge import (
    HIT_MERGED_COMPONENTS_DTYPE,
    HIT_MERGED_DTYPE,
)
from waveform_analysis.core.plugins.builtin.peaklet_waveforms.plugin import (
    _process_peaklet_batch,
)
from waveform_analysis.core.plugins.builtin.peaklets.tests.test_peaklets import (
    make_peaklet_context,
)
from waveform_analysis.core.plugins.builtin.peaks.peaklets import (
    PEAKLET_COMPONENTS_DTYPE,
    PEAKLET_DTYPE,
    _build_hmc_csr,
    _build_peaklet_component_csr,
)
from waveform_analysis.core.plugins.builtin.shared.waveform_merge import (
    WaveformOverlapConflictError,
)


def _compute_peaklets_and_components(ctx):
    components = PeakletComponentsPlugin().compute_array(ctx, "run_001")
    ctx._data["peaklet_components"] = components
    peaklets = PeakletPlugin().compute_array(ctx, "run_001")
    ctx._data["peaklets"] = peaklets
    return peaklets, components


def _make_cross_record_waveform_context(*, config=None):
    hits = np.array(
        [
            make_hit(record_id=0, board=0, channel=0, edge_start=3, edge_end=5),
            make_hit(record_id=1, board=0, channel=0, edge_start=2, edge_end=4),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    merged = np.zeros(1, dtype=HIT_MERGED_DTYPE)
    merged[0]["merged_id"] = 0
    merged[0]["time_start"] = 6000
    merged[0]["time_end"] = 12000
    merged[0]["sample_start"] = -1
    merged[0]["sample_end"] = -1
    merged[0]["dt"] = 2
    merged[0]["record_id"] = 0
    merged[0]["component_count"] = 2
    merged[0]["is_single_record"] = False

    hit_merged_components = np.array(
        [(0, 0), (0, 1)],
        dtype=HIT_MERGED_COMPONENTS_DTYPE,
    )
    peaklets = np.array(
        [(6000, 12000, 9000, 2, 1, 0, 1)],
        dtype=PEAKLET_DTYPE,
    )
    components = np.array([(0, 0)], dtype=PEAKLET_COMPONENTS_DTYPE)

    records = make_records(n_records=2, event_length=10, baseline=100.0, dt=2)
    records["timestamp"] = [0, 4000]
    records["polarity"] = "negative"
    wave_pool = np.array(
        [
            100,
            100,
            100,
            80,
            70,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            70,
            50,
            100,
            100,
            100,
            100,
            100,
            100,
        ],
        dtype=np.uint16,
    )
    return DummyContext(
        {
            "use_filtered": False,
            "debug_numba": True,
            "log_waveform_diagnostics": False,
            **(config or {}),
        },
        {
            "hit_threshold": hits,
            "hit_merged": merged,
            "hit_merged_components": hit_merged_components,
            "peaklets": peaklets,
            "peaklet_components": components,
            "records": records,
            "wave_pool": wave_pool,
        },
    )


def _make_all_single_numba_inputs(n_peaklets=6):
    peaklets = np.zeros(n_peaklets, dtype=PEAKLET_DTYPE)
    components = np.zeros(n_peaklets, dtype=PEAKLET_COMPONENTS_DTYPE)
    components["peak_id"] = np.arange(n_peaklets)
    components["merged_index"] = np.arange(n_peaklets)
    merged = np.zeros(n_peaklets, dtype=HIT_MERGED_DTYPE)
    merged["record_id"] = np.arange(n_peaklets)
    merged["board"] = 0
    merged["channel"] = np.arange(n_peaklets)
    merged["sample_start"] = 1
    merged["sample_end"] = 3
    merged["dt"] = 1
    merged["component_count"] = 1
    merged["is_single_record"] = True
    records = make_records(n_records=n_peaklets, event_length=4, baseline=100.0, dt=1)
    records["timestamp"] = np.arange(n_peaklets, dtype=np.int64) * 10_000
    records["polarity"] = "negative"
    wave_pool = np.full(n_peaklets * 4, 100, dtype=np.uint16)
    for record_index in range(n_peaklets):
        offset = record_index * 4
        wave_pool[offset + 1 : offset + 3] = [90, 110]
    return peaklets, components, merged, records, wave_pool


def test_peaklet_waveforms_cross_record_uses_component_hits_from_each_record():
    ctx = _make_cross_record_waveform_context()

    waveforms = PeakletWaveformPlugin().compute(ctx, "run_001")
    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    assert waveforms.dtype == PEAKLET_WAVEFORMS_DTYPE
    assert len(waveforms) == 1
    assert int(waveforms[0]["peak_id"]) == 0
    assert int(waveforms[0]["time_start"]) == 6000
    assert int(waveforms[0]["time_end"]) == 12000
    assert int(waveforms[0]["dt"]) == 2
    assert int(waveforms[0]["wave_offset"]) == 0
    assert int(waveforms[0]["wave_length"]) == 3
    np.testing.assert_allclose(pool, np.array([20.0, 30.0, 50.0], dtype=np.float32))


@pytest.mark.parametrize("clip_negative_signal", [False, True])
def test_peaklet_waveforms_all_single_numba_first_jit_matches_python(clip_negative_signal):
    peaklets, components, merged, records, wave_pool = _make_all_single_numba_inputs()
    plugin = PeakletWaveformPlugin()
    plugin._clip_negative_signal = clip_negative_signal
    plugin._hit_merged_components = np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE)
    plugin._hit_threshold = np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

    numba_waveforms, numba_pool = plugin._build_numba(
        peaklets=peaklets,
        components=components,
        merged=merged,
        records=records,
        wave_pool=wave_pool,
    )
    python_waveforms, python_pool = plugin._build_python(
        peaklets=peaklets,
        components=components,
        merged=merged,
        records=records,
        wave_pool=wave_pool,
    )

    for field in PEAKLET_WAVEFORMS_DTYPE.names:
        np.testing.assert_array_equal(numba_waveforms[field], python_waveforms[field])
    np.testing.assert_array_equal(numba_pool, python_pool)


@pytest.mark.parametrize("clip_negative_signal", [False, True])
def test_peaklet_waveforms_all_single_numba_multichannel_reduction_matches_canonical(
    clip_negative_signal,
):
    peaklets, components, merged, records, _ = _make_all_single_numba_inputs(3)
    peaklets = peaklets[:1]
    components["peak_id"] = 0
    components["merged_index"] = [0, 2, 1]
    merged["channel"] = [0, 2, 1]
    records["timestamp"] = 0
    records["baseline"] = 0.0
    records["polarity"] = "positive"
    wave_pool = np.zeros(12, dtype=np.float32)
    wave_pool[1:3] = np.float32(65535.0)
    wave_pool[5:7] = np.float32(0.09999847)
    wave_pool[9:11] = np.float32(-65535.0)

    plugin = PeakletWaveformPlugin()
    plugin._clip_negative_signal = clip_negative_signal
    plugin._hit_merged_components = np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE)
    plugin._hit_threshold = np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

    numba_waveforms, numba_pool = plugin._build_numba(
        peaklets=peaklets,
        components=components,
        merged=merged,
        records=records,
        wave_pool=wave_pool,
    )
    canonical_waveforms, canonical_pool = plugin._build_python(
        peaklets=peaklets,
        components=components,
        merged=merged,
        records=records,
        wave_pool=wave_pool,
    )

    for field in PEAKLET_WAVEFORMS_DTYPE.names:
        np.testing.assert_array_equal(numba_waveforms[field], canonical_waveforms[field])
    np.testing.assert_array_equal(numba_pool, canonical_pool)


def test_peaklet_waveforms_numba_entry_rejects_off_grid_nonoverlap():
    peaklets, components, merged, records, wave_pool = _make_all_single_numba_inputs(2)
    components["peak_id"] = 0
    records["timestamp"] = [0, 1500]
    merged["sample_start"] = 0
    merged["sample_end"] = 1
    plugin = PeakletWaveformPlugin()
    plugin._clip_negative_signal = False
    plugin._hit_merged_components = np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE)
    plugin._hit_threshold = np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

    with pytest.raises(ValueError, match="common dt grid"):
        plugin._build_numba(
            peaklets=peaklets[:1],
            components=components,
            merged=merged,
            records=records,
            wave_pool=wave_pool,
        )


def test_peaklet_waveforms_numba_entry_rejects_nonfinite_signal():
    peaklets, components, merged, records, wave_pool = _make_all_single_numba_inputs(1)
    records["baseline"] = np.nan
    plugin = PeakletWaveformPlugin()
    plugin._clip_negative_signal = False
    plugin._hit_merged_components = np.zeros(0, dtype=HIT_MERGED_COMPONENTS_DTYPE)
    plugin._hit_threshold = np.zeros(0, dtype=THRESHOLD_HIT_DTYPE)

    with pytest.raises(ValueError, match="non-finite"):
        plugin._build_numba(
            peaklets=peaklets,
            components=components,
            merged=merged,
            records=records,
            wave_pool=wave_pool,
        )


def test_peaklet_waveforms_cross_record_conflicting_overlap_raises():
    ctx = _make_cross_record_waveform_context()
    ctx._data["wave_pool"][12] = 60

    with pytest.raises(WaveformOverlapConflictError, match="abs_time_ps=8000"):
        PeakletWaveformPlugin().compute(ctx, "run_001")


def test_peaklet_waveforms_direct_component_offsets_match_csr_fallback():
    ctx = _make_cross_record_waveform_context()
    plugin = PeakletWaveformPlugin()
    plugin._configure_build(ctx)
    plugin._hit_merged_components = ctx._data["hit_merged_components"]
    plugin._hit_threshold = ctx._data["hit_threshold"]
    merged = ctx._data["hit_merged"]
    kwargs = {
        "peaklets": ctx._data["peaklets"],
        "components": ctx._data["peaklet_components"],
        "is_single_record": merged["is_single_record"],
        "records": ctx._data["records"],
        "wave_pool": ctx._data["wave_pool"],
    }

    direct_waveforms, direct_pool = plugin._build_cross_record_numba(merged=merged, **kwargs)
    fallback_fields = [
        name for name in merged.dtype.names if name not in {"component_offset", "component_count"}
    ]
    fallback_waveforms, fallback_pool = plugin._build_cross_record_numba(
        merged=merged[fallback_fields], **kwargs
    )

    assert direct_waveforms.dtype == PEAKLET_WAVEFORMS_DTYPE
    for field in PEAKLET_WAVEFORMS_DTYPE.names:
        np.testing.assert_array_equal(direct_waveforms[field], fallback_waveforms[field])
    np.testing.assert_array_equal(direct_pool, fallback_pool)


def test_peaklet_waveforms_process_worker_matches_canonical_overlap_result():
    ctx = _make_cross_record_waveform_context()
    expected_waveforms = PeakletWaveformPlugin().compute(ctx, "run_001")
    expected_pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    actual_waveforms, actual_pool = _process_peaklet_batch(
        {
            "peaklets": ctx._data["peaklets"],
            "components": ctx._data["peaklet_components"],
            "merged": ctx._data["hit_merged"],
            "records": ctx._data["records"],
            "wave_pool": ctx._data["wave_pool"],
            "hit_merged_components": ctx._data["hit_merged_components"],
            "hit_threshold": ctx._data["hit_threshold"],
            "clip_negative_signal": False,
        }
    )

    for field in PEAKLET_WAVEFORMS_DTYPE.names:
        np.testing.assert_array_equal(actual_waveforms[field], expected_waveforms[field])
    np.testing.assert_array_equal(actual_pool, expected_pool)


def test_peaklet_waveforms_mix_single_and_cross_record_pieces_in_one_peaklet():
    hits = np.array(
        [
            make_hit(record_id=0, board=0, channel=0, edge_start=3, edge_end=5),
            make_hit(record_id=1, board=0, channel=0, edge_start=2, edge_end=4),
            make_hit(record_id=2, board=0, channel=0, edge_start=1, edge_end=3),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    merged = np.zeros(2, dtype=HIT_MERGED_DTYPE)
    merged[0]["merged_id"] = 0
    merged[0]["time_start"] = 6000
    merged[0]["time_end"] = 10000
    merged[0]["sample_start"] = 3
    merged[0]["sample_end"] = 5
    merged[0]["dt"] = 2
    merged[0]["record_id"] = 0
    merged[0]["component_offset"] = 0
    # A single-record merged row may itself summarize overlapping threshold
    # hits; waveform reconstruction must still read its merged window once.
    merged[0]["component_count"] = 2
    merged[0]["is_single_record"] = True
    merged[1]["merged_id"] = 1
    merged[1]["time_start"] = 8000
    merged[1]["time_end"] = 14000
    merged[1]["sample_start"] = -1
    merged[1]["sample_end"] = -1
    merged[1]["dt"] = 2
    merged[1]["record_id"] = 1
    merged[1]["component_offset"] = 2
    merged[1]["component_count"] = 2
    merged[1]["is_single_record"] = False

    hit_merged_components = np.array(
        [(0, 0), (0, 0), (1, 1), (1, 2)], dtype=HIT_MERGED_COMPONENTS_DTYPE
    )
    peaklets = np.array([(6000, 14000, 10000, 3, 1, 0, 2)], dtype=PEAKLET_DTYPE)
    components = np.array([(0, 0), (0, 1)], dtype=PEAKLET_COMPONENTS_DTYPE)
    records = make_records(n_records=3, event_length=10, baseline=100.0, dt=2)
    records["timestamp"] = [0, 4000, 8000]
    records["polarity"] = "negative"
    wave_pool = np.full(30, 100, dtype=np.uint16)
    wave_pool[[3, 4, 12, 13, 21, 22]] = [80, 70, 70, 50, 50, 80]
    ctx = DummyContext(
        {"use_filtered": False, "debug_numba": True, "log_waveform_diagnostics": False},
        {
            "hit_threshold": hits,
            "hit_merged": merged,
            "hit_merged_components": hit_merged_components,
            "peaklets": peaklets,
            "peaklet_components": components,
            "records": records,
            "wave_pool": wave_pool,
        },
    )

    waveforms = PeakletWaveformPlugin().compute(ctx, "run_001")
    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    assert int(waveforms[0]["time_start"]) == 6000
    assert int(waveforms[0]["time_end"]) == 14000
    assert int(waveforms[0]["wave_length"]) == 4
    np.testing.assert_array_equal(pool, np.array([20.0, 30.0, 50.0, 20.0], dtype=np.float32))


def test_peaklet_waveforms_cross_record_mixed_dt_raises_from_numba_path():
    ctx = _make_cross_record_waveform_context()
    ctx._data["records"]["dt"] = [2, 4]

    with pytest.raises(ValueError, match="mixed dt"):
        PeakletWaveformPlugin().compute(ctx, "run_001")


def test_peaklet_waveforms_debug_numba_raises_instead_of_fallback():
    ctx = _make_cross_record_waveform_context()
    records = ctx._data["records"]
    ctx._data["records"] = records[[name for name in records.dtype.names if name != "dt"]]

    with pytest.raises(KeyError, match="records dt"):
        PeakletWaveformPlugin().compute(ctx, "run_001")


def test_peaklet_waveform_csr_helpers_mark_empty_groups():
    components = np.array([(0, 2), (2, 3), (0, 1)], dtype=PEAKLET_COMPONENTS_DTYPE)
    grouped_merged, starts, ends = _build_peaklet_component_csr(components, 4)

    np.testing.assert_array_equal(grouped_merged, np.array([2, 1, 3], dtype=np.int64))
    np.testing.assert_array_equal(starts, np.array([0, -1, 2, -1], dtype=np.int64))
    np.testing.assert_array_equal(ends, np.array([2, -1, 3, -1], dtype=np.int64))

    hmc = np.array([(1, 4), (0, 2), (1, 5)], dtype=HIT_MERGED_COMPONENTS_DTYPE)
    grouped_hits, hmc_starts, hmc_ends = _build_hmc_csr(hmc, 4)

    np.testing.assert_array_equal(grouped_hits, np.array([2, 4, 5], dtype=np.int64))
    np.testing.assert_array_equal(hmc_starts, np.array([0, 1, -1, -1], dtype=np.int64))
    np.testing.assert_array_equal(hmc_ends, np.array([1, 3, -1, -1], dtype=np.int64))


def test_peaklet_waveforms_align_and_sum_hit_merged_absolute_windows():
    hits = np.array(
        [
            make_hit(record_id=0, board=0, channel=0, edge_start=3, edge_end=5),
            make_hit(record_id=1, board=0, channel=1, edge_start=4, edge_end=6),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    wave_pool = np.array(
        [
            100,
            100,
            100,
            80,
            70,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            90,
            80,
            100,
            100,
            100,
            100,
        ],
        dtype=np.uint16,
    )
    ctx = make_peaklet_context(hits, wave_pool)
    _compute_peaklets_and_components(ctx)

    waveforms = PeakletWaveformPlugin().compute(ctx, "run_001")
    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    assert waveforms.dtype == PEAKLET_WAVEFORMS_DTYPE
    assert len(waveforms) == 1
    assert int(waveforms[0]["time_start"]) == 6000
    assert int(waveforms[0]["time_end"]) == 12000
    assert int(waveforms[0]["dt"]) == 2
    assert int(waveforms[0]["wave_offset"]) == 0
    assert int(waveforms[0]["wave_length"]) == 3
    np.testing.assert_allclose(pool, np.array([20.0, 40.0, 20.0], dtype=np.float32))


def test_peaklet_waveform_pool_reuses_waveforms_memory_result(monkeypatch):
    hits = np.array(
        [
            make_hit(record_id=0, board=0, channel=0, edge_start=3, edge_end=5),
            make_hit(record_id=1, board=0, channel=1, edge_start=4, edge_end=6),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(20, 100, dtype=np.uint16))
    _compute_peaklets_and_components(ctx)

    PeakletWaveformPlugin().compute(ctx, "run_001")
    expected_pool = ctx._results[("run_001", "peaklet_waveform_pool")]

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("peaklet_waveform_pool should reuse memory")

    monkeypatch.setattr(PeakletWaveformPlugin, "_compute_waveforms_and_pool", fail_if_called)

    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    np.testing.assert_array_equal(pool, expected_pool)


def test_peaklet_waveform_pool_lineage_tracks_canonical_waveform(tmp_path):
    ctx = Context(
        config={
            "peaklet_waveforms": {
                "use_filtered": True,
                "clip_negative_signal": True,
            }
        },
        storage_dir=str(tmp_path / "cache"),
    )
    ctx.register(PeakletWaveformPlugin(), PeakletWaveformPoolPlugin())

    lineage = ctx.get_lineage("peaklet_waveform_pool")

    assert lineage["plugin_version"] == "3.0.0"
    assert lineage["config"] == {}
    assert list(lineage["depends_on"]) == ["peaklet_waveforms"]
    waveform_lineage = lineage["depends_on"]["peaklet_waveforms"]
    assert waveform_lineage["plugin_version"] == "2.0.0"
    assert waveform_lineage["config"]["use_filtered"] is True
    assert waveform_lineage["config"]["clip_negative_signal"] is True
    assert "wave_pool_filtered" in waveform_lineage["depends_on"]


def test_peaklet_waveform_pool_key_changes_with_waveform_version(tmp_path):
    def pool_key(version, storage_name, *, use_filtered=False):
        ctx = Context(
            config={"peaklet_waveforms": {"use_filtered": use_filtered}},
            storage_dir=str(tmp_path / storage_name),
        )
        waveform_plugin = PeakletWaveformPlugin()
        waveform_plugin.version = version
        ctx.register(waveform_plugin, PeakletWaveformPoolPlugin())
        return ctx.key_for("run_001", "peaklet_waveform_pool")

    assert pool_key("1.3.1", "current") != pool_key("9.9.9", "changed")
    assert pool_key("1.3.1", "raw") != pool_key("1.3.1", "filtered", use_filtered=True)


def test_peaklet_waveform_pool_cold_build_uses_registered_waveform_config():
    ctx = _make_cross_record_waveform_context(
        config={
            "peaklet_waveforms": {"clip_negative_signal": True},
            "peaklet_waveform_pool": {"clip_negative_signal": False},
        }
    )
    waveform_plugin = PeakletWaveformPlugin()
    ctx._plugins = {"peaklet_waveforms": waveform_plugin}

    with pytest.warns(FutureWarning, match="peaklet_waveforms"):
        pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    assert waveform_plugin._clip_negative_signal is True
    assert len(pool) > 0


def test_peaklet_waveforms_reuses_pool_memory_result(monkeypatch):
    hits = np.array(
        [
            make_hit(record_id=0, board=0, channel=0, edge_start=3, edge_end=5),
            make_hit(record_id=1, board=0, channel=1, edge_start=4, edge_end=6),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(20, 100, dtype=np.uint16))
    _compute_peaklets_and_components(ctx)

    PeakletWaveformPoolPlugin().compute(ctx, "run_001")
    expected_waveforms = ctx._results[("run_001", "peaklet_waveforms")]

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("peaklet_waveforms should reuse memory")

    monkeypatch.setattr(PeakletWaveformPlugin, "_compute_waveforms_and_pool", fail_if_called)

    waveforms = PeakletWaveformPlugin().compute(ctx, "run_001")

    np.testing.assert_array_equal(waveforms, expected_waveforms)


def test_peaklet_waveforms_reject_components_misaligned_with_peaklets():
    hits = np.array(
        [
            make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=3),
            make_hit(record_id=1, board=0, channel=1, edge_start=1, edge_end=3),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(20, 100, dtype=np.uint16))
    peaklets, components = _compute_peaklets_and_components(ctx)
    assert int(peaklets[0]["component_count"]) == 2
    ctx._data["peaklet_components"] = components[:1]

    with pytest.raises(ValueError, match="inconsistent with peaklets"):
        PeakletWaveformPlugin().compute(ctx, "run_001")


def test_peaklet_waveforms_preserve_signed_signal_after_polarity_conversion_by_default():
    hits = np.array(
        [
            make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=4),
            make_hit(record_id=1, board=0, channel=1, edge_start=1, edge_end=4),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    wave_pool = np.array(
        [
            100,
            80,
            130,
            70,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            120,
            80,
            140,
            100,
            100,
            100,
            100,
            100,
            100,
        ],
        dtype=np.uint16,
    )
    ctx = make_peaklet_context(hits, wave_pool)
    ctx._data["records"]["polarity"] = ["negative", "positive"]
    _compute_peaklets_and_components(ctx)

    PeakletWaveformPlugin().compute(ctx, "run_001")
    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    np.testing.assert_allclose(pool, np.array([40.0, -50.0, 70.0], dtype=np.float32))


def test_peaklet_waveforms_can_clip_negative_signal_for_compatibility():
    hits = np.array(
        [
            make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=4),
            make_hit(record_id=1, board=0, channel=1, edge_start=1, edge_end=4),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    wave_pool = np.array(
        [
            100,
            80,
            130,
            70,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            120,
            80,
            140,
            100,
            100,
            100,
            100,
            100,
            100,
        ],
        dtype=np.uint16,
    )
    ctx = make_peaklet_context(hits, wave_pool)
    ctx.config["clip_negative_signal"] = True
    ctx._data["records"]["polarity"] = ["negative", "positive"]
    _compute_peaklets_and_components(ctx)

    PeakletWaveformPlugin().compute(ctx, "run_001")
    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    np.testing.assert_allclose(pool, np.array([40.0, 0.0, 70.0], dtype=np.float32))


def test_peaklet_waveforms_use_filtered_pool_when_configured():
    hits = np.array(
        [make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=3)],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(10, 100, dtype=np.uint16), use_filtered=True)
    ctx._data["wave_pool_filtered"] = np.array(
        [100, 50, 40, 100, 100, 100, 100, 100, 100, 100], dtype=np.uint16
    )
    _compute_peaklets_and_components(ctx)

    PeakletWaveformPlugin().compute(ctx, "run_001")
    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    np.testing.assert_allclose(pool, np.array([50.0, 60.0], dtype=np.float32))


def test_peaklet_waveforms_mixed_dt_in_one_peaklet_raises():
    hits = np.array(
        [
            make_hit(record_id=0, board=0, channel=0, edge_start=1, edge_end=3, dt=2),
            make_hit(record_id=1, board=0, channel=1, edge_start=1, edge_end=3, dt=4),
        ],
        dtype=THRESHOLD_HIT_DTYPE,
    )
    ctx = make_peaklet_context(hits, np.full(20, 90, dtype=np.uint16), time_window_ns=10.0)
    ctx._data["records"]["dt"] = [2, 4]
    _compute_peaklets_and_components(ctx)

    with pytest.raises(ValueError, match="mixed dt"):
        PeakletWaveformPlugin().compute(ctx, "run_001")


def test_peaklet_waveforms_empty_peaklets_return_empty_index_and_pool():
    ctx = make_peaklet_context(
        np.zeros(0, dtype=THRESHOLD_HIT_DTYPE),
        np.zeros(0, dtype=np.uint16),
    )
    ctx._data["peaklet_components"] = PeakletComponentsPlugin().compute_array(ctx, "run_001")
    ctx._data["peaklets"] = PeakletPlugin().compute_array(ctx, "run_001")

    waveforms = PeakletWaveformPlugin().compute(ctx, "run_001")
    pool = PeakletWaveformPoolPlugin().compute(ctx, "run_001")

    assert len(waveforms) == 0
    assert waveforms.dtype == PEAKLET_WAVEFORMS_DTYPE
    assert pool.dtype == np.float32
    assert len(pool) == 0
