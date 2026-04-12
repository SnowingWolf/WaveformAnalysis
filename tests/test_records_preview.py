import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

from waveform_analysis.core.data import RecordsView
from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE
from waveform_analysis.utils.preview import plot_records_waveforms


def _make_records_view() -> RecordsView:
    records = np.zeros(3, dtype=RECORDS_DTYPE)
    records["record_id"] = np.array([101, 102, 103], dtype=np.int64)
    records["timestamp"] = np.array([1000, 2000, 3000], dtype=np.int64)
    records["board"] = 0
    records["channel"] = np.array([1, 1, 2], dtype=np.int16)
    records["baseline"] = 100.0
    records["polarity"] = "negative"
    records["dt"] = 2
    records["wave_offset"] = np.array([0, 8, 16], dtype=np.int64)
    records["event_length"] = 8

    wave_pool = np.array(
        [
            100,
            100,
            95,
            70,
            95,
            100,
            100,
            100,
            100,
            100,
            90,
            85,
            90,
            100,
            100,
            100,
            100,
            100,
            99,
            98,
            99,
            100,
            100,
            100,
        ],
        dtype=np.int16,
    )
    return RecordsView(records, wave_pool)


def test_plot_records_waveforms_accepts_explicit_record_ids():
    rv = _make_records_view()

    with pytest.warns(DeprecationWarning, match="plot_records_waveforms"):
        fig = plot_records_waveforms(rv, record_ids=[102, 101], ncols=1)

    assert fig is not None
    assert fig.axes[0].get_title() == "Record 102"
    assert fig.axes[1].get_title() == "Record 101"
    assert "height=15.00" in fig.axes[0].texts[0].get_text()
    assert "area=35.00" in fig.axes[0].texts[0].get_text()


def test_plot_records_waveforms_supports_feature_filters():
    rv = _make_records_view()

    with pytest.warns(DeprecationWarning, match="plot_records_waveforms"):
        fig = plot_records_waveforms(
            rv,
            channel=1,
            height_range=(20.0, 40.0),
            area_range=(30.0, 80.0),
            ncols=1,
        )

    visible_axes = [ax for ax in fig.axes if ax.axison]
    assert len(visible_axes) == 1
    assert visible_axes[0].get_title() == "Record 101"


def test_plot_records_waveforms_handles_empty_query():
    rv = _make_records_view()

    with pytest.warns(DeprecationWarning, match="plot_records_waveforms"):
        fig = plot_records_waveforms(rv, channel=9)

    assert fig is not None
    assert fig.axes[0].texts[0].get_text() == "No records matched the query"
