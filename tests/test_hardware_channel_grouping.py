import numpy as np
import pytest

import waveform_analysis.core.hardware.channel as channel_module
from waveform_analysis.core.hardware.channel import (
    HardwareChannel,
    group_indices_by_hardware_channel,
)


def _reference_groups(boards, channels):
    boards_arr = np.asarray(boards, dtype=np.int32)
    channels_arr = np.asarray(channels, dtype=np.int32)
    if len(boards_arr) == 0:
        return {}
    keys = np.empty(
        len(boards_arr),
        dtype=np.dtype([("board", np.int32), ("channel", np.int32)]),
    )
    keys["board"] = boards_arr
    keys["channel"] = channels_arr
    order = np.argsort(keys, kind="stable")
    sorted_keys = keys[order]
    starts = np.flatnonzero(np.r_[True, sorted_keys[1:] != sorted_keys[:-1]])
    ends = np.r_[starts[1:], len(order)]
    return {
        HardwareChannel(
            int(sorted_keys[start]["board"]), int(sorted_keys[start]["channel"])
        ): order[start:end]
        for start, end in zip(starts, ends, strict=False)
    }


def _assert_same_groups(actual, expected):
    assert list(actual) == list(expected)
    for key in expected:
        np.testing.assert_array_equal(actual[key], expected[key])


@pytest.mark.skipif(
    channel_module._stable_dense_order_numba is None,
    reason="Numba is not available",
)
def test_dense_counting_order_matches_stable_structured_reference(monkeypatch):
    dense_kernel = channel_module._stable_dense_order_numba
    calls = 0

    def wrapped(*args):
        nonlocal calls
        calls += 1
        return dense_kernel(*args)

    monkeypatch.setattr(channel_module, "_stable_dense_order_numba", wrapped)
    boards = np.array([2, 0, 1, 0, 2, 1, 0, 2, 1, 0], dtype=np.int32)
    channels = np.array([1, 3, 0, 1, 1, 0, 3, 0, 0, 1], dtype=np.int32)

    actual = group_indices_by_hardware_channel(boards, channels)

    _assert_same_groups(actual, _reference_groups(boards, channels))
    assert calls == 1


@pytest.mark.parametrize("seed", range(8))
def test_random_grouping_matches_stable_structured_reference(seed):
    rng = np.random.default_rng(seed)
    n = 257 + seed * 31
    boards = rng.integers(0, 8, size=n, dtype=np.int32)
    channels = rng.integers(0, 32, size=n, dtype=np.int32)

    actual = group_indices_by_hardware_channel(boards, channels)

    _assert_same_groups(actual, _reference_groups(boards, channels))


@pytest.mark.parametrize(
    ("boards", "channels"),
    (
        (np.array([], dtype=np.int32), np.array([], dtype=np.int32)),
        (np.array([0, 31], dtype=np.int32), np.array([0, 31], dtype=np.int32)),
        (np.array([0, 2_000_000], dtype=np.int32), np.array([0, 2_000_000], dtype=np.int32)),
        (np.array([-1, 0, -1], dtype=np.int32), np.array([2, 2, 1], dtype=np.int32)),
    ),
)
def test_sparse_wide_negative_and_empty_inputs_use_safe_reference_fallback(
    monkeypatch,
    boards,
    channels,
):
    def fail_if_called(*args):
        raise AssertionError("dense kernel must not receive guarded fallback input")

    monkeypatch.setattr(channel_module, "_stable_dense_order_numba", fail_if_called)

    actual = group_indices_by_hardware_channel(boards, channels)

    _assert_same_groups(actual, _reference_groups(boards, channels))


def test_mismatched_board_and_channel_lengths_are_rejected():
    with pytest.raises(ValueError, match="same length"):
        group_indices_by_hardware_channel([0, 1], [0])
