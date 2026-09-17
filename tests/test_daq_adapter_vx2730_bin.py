"""VX2730 CoMPASS binary (.BIN) adapter tests."""

import numpy as np
import pytest

from tests.daq_adapter_helpers import make_vx2730_bin_bytes
from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.records import RecordsPlugin
from waveform_analysis.core.plugins.builtin.st_waveforms.plugin import WaveformsPlugin
from waveform_analysis.core.processing.records_builder import build_records_from_raw_files
from waveform_analysis.utils.formats import (
    VX2730_BIN_LAYOUT,
    VX2730BinReader,
    get_adapter,
    get_format_reader,
)


def _events(n: int, *, n_samples: int = 4, channel: int = 0, board: int = 0) -> list[dict]:
    return [
        {
            "board": board,
            "channel": channel,
            "timestamp": 1_000_000 * (i + 1),
            "energy": 100 + i,
            "energy_cal": 1.5 * i,
            "energy_short": 50 + i,
            "flags": 0x4000 if i % 2 else 0,
            "wave_code": 1,
            "samples": np.arange(n_samples) + 8000 + i,
        }
        for i in range(n)
    ]


def _write(path, events, **kwargs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(make_vx2730_bin_bytes(events, **kwargs))
    return path


class TestVX2730BinReader:
    def test_registered(self):
        adapter = get_adapter("vx2730_bin")
        assert adapter.format_spec.name == "vx2730_bin"
        assert isinstance(get_format_reader("vx2730_bin"), VX2730BinReader)
        assert adapter.sampling_rate_hz == 500e6

    def test_read_full_header(self, tmp_path):
        events = _events(3)
        path = _write(tmp_path / "SDataR_run.BIN", events)

        data = VX2730BinReader().read_file(path)

        assert data.dtype == np.int64
        assert data.shape == (3, 7 + 4)
        for row, event in zip(data, events, strict=True):
            assert row[0] == event["board"]
            assert row[1] == event["channel"]
            assert row[2] == event["timestamp"]
            assert row[3] == event["energy"]
            assert row[4] == event["energy_short"]
            assert row[5] == event["flags"]
            assert row[6] == 1
            np.testing.assert_array_equal(row[7:], event["samples"])

    def test_read_header_with_calibrated_energy(self, tmp_path):
        events = _events(2)
        path = _write(tmp_path / "run.BIN", events, header=0xCAEF)

        data = VX2730BinReader().read_file(path)

        assert data.shape == (2, 11)
        np.testing.assert_array_equal(data[:, 2], [e["timestamp"] for e in events])
        np.testing.assert_array_equal(data[:, 7:], [e["samples"] for e in events])

    def test_read_header_without_waveform(self, tmp_path):
        events = _events(2)
        path = _write(tmp_path / "run.BIN", events, header=0xCAE5)

        data = VX2730BinReader().read_file(path)

        assert data.shape == (2, 7)
        np.testing.assert_array_equal(data[:, 3], [100, 101])
        np.testing.assert_array_equal(data[:, 6], [0, 0])

    def test_large_timestamp_kept_as_int64(self, tmp_path):
        events = _events(1)
        events[0]["timestamp"] = 2**62 + 7
        path = _write(tmp_path / "run.BIN", events)

        assert VX2730BinReader().read_file(path)[0, 2] == 2**62 + 7

    def test_multi_channel_single_file(self, tmp_path):
        events = _events(2, channel=0) + _events(2, channel=5, board=1)
        path = _write(tmp_path / "run.BIN", events)

        data = VX2730BinReader().read_file(path)

        np.testing.assert_array_equal(data[:, 0], [0, 0, 1, 1])
        np.testing.assert_array_equal(data[:, 1], [0, 0, 5, 5])

    def test_generator_chunks_match_full_read(self, tmp_path):
        paths = [
            _write(tmp_path / "run.BIN", _events(7)),
            _write(tmp_path / "run_1.BIN", _events(3)),
        ]
        reader = VX2730BinReader(events_per_chunk=3)

        chunks = list(reader.read_files_generator(paths))

        assert [len(c) for c in chunks] == [3, 3, 1, 3]
        np.testing.assert_array_equal(np.vstack(chunks), reader.read_files(paths))
        assert reader.count_total_rows(paths) == 10

    def test_empty_and_header_only_files(self, tmp_path):
        empty = tmp_path / "empty.BIN"
        empty.touch()
        header_only = _write(tmp_path / "header.BIN", [])
        reader = VX2730BinReader()

        assert reader.read_file(empty).size == 0
        assert reader.read_file(header_only).size == 0
        assert reader.read_files([empty, header_only]).size == 0
        assert list(reader.read_files_generator([empty, header_only])) == []
        assert reader.count_total_rows([empty, header_only]) == 0
        assert reader.read_file(tmp_path / "missing.BIN").size == 0

    def test_invalid_header_raises(self, tmp_path):
        path = tmp_path / "bad.BIN"
        path.write_bytes(b"\x00\x00" + bytes(40))

        with pytest.raises(ValueError, match="Invalid VX2730 BIN header"):
            VX2730BinReader().read_file(path)

    def test_truncated_file_raises(self, tmp_path):
        path = tmp_path / "run.BIN"
        path.write_bytes(make_vx2730_bin_bytes(_events(2))[:-3])

        with pytest.raises(ValueError, match="trailing bytes"):
            VX2730BinReader().read_file(path)

    def test_inconsistent_waveform_length_raises(self, tmp_path):
        events = _events(2)
        events[1]["n_samples"] = 5  # size stays aligned but declared length differs
        path = _write(tmp_path / "run.BIN", events)

        with pytest.raises(ValueError, match="Inconsistent VX2730 BIN waveform length"):
            VX2730BinReader().read_file(path)

    def test_invalid_events_per_chunk(self):
        with pytest.raises(ValueError):
            VX2730BinReader(events_per_chunk=0)


class TestVX2730BinLayout:
    def test_groups_and_natural_order(self, tmp_path):
        raw = tmp_path / "RAW"
        for name in [
            "SDataR_run_10.BIN",
            "SDataR_run.BIN",
            "SDataR_run_2.bin",
            "DataR_CH3@VX2730_53013_run.BIN",
            "notes.txt",
        ]:
            _write(raw / name, [])

        groups = VX2730_BIN_LAYOUT.group_files_by_channel(raw)

        assert sorted(groups) == [0, 3]
        assert [f["filename"] for f in groups[0]] == [
            "SDataR_run.BIN",
            "SDataR_run_2.bin",
            "SDataR_run_10.BIN",
        ]
        assert [f["index"] for f in groups[0]] == [0, 1, 2]
        assert [f["filename"] for f in groups[3]] == ["DataR_CH3@VX2730_53013_run.BIN"]

    def test_scan_run(self, tmp_path):
        path = _write(tmp_path / "DAQ" / "led" / "RAW" / "SDataR_led.BIN", _events(1))

        assert get_adapter("vx2730_bin").scan_run(str(tmp_path / "DAQ"), "led") == {0: [path]}


class TestVX2730BinRecords:
    def test_build_records_from_raw_files(self, tmp_path):
        n_samples = 60
        events = _events(5, n_samples=n_samples)
        events[2]["channel"] = 1
        path = _write(tmp_path / "run.BIN", events, n_samples=n_samples)

        bundle = build_records_from_raw_files(
            [[str(path)]], adapter_name="vx2730_bin", default_dt_ns=2
        )
        records = bundle.records

        assert len(records) == 5
        np.testing.assert_array_equal(
            np.sort(records["timestamp"]), [e["timestamp"] for e in events]
        )
        assert set(records["channel"].tolist()) == {0, 1}
        assert np.all(records["dt"] == 2)
        assert np.all(records["event_length"] == n_samples)
        for rec in records:
            source = next(e for e in events if e["timestamp"] == rec["timestamp"])
            start = int(rec["wave_offset"])
            wave = np.asarray(bundle.wave_pool[start : start + n_samples])
            np.testing.assert_array_equal(wave, source["samples"])
            assert rec["baseline"] == pytest.approx(np.mean(source["samples"][:40]))

    def test_records_rejects_st_waveforms_input(self):
        plugin = RecordsPlugin()
        ctx = FakeContext(
            config={"daq_adapter": "vx2730_bin", "records": {"input_source": "st_waveforms"}},
            plugins={"records": plugin},
        )

        with pytest.raises(ValueError, match="not supported for vx2730_bin"):
            plugin.resolve_depends_on(ctx)

    def test_st_waveforms_rejects_adapter(self):
        plugin = WaveformsPlugin()
        ctx = FakeContext(
            config={"daq_adapter": "vx2730_bin"},
            data={"raw_files": [["dummy.BIN"]]},
        )

        with pytest.raises(ValueError, match="not supported for vx2730_bin"):
            plugin.compute(ctx, "run_001")
