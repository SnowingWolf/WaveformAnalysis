import pytest

from waveform_analysis.utils.daq import adapt_daq_run


class GoodDAQWithMethod:
    def __init__(self, paths):
        self._paths = paths

    def get_channel_paths(self, n_channels):
        out = [list(p) for p in self._paths]
        if len(out) < n_channels:
            out.extend([[]] * (n_channels - len(out)))
        return out[:n_channels]


class BadMethodWithChannelFiles:
    def __init__(self, channel_files):
        self.channel_files = channel_files

    def get_channel_paths(self, n_channels):
        raise RuntimeError("simulated failure")


def test_adapter_prefers_existing_method():
    daq = GoodDAQWithMethod(paths=[["a.csv"], [], ["c1.csv", "c2.csv"]])
    adapted = adapt_daq_run(daq)
    res = adapted.get_channel_paths(4)
    assert isinstance(res, list)
    assert len(res) == 4
    assert res[0] == ["a.csv"]
    assert res[1] == []
    assert res[2] == ["c1.csv", "c2.csv"]
    assert res[3] == []


def test_adapter_falls_back_to_channel_files_on_method_error():
    cf = {
        0: [{"path": "p0_first"}, "p0_second"],
        2: [{"path": "p2_only"}],
    }
    daq = BadMethodWithChannelFiles(channel_files=cf)
    adapted = adapt_daq_run(daq)
    res = adapted.get_channel_paths(4)
    assert res[0] == ["p0_first", "p0_second"]
    assert res[1] == []
    assert res[2] == ["p2_only"]
    assert res[3] == []


def test_adapter_accepts_plain_dict_mapping():
    mapping = {0: ["d0_1", {"path": "d0_2"}], 2: ["d2_1"]}
    adapted = adapt_daq_run(mapping)
    res = adapted.get_channel_paths(4)
    assert res[0] == ["d0_1", "d0_2"]
    assert res[1] == []
    assert res[2] == ["d2_1"]
    assert res[3] == []


def test_adapter_unknown_shape_returns_empty_lists():
    class Unknown: ...

    adapted = adapt_daq_run(Unknown())
    assert adapted.get_channel_paths(3) == [[], [], []]


def test_channel_files_non_dict_is_ignored():
    class HasListChannelFiles:
        def __init__(self):
            self.channel_files = ["not", "a", "dict"]

    adapted = adapt_daq_run(HasListChannelFiles())
    assert adapted.get_channel_paths(2) == [[], []]
