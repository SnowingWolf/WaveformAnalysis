"""Physical board/channel access must be independent of file grouping keys."""

from pathlib import Path

import numpy as np
import pytest

from tests.daq_adapter_helpers import make_v1725_single_wave_blob, make_vx2730_bin_bytes
from waveform_analysis.acquisition.formats import DAQAdapter, VX2730BinReader, get_adapter


@pytest.fixture(params=["vx2730", "vx2730_bin", "v1725"])
def channel_run(request, tmp_path):
    """Small real reader inputs, including one channel shared by two boards."""
    name = request.param
    adapter = get_adapter(name)
    raw = tmp_path / "run" / "RAW"
    raw.mkdir(parents=True)
    events = [(0, 3, 101), (1, 3, 202), (1, 7, 303), (0, 3, 404)]
    if name == "vx2730":
        # Deliberately unrelated filename groups; each group has its own header.
        for group, rows in [(8, events[:2]), (9, events[2:])]:
            text = "HEADER 1\nHEADER 2\n" + "".join(
                f"{board};{channel};{timestamp};0;0;0;0;11;12\n"
                for board, channel, timestamp in rows
            )
            (raw / f"CH{group}_0.CSV").write_text(text)
    elif name == "vx2730_bin":
        (raw / "SDataR_run.BIN").write_bytes(
            make_vx2730_bin_bytes(
                [
                    {"board": board, "channel": channel, "timestamp": timestamp}
                    for board, channel, timestamp in events
                ]
            )
        )
    else:
        for board in [0, 1]:
            (raw / f"test_raw_b{board}_seg0.bin").write_bytes(
                b"".join(
                    make_v1725_single_wave_blob(channel=channel, timestamp=timestamp)
                    for event_board, channel, timestamp in events
                    if event_board == board
                )
            )
    return adapter, tmp_path, raw


def _timestamps(adapter, data):
    return adapter.extract_columns(data)["timestamp"].tolist()


def test_channel_is_selected_from_event_metadata(channel_run):
    adapter, root, _ = channel_run
    data = adapter.load_channel(str(root), "run", channel=3, board=0)
    assert _timestamps(adapter, data) == [101, 404]
    extracted = adapter.extract_columns(data)
    assert extracted["board"].tolist() == [0, 0]
    assert extracted["channel"].tolist() == [3, 3]
    raw = np.concatenate(
        [
            adapter.format_reader.read_files(paths)
            for paths in adapter.scan_run(str(root), "run").values()
        ]
    )
    metadata = adapter.extract_columns(raw)
    expected = raw[(metadata["board"] == 0) & (metadata["channel"] == 3)]
    assert data.dtype == expected.dtype
    assert data.shape == expected.shape
    if data.dtype.names:
        for field in data.dtype.names:
            for actual, reference in zip(data[field], expected[field], strict=True):
                np.testing.assert_array_equal(actual, reference)
    else:
        np.testing.assert_array_equal(data, expected)


def test_generator_selects_channel_and_preserves_native_records(channel_run):
    adapter, root, _ = channel_run
    chunks = list(
        adapter.load_channel_generator(str(root), "run", channel=3, board=1, chunk_size=1)
    )
    assert chunks
    assert all(len(chunk) for chunk in chunks)
    data = np.concatenate(chunks)
    assert _timestamps(adapter, data) == [202]
    reference = adapter.load_channel(str(root), "run", channel=3, board=1)
    assert data.dtype == reference.dtype
    assert data.shape == reference.shape
    if data.dtype.names:
        for field in data.dtype.names:
            for actual, expected in zip(data[field], reference[field], strict=True):
                np.testing.assert_array_equal(actual, expected)
    else:
        np.testing.assert_array_equal(data, reference)


def test_all_channels_are_only_recorded_hardware_keys(channel_run):
    adapter, root, _ = channel_run
    result = adapter.load_all_channels(str(root), "run")
    assert isinstance(result, dict)
    assert set(result) == {(0, 3), (1, 3), (1, 7)}
    assert _timestamps(adapter, result[(0, 3)]) == [101, 404]
    assert _timestamps(adapter, result[(1, 3)]) == [202]
    assert _timestamps(adapter, result[(1, 7)]) == [303]


@pytest.mark.parametrize("method", ["load_channel", "load_channel_generator"])
def test_board_is_required_and_never_inferred_from_group(channel_run, method):
    adapter, root, _ = channel_run
    with pytest.raises(TypeError, match="board"):
        result = getattr(adapter, method)(str(root), "run", channel=3)
        if method.endswith("generator"):
            list(result)


