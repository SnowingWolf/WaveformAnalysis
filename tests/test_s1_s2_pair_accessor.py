import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np
import pytest

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.peaklets._compute import (
    PEAKLET_WAVEFORMS_DTYPE,
)
from waveform_analysis.core.plugins.builtin.s1_s2_pair_candidates import (
    S1_S2_PAIR_CANDIDATES_DTYPE,
)
from waveform_analysis.utils.s1_s2_pair_accessor import (
    S1S2PairAccessor,
    WaveformNotFoundError,
)

S2_PEAK_ID = 99


class CountingContext(DummyContext):
    def __init__(self, data):
        super().__init__(data=data)
        self.calls: list[tuple[str, str]] = []

    def get_data(self, run_id, name, *, output="native", **kwargs):
        self.calls.append((name, output))
        return super().get_data(run_id, name, output=output, **kwargs)


def _candidate_rows(candidate_ids=(1, 2, 3)):
    rows = np.zeros(len(candidate_ids), dtype=S1_S2_PAIR_CANDIDATES_DTYPE)
    for index, peak_id in enumerate(candidate_ids):
        rows[index]["pair_id"] = index
        rows[index]["s1_peak_id"] = peak_id
        rows[index]["s2_peak_id"] = S2_PEAK_ID
        rows[index]["s1_index"] = index
        rows[index]["s2_index"] = 0
        rows[index]["s1_time"] = (120 + index * 200) * 1000
        rows[index]["s2_time"] = 1050 * 1000
        rows[index]["drift_time"] = rows[index]["s2_time"] - rows[index]["s1_time"]
        rows[index]["drift_time_ns"] = rows[index]["drift_time"] / 1000
        rows[index]["s1_width"] = 40
        rows[index]["s2_width"] = 100
    return rows


def _selected_rows(selected_id=2, *, duplicate=False):
    selected_ids = (selected_id, 1) if duplicate else (selected_id,)
    rows = _candidate_rows(selected_ids)
    rows["selected"] = True
    return rows


def _orphan_s2_row():
    row = np.zeros(1, dtype=S1_S2_PAIR_CANDIDATES_DTYPE)
    row["pair_id"] = -1
    row["s1_peak_id"] = -1
    row["s2_peak_id"] = S2_PEAK_ID
    row["s1_index"] = -1
    row["s2_index"] = 0
    row["s1_time"] = -1
    row["s2_time"] = 1050 * 1000
    row["drift_time"] = -1
    row["drift_time_ns"] = -1
    row["s2_width"] = 100
    return row


def _waveform_layer(peak_ids=(1, 2, 3, S2_PEAK_ID)):
    starts_ns = {1: 100, 2: 300, 3: 500, 4: 700, S2_PEAK_ID: 1000}
    values = {
        1: np.array([0.0, 1.0, 2.0, 1.0, 0.0]),
        2: np.array([0.0, 3.0, 6.0, 3.0, 0.0]),
        3: np.array([0.0, 2.0, 4.0, 2.0, 0.0]),
        4: np.array([0.0, 4.0, 8.0, 4.0, 0.0]),
        S2_PEAK_ID: np.array([0.0, 1000.0, 2000.0, 1000.0, 0.0]),
    }
    rows = np.zeros(len(peak_ids), dtype=PEAKLET_WAVEFORMS_DTYPE)
    pool_parts = []
    offset = 0
    for index, peak_id in enumerate(peak_ids):
        waveform = values[peak_id]
        rows[index]["peak_id"] = peak_id
        rows[index]["time_start"] = starts_ns[peak_id] * 1000
        rows[index]["time_end"] = (starts_ns[peak_id] + len(waveform) * 10) * 1000
        rows[index]["dt"] = 10
        rows[index]["wave_offset"] = offset
        rows[index]["wave_length"] = len(waveform)
        pool_parts.append(waveform)
        offset += len(waveform)
    return rows, np.concatenate(pool_parts) if pool_parts else np.zeros(0)


