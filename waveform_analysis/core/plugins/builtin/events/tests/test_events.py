"""Tests for EventPlugin (events bundle)."""

import numpy as np
import pytest

from waveform_analysis.core.plugins.builtin.cpu.event import EventPlugin as ShimPlugin
from waveform_analysis.core.plugins.builtin.events import (
    EVENT_DTYPE,
    FLAG_EVENT_VALID,
    FLAG_POSITION_VALID,
    EventPlugin,
)
from waveform_analysis.core.plugins.builtin.position_reconstruction import (
    POSITION_RECONSTRUCTION_DTYPE,
)
from waveform_analysis.core.plugins.builtin.s1_s2_pair_candidates import (
    S1_S2_PAIR_CANDIDATES_DTYPE,
)


class EventContext:
    def __init__(self, pairs, positions):
        self.data = {"s1_s2_pairs": pairs, "position_reconstruction": positions}

    def get_data(self, run_id, data_name):
        return self.data[data_name]

    def get_config(self, plugin, key):
        return plugin.options[key].default


@pytest.fixture
def event_inputs():
    pairs = np.zeros(3, dtype=S1_S2_PAIR_CANDIDATES_DTYPE)
    pairs["pair_id"] = [31, 7, 42]
    pairs["selected"] = [True, False, True]
    pairs["s1_peak_id"] = [101, 102, 103]
    pairs["s2_peak_id"] = [201, 202, 203]
    pairs["s1_area"] = [10.0, 20.0, 30.0]
    pairs["s2_area"] = [100.0, 200.0, 300.0]
    pairs["s1_time"] = [1.25e12, 2.25e12, 3.25e12]
    pairs["s2_time"] = pairs["s1_time"] + 5e7
    pairs["drift_time_ns"] = 5e4
    pairs["score_total"] = [0.8, 0.2, 0.4]
    positions = np.zeros(2, dtype=POSITION_RECONSTRUCTION_DTYPE)
    positions["pair_id"] = [31, 42]
    positions["x"] = [1.0, np.nan]
    positions["y"] = [2.0, np.nan]
    positions["z"] = [30.0, 40.0]
    positions["r"] = [np.sqrt(5.0), np.nan]
    positions["flags"] = [1, 0]
    return pairs, positions


def test_old_path_is_new_bundle():
    assert ShimPlugin is EventPlugin


def test_plugin_metadata():
    plugin = EventPlugin()
    assert plugin.provides == "events"
    assert plugin.version == "0.1.0"
    assert plugin.output_dtype is EVENT_DTYPE
    assert "event_id" in EVENT_DTYPE.names


def test_events_align_positions_and_flags_by_pair_id(event_inputs):
    pairs, positions = event_inputs
    plugin = EventPlugin()
    expected = plugin.compute(EventContext(pairs, positions), "run")
    observed = plugin.compute(EventContext(pairs, positions[::-1]), "run")

    for name in EVENT_DTYPE.names:
        np.testing.assert_array_equal(observed[name], expected[name])
    np.testing.assert_array_equal(observed["pair_id"], [31, 42])
    np.testing.assert_array_equal(observed["event_id"], [0, 1])
    np.testing.assert_array_equal(observed["event_number"], [0, 1])
    np.testing.assert_array_equal(observed["s1_time"], pairs["s1_time"][[0, 2]])
    np.testing.assert_array_equal(observed["drift_time_ns"], [5e4, 5e4])
    assert observed["flags"][0] & FLAG_POSITION_VALID
    assert observed["flags"][0] & FLAG_EVENT_VALID
    assert not observed["flags"][1] & FLAG_POSITION_VALID
    assert np.isnan(observed["x"][1])
    assert observed.dtype == EVENT_DTYPE


@pytest.mark.parametrize("product", ["selected pairs", "positions"])
def test_events_reject_duplicate_pair_ids(event_inputs, product):
    pairs, positions = event_inputs
    if product == "selected pairs":
        pairs["pair_id"][2] = pairs["pair_id"][0]
    else:
        positions["pair_id"][1] = positions["pair_id"][0]

    with pytest.raises(ValueError, match="duplicate.*pair_id"):
        EventPlugin().compute(EventContext(pairs, positions), "run")


@pytest.mark.parametrize(
    "case", ["missing", "extra", "different", "empty_positions", "empty_pairs"]
)
def test_events_reject_mismatched_pair_membership(event_inputs, case):
    pairs, positions = event_inputs
    if case == "missing":
        positions = positions[:1]
    elif case == "extra":
        positions = np.concatenate([positions, np.zeros(1, dtype=positions.dtype)])
        positions["pair_id"][-1] = 99
    elif case == "different":
        positions["pair_id"][1] = 99
    elif case == "empty_positions":
        positions = positions[:0]
    else:
        pairs["selected"] = False

    with pytest.raises(ValueError, match="pair_id.*(missing|extra)|(?:missing|extra).*pair_id"):
        EventPlugin().compute(EventContext(pairs, positions), "run")


def test_events_accept_both_inputs_empty(event_inputs):
    pairs, positions = event_inputs
    pairs["selected"] = False
    result = EventPlugin().compute(EventContext(pairs, positions[:0]), "run")

    assert result.shape == (0,)
    assert result.dtype == EVENT_DTYPE


@pytest.mark.parametrize("product", ["pairs", "positions"])
def test_events_reject_noninteger_pair_ids(event_inputs, product):
    pairs, positions = event_inputs
    values = pairs if product == "pairs" else positions
    dtype = [
        (name, "f8" if name == "pair_id" else values.dtype[name]) for name in values.dtype.names
    ]
    converted = np.empty(values.shape, dtype=dtype)
    for name in values.dtype.names:
        converted[name] = values[name]
    if product == "pairs":
        pairs = converted
    else:
        positions = converted

    with pytest.raises(ValueError, match="pair_id.*integer"):
        EventPlugin().compute(EventContext(pairs, positions), "run")


def test_events_align_mixed_integer_ids_without_precision_loss(event_inputs):
    pairs, positions = event_inputs
    pairs["pair_id"][[0, 2]] = [2**53 + 1, 2**53]
    position_dtype = [
        (name, "u8" if name == "pair_id" else positions.dtype[name])
        for name in positions.dtype.names
    ]
    positions = positions.astype(position_dtype)
    positions["pair_id"] = [2**53, 2**53 + 1]
    positions["x"] = [1.0, 2.0]
    positions["flags"] = [1, 0]

    result = EventPlugin().compute(EventContext(pairs, positions), "run")

    np.testing.assert_array_equal(result["pair_id"], [2**53 + 1, 2**53])
    np.testing.assert_array_equal(result["x"], [2.0, 1.0])
    assert not result["flags"][0] & FLAG_POSITION_VALID
    assert result["flags"][1] & FLAG_POSITION_VALID


def test_events_reject_distinct_mixed_integer_ids_above_float_precision(event_inputs):
    pairs, positions = event_inputs
    pairs = pairs[:1]
    pairs["pair_id"] = [2**63 - 1]
    position_dtype = [
        (name, "u8" if name == "pair_id" else positions.dtype[name])
        for name in positions.dtype.names
    ]
    positions = positions[:1].astype(position_dtype)
    positions["pair_id"] = [2**63]

    with pytest.raises(ValueError, match="pair_id.*membership mismatch"):
        EventPlugin().compute(EventContext(pairs, positions), "run")
