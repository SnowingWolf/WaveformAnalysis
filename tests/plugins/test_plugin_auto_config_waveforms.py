import numpy as np

from tests.utils import DummyContext, register_test_adapter
from waveform_analysis.core.plugins.builtin.cpu.standard import WaveformsPlugin
from waveform_analysis.utils.formats import get_adapter, unregister_adapter


def test_waveforms_plugin_uses_raw_files_channels(monkeypatch):
    raw_files = [["f0"], ["f1"], ["f2"], ["f3"]]
    called = {}

    def fake_load_waveforms_flat(self, raw_files, n_channels, **_kwargs):  # noqa: ARG001
        called["raw_files_len"] = len(raw_files)
        called["n_channels"] = n_channels
        return [np.zeros((0, 0)) for _ in range(n_channels)]

    monkeypatch.setattr(WaveformsPlugin, "_load_waveforms_flat", fake_load_waveforms_flat)

    plugin = WaveformsPlugin()
    ctx = DummyContext(
        {
            "n_channels": 4,
            "waveforms": {"n_channels": 1, "start_channel_slice": 0},
            "show_progress": False,
        },
        {"raw_files": raw_files},
    )

    plugin.compute(ctx, "run_001")

    assert called["raw_files_len"] == 4
    assert called["n_channels"] == 4


def test_st_waveforms_lineage_uses_adapter_dtype():
    adapter_name = "test_adapter_lineage"
    register_test_adapter(adapter_name)
    try:
        plugin = WaveformsPlugin()
        ctx = DummyContext({"st_waveforms": {"daq_adapter": adapter_name, "wave_length": 16}})

        lineage = plugin.get_lineage(ctx)
        wave_field = next(item for item in lineage["dtype"] if item[0] == "wave")

        assert wave_field[2] == (16,)
    finally:
        unregister_adapter(adapter_name)


def test_waveforms_plugin_v1725_outputs_standard_st_waveforms(monkeypatch):
    raw_dtype = np.dtype(
        [
            ("channel", "i2"),
            ("timestamp", "i8"),
            ("baseline", "f8"),
            ("trunc", "b1"),
            ("wave", "O"),
        ]
    )
    raw_data = np.zeros(2, dtype=raw_dtype)
    raw_data["channel"] = np.array([0, 1], dtype=np.int16)
    raw_data["timestamp"] = np.array([10, 20], dtype=np.int64)
    raw_data["baseline"] = np.array([100.0, 200.0], dtype=np.float64)
    raw_data["trunc"] = np.array([False, True], dtype=np.bool_)
    raw_data["wave"][0] = np.array([11, 12, 13, 14], dtype=np.int16)
    raw_data["wave"][1] = np.array([21, 22], dtype=np.int16)

    adapter = get_adapter("v1725")

    def fake_read_files(file_paths, show_progress=False):  # noqa: ARG001
        assert file_paths == ["dup.bin"]
        return raw_data

    monkeypatch.setattr(adapter.format_reader, "read_files", fake_read_files)

    class _Logger:
        def info(self, *_args, **_kwargs):
            return None

        def warning(self, *_args, **_kwargs):
            return None

    plugin = WaveformsPlugin()
    ctx = DummyContext(
        config={"daq_adapter": "v1725", "show_progress": False},
        data={"raw_files": [["dup.bin"], ["dup.bin"]]},
    )
    ctx.logger = _Logger()

    st = plugin.compute(ctx, "run_001")

    assert isinstance(st, np.ndarray)
    assert st.dtype.names == (
        "baseline",
        "baseline_upstream",
        "polarity",
        "timestamp",
        "record_id",
        "dt",
        "event_length",
        "board",
        "channel",
        "wave",
    )
    assert st["wave"].shape == (2, 4)
    np.testing.assert_array_equal(st["event_length"], np.array([4, 2], dtype=np.int32))
    np.testing.assert_array_equal(st["board"], np.array([0, 0], dtype=np.int16))
    np.testing.assert_array_equal(st["channel"], np.array([0, 1], dtype=np.int16))
    np.testing.assert_array_equal(st["timestamp"], np.array([40000, 80000], dtype=np.int64))
    np.testing.assert_array_equal(st["dt"], np.array([4, 4], dtype=np.int32))
    assert np.all(np.isnan(st["baseline_upstream"]))
    np.testing.assert_array_equal(st["polarity"], np.array(["unknown", "unknown"]))
    assert int(st["wave"][1, 2]) == 0


def test_waveforms_plugin_applies_channel_metadata_polarity(monkeypatch):
    raw_files = [["f0"], ["f1"]]

    def fake_load_waveforms_flat(self, raw_files, n_channels, **_kwargs):  # noqa: ARG001
        out = []
        for ch in range(n_channels):
            arr = np.zeros((1, 12))
            arr[:, 0] = 0
            arr[:, 1] = ch
            arr[:, 2] = 100 + ch
            arr[:, 7:] = 50
            out.append(arr)
        return out

    monkeypatch.setattr(WaveformsPlugin, "_load_waveforms_flat", fake_load_waveforms_flat)

    plugin = WaveformsPlugin()
    ctx = DummyContext(
        config={
            "show_progress": False,
            "channel_metadata": {
                "channels": {
                    "0:0": {"polarity": "negative"},
                    "0:1": {"polarity": "positive"},
                }
            },
        },
        data={"raw_files": raw_files},
    )

    st = plugin.compute(ctx, "run_001")

    np.testing.assert_array_equal(st["polarity"], np.array(["negative", "positive"]))