@pytest.mark.parametrize("key", [(0, 7), (8, 3), (0, 8)])
def test_absent_board_channel_pair_is_an_error(channel_run, key):
    adapter, root, _ = channel_run
    board, channel = key
    with pytest.raises(ValueError, match="不存在"):
        adapter.load_channel(str(root), "run", channel=channel, board=board)
    with pytest.raises(ValueError, match="不存在"):
        list(adapter.load_channel_generator(str(root), "run", channel=channel, board=board))


@pytest.mark.parametrize("name", ["vx2730", "vx2730_bin", "v1725"])
def test_empty_run_has_no_recorded_channels(tmp_path, name):
    raw = tmp_path / "run" / "RAW"
    raw.mkdir(parents=True)
    filename = {
        "vx2730": "CH3_0.CSV",
        "vx2730_bin": "SDataR_run.BIN",
        "v1725": "test_raw_b0_seg0.bin",
    }[name]
    (raw / filename).touch()
    adapter = get_adapter(name)
    assert adapter.load_all_channels(str(tmp_path), "run") == {}
    with pytest.raises(ValueError, match="不存在"):
        adapter.load_channel(str(tmp_path), "run", channel=3, board=0)
    with pytest.raises(ValueError, match="不存在"):
        list(adapter.load_channel_generator(str(tmp_path), "run", channel=3, board=0))


@pytest.mark.parametrize("method", ["load_channel", "load_channel_generator", "load_all_channels"])
def test_reads_each_candidate_only_once_and_preserves_order(tmp_path, monkeypatch, method):
    reader = VX2730BinReader(events_per_chunk=1)
    adapter = DAQAdapter("counted", reader, get_adapter("vx2730_bin").directory_layout)
    first, second = Path("first.BIN"), Path("second.BIN")
    groups = {9: [first, second], 3: [first]}
    monkeypatch.setattr(adapter, "scan_run", lambda *_: groups)
    calls = []

    def read_files_generator(paths, chunk_size=10, **kwargs):
        calls.extend(paths)
        for path in paths:
            timestamp = 20 if path == first else 10
            yield np.array([[2, 4, timestamp, 0, 0, 0, 0, 11]], dtype=np.int64)

    monkeypatch.setattr(reader, "read_files_generator", read_files_generator)
    if method == "load_all_channels":
        data = adapter.load_all_channels(str(tmp_path), "run")[(2, 4)]
    elif method == "load_channel_generator":
        data = np.concatenate(
            list(adapter.load_channel_generator(str(tmp_path), "run", 4, board=2))
        )
    else:
        data = adapter.load_channel(str(tmp_path), "run", 4, board=2)
    assert calls == [first, second]
    assert _timestamps(adapter, data) == [20, 10]


def test_removed_n_channels_padding_argument(tmp_path):
    with pytest.raises(TypeError, match="n_channels"):
        get_adapter("vx2730").load_all_channels(str(tmp_path), "run", n_channels=8)
    with pytest.raises(TypeError):
        get_adapter("vx2730").load_all_channels(str(tmp_path), "run", 8)


@pytest.mark.parametrize("chunk_size", [0, -1])
def test_generator_requires_positive_chunk_size(channel_run, chunk_size):
    adapter, root, _ = channel_run
    with pytest.raises(ValueError, match="chunk_size"):
        list(adapter.load_channel_generator(str(root), "run", 3, chunk_size, board=0))


def test_reader_errors_are_not_treated_as_missing_channels(tmp_path):
    raw = tmp_path / "run" / "RAW"
    raw.mkdir(parents=True)
    (raw / "invalid.BIN").write_bytes(b"\x00\x00" + bytes(40))
    adapter = get_adapter("vx2730_bin")
    with pytest.raises(ValueError, match="Invalid VX2730 BIN header"):
        adapter.load_all_channels(str(tmp_path), "run")
    with pytest.raises(ValueError, match="Invalid VX2730 BIN header"):
        adapter.load_channel(str(tmp_path), "run", 0, board=0)
    with pytest.raises(ValueError, match="Invalid VX2730 BIN header"):
        list(adapter.load_channel_generator(str(tmp_path), "run", 0, board=0))


@pytest.mark.parametrize("name", ["vx2730", "vx2730_bin", "v1725"])
def test_missing_directory_is_not_an_empty_run(tmp_path, name):
    adapter = get_adapter(name)
    with pytest.raises(FileNotFoundError):
        adapter.load_all_channels(str(tmp_path), "missing")
    with pytest.raises(FileNotFoundError):
        adapter.load_channel(str(tmp_path), "missing", channel=0, board=0)
    with pytest.raises(FileNotFoundError):
        list(adapter.load_channel_generator(str(tmp_path), "missing", channel=0, board=0))
