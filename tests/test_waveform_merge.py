import numpy as np
import pytest

from waveform_analysis.core.plugins.builtin.shared.waveform_merge import (
    WaveformOverlapConflictError,
    merge_waveform_segments,
)


def _segment(values, times, *, board=0, channel=1, record_id=0, merged_index=0, dt=1):
    return {
        "waveform": np.asarray(values, dtype=np.float32),
        "abs_time_ps": np.asarray(times, dtype=np.int64),
        "dt": dt,
        "board": board,
        "channel": channel,
        "record_id": record_id,
        "merged_index": merged_index,
    }


def test_merge_waveform_segments_deduplicates_equal_channel_samples():
    result = merge_waveform_segments(
        [
            _segment([10, 20], [1000, 2000], record_id=1),
            _segment([10, 20], [1000, 2000], record_id=2),
        ],
        sum_channels=False,
        dense=False,
    )

    np.testing.assert_array_equal(result["waveform"], np.array([10, 20], dtype=np.float32))
    np.testing.assert_array_equal(result["abs_time_ps"], np.array([1000, 2000]))


def test_merge_waveform_segments_rejects_conflicting_channel_samples():
    with pytest.raises(
        WaveformOverlapConflictError,
        match=r"board=0, channel=1, abs_time_ps=1000.*record_id=1.*record_id=2",
    ):
        merge_waveform_segments(
            [
                _segment([10], [1000], record_id=1),
                _segment([11], [1000], record_id=2),
            ],
            sum_channels=False,
            dense=False,
        )


def test_merge_waveform_segments_sums_channels_after_deduplication_and_fills_gaps():
    result = merge_waveform_segments(
        [
            _segment([2, 3], [1000, 2000], channel=1, record_id=1),
            _segment([2, 3], [1000, 2000], channel=1, record_id=2),
            _segment([5, 7], [2000, 3000], channel=2, record_id=3),
            _segment([11], [5000], channel=2, record_id=4),
        ],
        sum_channels=True,
        dense=True,
    )

    np.testing.assert_array_equal(result["waveform"], np.array([2, 8, 7, 0, 11], dtype=np.float32))
    np.testing.assert_array_equal(result["abs_time_ps"], np.array([1000, 2000, 3000, 4000, 5000]))


@pytest.mark.parametrize(
    "segments, message",
    [
        ([_segment([1], [0], dt=0)], "positive dt"),
        ([_segment([1], [0], dt=1), _segment([1], [0], dt=2)], "mixed dt"),
        ([_segment([1, 2], [0])], "lengths differ"),
        ([_segment([], [0])], "lengths differ"),
        ([_segment([1, np.nan], [0, 1000])], "non-finite"),
        ([_segment([1, 2], [0, 2000], dt=1)], "not aligned"),
        (
            [_segment([1], [0], dt=1), _segment([2], [1500], dt=1)],
            "common dt grid",
        ),
    ],
)
def test_merge_waveform_segments_validates_inputs(segments, message):
    with pytest.raises(ValueError, match=message):
        merge_waveform_segments(segments, sum_channels=False, dense=False)
