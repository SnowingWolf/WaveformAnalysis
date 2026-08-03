import matplotlib

matplotlib.use("Agg")

import numpy as np
import pytest

from tests.utils import make_records_view
from waveform_analysis.utils.preview import plot_records_waveforms


def test_plot_records_waveforms_accepts_explicit_record_ids():
    rv = make_records_view(
        n_records=3,
        record_id=[101, 102, 103],
        timestamp=[1000, 2000, 3000],
        channel=[1, 1, 2],
        polarity="negative",
        dt=2,
        wave_pool=np.array(
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
        ),
    )

    with pytest.warns(DeprecationWarning, match="plot_records_waveforms"):
        fig = plot_records_waveforms(rv, record_ids=[102, 101], ncols=1)

    assert fig is not None
    assert fig.axes[0].get_title() == "Record 102"
    assert fig.axes[1].get_title() == "Record 101"
    assert "height=15.00" in fig.axes[0].texts[0].get_text()
    assert "area=35.00" in fig.axes[0].texts[0].get_text()


def test_plot_records_waveforms_supports_feature_filters():
    rv = make_records_view(
        n_records=3,
        record_id=[101, 102, 103],
        timestamp=[1000, 2000, 3000],
        channel=[1, 1, 2],
        polarity="negative",
        dt=2,
        wave_pool=np.array(
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
        ),
    )

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
    rv = make_records_view(
        n_records=3,
        record_id=[101, 102, 103],
        timestamp=[1000, 2000, 3000],
        channel=[1, 1, 2],
        polarity="negative",
        dt=2,
        wave_pool=np.array(
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
        ),
    )

    with pytest.warns(DeprecationWarning, match="plot_records_waveforms"):
        fig = plot_records_waveforms(rv, channel=9)

    assert fig is not None
    assert fig.axes[0].texts[0].get_text() == "No records matched the query"
