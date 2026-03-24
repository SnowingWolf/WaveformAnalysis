import numpy as np
import pytest

from waveform_analysis.core.hardware.channel import HardwareChannel
from waveform_analysis.core.processing.dtypes import create_record_dtype
from waveform_analysis.core.processing.records_builder import (
    split_by_channel,
    split_by_hardware_channel,
)


def _make_st_waveforms():
    dtype = create_record_dtype(8)
    data = np.zeros(2, dtype=dtype)
    data["board"] = [0, 1]
    data["channel"] = [1, 1]
    data["timestamp"] = [10, 20]
    data["baseline"] = 100.0
    data["event_length"] = 8
    data["wave"] = 100
    return data


def test_split_by_hardware_channel_keeps_same_channel_number_on_different_boards_separate():
    st = _make_st_waveforms()

    groups = split_by_hardware_channel(st)

    assert [group[0] for group in groups] == [HardwareChannel(0, 1), HardwareChannel(1, 1)]
    assert [len(group[1]) for group in groups] == [1, 1]


def test_split_by_channel_rejects_multi_board_input():
    st = _make_st_waveforms()

    with pytest.raises(ValueError, match="split_by_channel no longer supports multi-board data"):
        split_by_channel(st)
