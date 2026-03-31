import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

from waveform_analysis.utils.preview import WaveformPreviewer

PREVIEW_DTYPE = np.dtype(
    [
        ("baseline", "f8"),
        ("timestamp", "i8"),
        ("channel", "i2"),
        ("wave", "i2", (16,)),
    ]
)


def _make_waveforms():
    data = np.zeros(1, dtype=PREVIEW_DTYPE)
    data["baseline"] = 100.0
    data["timestamp"] = 123456
    data["channel"] = 2
    data[0]["wave"] = np.array(
        [100, 100, 95, 80, 60, 80, 95, 100, 100, 100, 100, 100, 100, 100, 100, 100]
    )
    return data


def test_plot_overlay_accepts_dt():
    previewer = WaveformPreviewer("run_001")
    fig = previewer.plot_overlay(_make_waveforms(), annotate=False, dt=1.5)
    ax = fig.axes[0]
    assert ax.lines[0].get_xdata()[1] == pytest.approx(1.5)


def test_plot_grid_accepts_deprecated_sampling_interval_ns_with_warning():
    previewer = WaveformPreviewer("run_001")
    with pytest.warns(DeprecationWarning, match="sampling_interval_ns"):
        fig = previewer.plot_grid(
            _make_waveforms(),
            annotate=False,
            sampling_interval_ns=3.0,
        )
    ax = fig.axes[0]
    assert ax.lines[0].get_xdata()[1] == pytest.approx(3.0)
