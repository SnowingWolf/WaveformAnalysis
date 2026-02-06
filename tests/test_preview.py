import logging

import matplotlib
import numpy as np

matplotlib.use("Agg")

from waveform_analysis.core.processing.dtypes import ST_WAVEFORM_DTYPE
from waveform_analysis.utils.preview import WaveformPreviewer


def _make_waveforms(n_events: int = 3) -> np.ndarray:
    waveforms = np.zeros(n_events, dtype=ST_WAVEFORM_DTYPE)
    waveforms["baseline"] = 0.0
    waveforms["timestamp"] = np.arange(n_events, dtype=np.int64)
    waveforms["channel"] = 0
    waveforms["wave"][:, 10] = -5
    return waveforms


def test_compute_features_handles_out_of_bounds_ranges(caplog):
    previewer = WaveformPreviewer(run_name="dummy", data_root="DAQ", n_channels=1)
    waveforms = _make_waveforms()

    with caplog.at_level(logging.WARNING):
        features = previewer.compute_features(
            waveforms, peaks_range=(2000, 2100), charge_range=(2000, 2100)
        )

    assert np.isnan(features["peaks"]).all()
    assert np.isnan(features["charges"]).all()
    assert np.isnan(features["peak_positions"]).all()
    assert any("peaks_range" in rec.message for rec in caplog.records)
    assert any("charge_range" in rec.message for rec in caplog.records)


def test_plot_grid_skips_missing_peaks():
    previewer = WaveformPreviewer(run_name="dummy", data_root="DAQ", n_channels=1)
    waveforms = _make_waveforms()
    fig = previewer.plot_grid(
        waveforms, annotate=True, peaks_range=(2000, 2100), charge_range=(2000, 2100)
    )
    assert fig is not None


def test_plot_overlay_skips_missing_peaks():
    previewer = WaveformPreviewer(run_name="dummy", data_root="DAQ", n_channels=1)
    waveforms = _make_waveforms()
    fig = previewer.plot_overlay(
        waveforms, annotate=True, peaks_range=(2000, 2100), charge_range=(2000, 2100)
    )
    assert fig is not None
