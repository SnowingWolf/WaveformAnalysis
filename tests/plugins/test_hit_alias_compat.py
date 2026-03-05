import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.builtin.cpu import HitFinderPlugin, SignalPeaksPlugin
from waveform_analysis.core.processing.dtypes import create_record_dtype


def _make_st_waveforms() -> np.ndarray:
    dtype = create_record_dtype(128)
    st_waveforms = np.zeros(1, dtype=dtype)
    wave = np.ones(128, dtype=np.int16) * 100
    wave[48:56] = 40
    st_waveforms[0]["wave"] = wave
    st_waveforms[0]["baseline"] = 100.0
    st_waveforms[0]["timestamp"] = 100_000
    st_waveforms[0]["event_length"] = 128
    st_waveforms[0]["channel"] = 0
    return st_waveforms


def test_signal_peaks_plugin_alias_deprecated():
    with pytest.warns(DeprecationWarning, match="SignalPeaksPlugin"):
        plugin = SignalPeaksPlugin()
    assert plugin.provides == "hit"


def test_hit_plugin_supports_signal_peaks_compat_name(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(HitFinderPlugin())

    run_id = "run_compat_signal_peaks"
    ctx._results[(run_id, "st_waveforms")] = _make_st_waveforms()

    with pytest.warns(DeprecationWarning, match="signal_peaks"):
        ctx.set_config(
            {
                "use_filtered": False,
                "use_derivative": False,
                "height": 5.0,
                "distance": 1,
                "prominence": 1.0,
                "width": 1,
            },
            plugin_name="signal_peaks",
        )

    plugin = ctx.get_plugin("hit")
    assert ctx.get_config(plugin, "height") == 5.0

    data_hit = ctx.get_data(run_id, "hit")
    with pytest.warns(DeprecationWarning, match="signal_peaks"):
        data_signal_peaks = ctx.get_data(run_id, "signal_peaks")

    assert isinstance(data_hit, np.ndarray)
    np.testing.assert_array_equal(data_hit, data_signal_peaks)


def test_stale_signal_peaks_alias_cache_does_not_bypass_recompute(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(HitFinderPlugin())

    run_id = "run_stale_alias_cache"
    ctx._results[(run_id, "st_waveforms")] = _make_st_waveforms()

    # Compute a canonical result first (has valid lineage for "hit")
    ctx.set_config(
        {
            "use_filtered": False,
            "use_derivative": False,
            "height": 5.0,
            "distance": 1,
            "prominence": 1.0,
            "width": 1,
        },
        plugin_name="hit",
    )
    data_old = ctx.get_data(run_id, "hit")
    assert len(data_old) > 0

    # Simulate legacy in-memory alias cache without lineage metadata
    ctx._results[(run_id, "signal_peaks")] = data_old.copy()

    # Force canonical cache miss so fallback path is exercised
    ctx._results.pop((run_id, "hit"), None)
    ctx._results_lineage.pop((run_id, "hit"), None)

    # Change config so recompute should produce a different result
    ctx.set_config({"height": 1e6}, plugin_name="hit")
    data_new = ctx.get_data(run_id, "hit")

    assert len(data_new) == 0
