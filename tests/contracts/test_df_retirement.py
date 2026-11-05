"""The retired builtin table chain must not leak through facades or cached requests."""

import importlib

import pytest

from waveform_analysis import Context, group_multi_channel_hits
from waveform_analysis.core.processing import EventAnalyzer


@pytest.mark.parametrize(
    "module_name",
    [
        "waveform_analysis.plugins",
        "waveform_analysis.core.plugins",
        "waveform_analysis.core.plugins.builtin",
        "waveform_analysis.core.plugins.builtin.cpu",
        "waveform_analysis.core.plugins.builtin.cpu.standard",
    ],
)
def test_retired_classes_are_absent_from_public_facades(module_name):
    module = importlib.import_module(module_name)
    for name in ("DataFramePlugin", "GroupedEventsPlugin", "PairedEventsPlugin"):
        assert name not in module.__all__
        with pytest.raises(AttributeError):
            getattr(module, name)


@pytest.mark.parametrize(
    "data_name", ["df", "df_events", "df_paired", "events_df", "events_grouped"]
)
def test_retired_requests_reject_even_an_existing_memory_result(tmp_path, data_name):
    ctx = Context(storage_dir=str(tmp_path))
    ctx._results[("run_001", data_name)] = object()
    with pytest.raises(ValueError, match=f"Data name '{data_name}' has been removed") as caught:
        ctx.get_data("run_001", data_name)
    assert "docs/user-guide/DF_RETIREMENT.md" in str(caught.value)


def test_independent_dataframe_analysis_still_handles_empty_input():
    import pandas as pd

    table = pd.DataFrame(columns=["timestamp", "channel", "area", "height"])
    grouped = group_multi_channel_hits(table, time_window_ns=100)
    assert grouped.empty
    assert EventAnalyzer().group_events(table, use_numba=False).empty