def _context(candidate_ids=(1, 2, 3), selected_id=2, *, waveform_ids=None):
    candidates = _candidate_rows(candidate_ids)
    selected = (
        np.zeros(0, dtype=S1_S2_PAIR_CANDIDATES_DTYPE)
        if selected_id is None
        else _selected_rows(selected_id)
    )
    if waveform_ids is None:
        waveform_ids = (*candidate_ids, S2_PEAK_ID)
        if selected_id is not None and selected_id not in waveform_ids:
            waveform_ids = (*waveform_ids, selected_id)
    waveforms, pool = _waveform_layer(waveform_ids)
    return CountingContext(
        {
            "s1_s2_pair_candidates": candidates,
            "s1_s2_pairs": selected,
            "peaklet_waveforms": waveforms,
            "peaklet_waveform_pool": pool,
        }
    )


def test_plot_s2_candidates_uses_independent_axes_styles_and_absolute_timing():
    accessor = S1S2PairAccessor(_context(), "run")

    fig, (ax_s1, ax_s2), info = accessor.plot_s2_candidates(S2_PEAK_ID)
    try:
        assert fig.axes == [ax_s1, ax_s2]
        assert ax_s1.get_yscale() == "linear"
        assert ax_s2.get_yscale() == "linear"
        assert len(ax_s1.lines) == 3
        assert len(ax_s2.lines) == 1
        assert all(line.axes is ax_s1 for line in ax_s1.lines)
        assert ax_s2.lines[0].axes is ax_s2

        selected_line = next(line for line in ax_s1.lines if "Selected S1" in line.get_label())
        candidate_line = next(line for line in ax_s1.lines if "Candidate S1" in line.get_label())
        assert selected_line.get_color() == "tab:green"
        assert candidate_line.get_color() == "tab:blue"
        assert selected_line.get_linewidth() > candidate_line.get_linewidth()
        assert ax_s2.lines[0].get_color() == "tab:red"

        np.testing.assert_allclose(ax_s1.lines[0].get_xdata(), [0, 10, 20, 30, 40])
        np.testing.assert_allclose(ax_s2.lines[0].get_xdata(), [900, 910, 920, 930, 940])
        assert ax_s1.get_ylim()[1] < 20
        assert ax_s2.get_ylim()[1] > 2000

        assert info["s2_peak_id"] == S2_PEAK_ID
        assert info["candidate_s1_peak_ids"] == [1, 2, 3]
        assert info["selected_s1_peak_id"] == 2
        assert info["missing_waveform_peak_ids"] == []
        assert info["event_t0_ns"] == 100
        assert "Candidates=3" in ax_s1.get_title()
        assert "Selected S1=2" in ax_s1.get_title()
    finally:
        plt.close(fig)


def test_plot_s2_candidates_handles_no_candidates_and_no_selected():
    waveforms, pool = _waveform_layer((S2_PEAK_ID,))
    context = CountingContext(
        {
            "s1_s2_pair_candidates": _orphan_s2_row(),
            "s1_s2_pairs": np.zeros(0, dtype=S1_S2_PAIR_CANDIDATES_DTYPE),
            "peaklet_waveforms": waveforms,
            "peaklet_waveform_pool": pool,
        }
    )
    accessor = S1S2PairAccessor(context, "run")

    fig, (ax_s1, ax_s2), info = accessor.plot_s2_candidates(S2_PEAK_ID)
    try:
        assert len(ax_s1.lines) == 0
        assert len(ax_s2.lines) == 1
        assert info["candidate_s1_peak_ids"] == []
        assert info["selected_s1_peak_id"] is None
    finally:
        plt.close(fig)

    context = _context(selected_id=None)
    accessor = S1S2PairAccessor(context, "run")
    fig, (_, _), info = accessor.plot_s2_candidates(S2_PEAK_ID)
    try:
        assert info["candidate_s1_peak_ids"] == [1, 2, 3]
        assert info["selected_s1_peak_id"] is None
    finally:
        plt.close(fig)


def test_plot_s2_candidates_records_missing_s1_waveforms():
    accessor = S1S2PairAccessor(_context(waveform_ids=(1, 2, S2_PEAK_ID)), "run")

    fig, (ax_s1, _), info = accessor.plot_s2_candidates(S2_PEAK_ID)
    try:
        assert len(ax_s1.lines) == 2
        assert info["candidate_s1_peak_ids"] == [1, 2, 3]
        assert info["missing_waveform_peak_ids"] == [3]
        assert info["plotted_s1_peak_ids"] == [1, 2]
    finally:
        plt.close(fig)


def test_plot_s2_candidates_adds_selected_s1_outside_candidate_table():
    accessor = S1S2PairAccessor(_context(candidate_ids=(1, 2), selected_id=4), "run")

    fig, (ax_s1, _), info = accessor.plot_s2_candidates(S2_PEAK_ID)
    try:
        assert info["candidate_s1_peak_ids"] == [1, 2]
        assert info["selected_s1_peak_id"] == 4
        assert info["selected_s1_outside_candidates"] is True
        assert info["plotted_s1_peak_ids"] == [1, 2, 4]
        assert any("peak_id=4" in line.get_label() for line in ax_s1.lines)
    finally:
        plt.close(fig)


def test_plot_s2_candidates_deduplicates_candidates_in_stable_order_and_accepts_ax():
    context = _context(
        candidate_ids=(3, 1, 3, 2),
        selected_id=1,
        waveform_ids=(1, 2, 3, S2_PEAK_ID),
    )
    accessor = S1S2PairAccessor(context, "run")
    base_fig, base_ax = plt.subplots()

    fig, (ax_s1, ax_s2), info = accessor.plot_s2_candidates(S2_PEAK_ID, ax=base_ax)
    try:
        assert fig is base_fig
        assert ax_s1 is base_ax
        assert ax_s2 in fig.axes
        assert info["candidate_s1_peak_ids"] == [3, 1, 2]
        assert len(ax_s1.lines) == 3
    finally:
        plt.close(fig)


def test_plot_s2_candidates_rejects_duplicate_selected_pairs():
    context = _context()
    context._data["s1_s2_pairs"] = _selected_rows(2, duplicate=True)
    accessor = S1S2PairAccessor(context, "run")

    with pytest.raises(ValueError, match="multiple selected.*s2_peak_id=99"):
        accessor.plot_s2_candidates(S2_PEAK_ID)


def test_plot_s2_candidates_distinguishes_unknown_and_missing_s2_waveform():
    known_context = _context(waveform_ids=(1, 2, 3))
    known_accessor = S1S2PairAccessor(known_context, "run")
    with pytest.raises(WaveformNotFoundError, match="s2_peak_id=99"):
        known_accessor.plot_s2_candidates(S2_PEAK_ID)

    waveforms, pool = _waveform_layer((1,))
    unknown_context = CountingContext(
        {
            "s1_s2_pair_candidates": np.zeros(0, dtype=S1_S2_PAIR_CANDIDATES_DTYPE),
            "s1_s2_pairs": np.zeros(0, dtype=S1_S2_PAIR_CANDIDATES_DTYPE),
            "peaklet_waveforms": waveforms,
            "peaklet_waveform_pool": pool,
        }
    )
    unknown_accessor = S1S2PairAccessor(unknown_context, "run")
    with pytest.raises(ValueError, match="S2 peak_id=99 not found"):
        unknown_accessor.plot_s2_candidates(S2_PEAK_ID)


def test_plot_s2_candidates_reuses_native_tables_and_waveform_layer():
    context = _context()
    accessor = S1S2PairAccessor(context, "run")

    first, _, _ = accessor.plot_s2_candidates(S2_PEAK_ID, show_intervals=False)
    second, _, _ = accessor.plot_s2_candidates(S2_PEAK_ID, show_intervals=False)
    plt.close(first)
    plt.close(second)

    names = [name for name, _ in context.calls]
    assert names.count("s1_s2_pairs") == 1
    assert names.count("s1_s2_pair_candidates") == 1
    assert names.count("peaklet_waveforms") == 1
    assert names.count("peaklet_waveform_pool") == 1
    assert all(output == "native" for _, output in context.calls)


def test_existing_plot_behavior_remains_single_axis_pair_plot():
    context = _context()

    class TwoArgumentContext:
        def get_data(self, run_id, name):
            return context._data[name]

    accessor = S1S2PairAccessor(TwoArgumentContext(), "run")

    fig, ax = accessor.plot(0)
    try:
        assert fig.axes == [ax]
        assert len(ax.lines) == 4
        assert ax.get_ylabel() == "Amplitude (summed signal)"
    finally:
        plt.close(fig)
