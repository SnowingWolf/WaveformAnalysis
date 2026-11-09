"""VX2730 CoMPASS binary (.BIN) adapter tests."""

import numpy as np
import pytest

from tests.daq_adapter_helpers import make_vx2730_bin_bytes
from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.records import RecordsPlugin
from waveform_analysis.core.plugins.builtin.st_waveforms.plugin import WaveformsPlugin
from waveform_analysis.core.plugins.builtin.wave_pool.plugin import WavePoolPlugin
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


def _write_continuation(path, events, **kwargs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(make_vx2730_bin_bytes(events, **kwargs)[2:])
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

    @pytest.mark.parametrize("first_name", ["run.BIN", "run_0.BIN", "CH0_0.BIN"])
    def test_headerless_continuation_all_read_modes(self, tmp_path, first_name):
        stem = first_name.removesuffix(".BIN").removesuffix("_0")
        events = _events(5)
        paths = [
            _write(tmp_path / first_name, events[:2]),
            _write_continuation(tmp_path / f"{stem}_1.BIN", events[2:]),
        ]
        reader = VX2730BinReader(events_per_chunk=2)
        expected = reader.read_file(_write(tmp_path / "expected.BIN", events))

        np.testing.assert_array_equal(reader.read_files(paths), expected)
        np.testing.assert_array_equal(np.vstack(list(reader.read_files_generator(paths))), expected)
        assert reader.count_total_rows(paths) == 5

        dtype = np.dtype([("timestamp", "<i8"), ("samples", "<i8", (4,))])

        def structurizer(chunk, output, offset):
            output["timestamp"][offset : offset + len(chunk)] = chunk[:, 2]
            output["samples"][offset : offset + len(chunk)] = chunk[:, 7:]
            return len(chunk)

        streamed = reader.read_files_streaming(paths, dtype, tmp_path / "out.dat", structurizer)
        np.testing.assert_array_equal(streamed["timestamp"], expected[:, 2])
        np.testing.assert_array_equal(streamed["samples"], expected[:, 7:])

    def test_headerless_read_file_requires_stream_context(self, tmp_path):
        path = _write_continuation(tmp_path / "run_1.BIN", _events(2))
        with pytest.raises(ValueError, match="Invalid VX2730 BIN header"):
            VX2730BinReader().read_file(path, is_first_file=False)

    @pytest.mark.parametrize("mode", ["full", "generator", "count"])
    @pytest.mark.parametrize("failure", ["header", "truncated", "samples", "order", "gap"])
    def test_continuation_validation(self, tmp_path, mode, failure):
        first = _write(tmp_path / "run.BIN", _events(1))
        second = _write_continuation(tmp_path / "run_1.BIN", _events(2))
        match = ""
        if failure == "header":
            second.write_bytes(b"\x00\x00" + second.read_bytes())
            match = "Invalid VX2730 BIN header"
        elif failure == "truncated":
            second.write_bytes(second.read_bytes()[:-1])
            match = "trailing bytes"
        elif failure == "samples":
            _write_continuation(second, _events(2, n_samples=5))
            match = "waveform length"
        elif failure == "gap":
            second = second.rename(tmp_path / "run_2.BIN")
            match = "segment order"
        paths = [second, first] if failure == "order" else [first, second]
        if failure == "order":
            match = "Invalid VX2730 BIN header"
        reader = VX2730BinReader()
        with pytest.raises(ValueError, match=match):
            if mode == "full":
                reader.read_files(paths)
            elif mode == "generator":
                list(reader.read_files_generator(paths))
            else:
                reader.count_total_rows(paths)

    def test_independent_headers_can_change_within_named_family(self, tmp_path):
        paths = [
            _write(tmp_path / "run.BIN", _events(1)),
            _write(tmp_path / "run_1.BIN", _events(1), header=0xCAEF),
            _write_continuation(tmp_path / "run_2.BIN", _events(1), header=0xCAEF),
        ]
        assert len(VX2730BinReader().read_files(paths)) == 3

    @pytest.mark.parametrize("names", [["run_1.BIN", "run_2.BIN"], ["run_2.BIN", "run.BIN"]])
    def test_independent_headers_allow_subsets_gaps_and_reverse_order(self, tmp_path, names):
        paths = [_write(tmp_path / name, _events(1)) for name in names]
        reader = VX2730BinReader()
        assert len(reader.read_files(paths)) == 2
        assert reader.count_total_rows(paths) == 2
        assert sum(len(chunk) for chunk in reader.read_files_generator(paths)) == 2

    @pytest.mark.parametrize("stem", ["run", "acquisition_20261030"])
    def test_headed_subset_can_anchor_continuation(self, tmp_path, stem):
        paths = [
            _write(tmp_path / f"{stem}_1.BIN", _events(1)),
            _write_continuation(tmp_path / f"{stem}_2.BIN", _events(1)),
        ]
        assert len(VX2730BinReader().read_files(paths)) == 2

    @pytest.mark.parametrize("other", ["CH1_1.BIN", "other/CH0_1.BIN", "other_run_1.BIN"])
    def test_header_not_inherited_across_streams(self, tmp_path, other):
        first = _write(tmp_path / "CH0_0.BIN", _events(1))
        second = _write_continuation(tmp_path / other, _events(1, channel=1, board=1))
        with pytest.raises(ValueError, match="Invalid VX2730 BIN header"):
            VX2730BinReader().read_files([first, second])

    def test_interleaved_streams_keep_their_own_header(self, tmp_path):
        paths = [
            _write(tmp_path / "CH0_0.BIN", _events(1), header=0xCAED),
            _write(tmp_path / "CH1_0.BIN", _events(1, channel=1), header=0xCAEF),
            _write_continuation(tmp_path / "CH0_1.BIN", _events(1)),
            _write_continuation(tmp_path / "CH1_1.BIN", _events(1, channel=1), header=0xCAEF),
        ]
        data = VX2730BinReader().read_files(paths)
        np.testing.assert_array_equal(data[:, 1], [0, 1, 0, 1])
        assert VX2730BinReader().count_total_rows(paths) == 4

    def test_numeric_run_name_can_anchor_continuation(self, tmp_path):
        paths = [
            _write(tmp_path / "run_20261030.BIN", _events(1)),
            _write_continuation(tmp_path / "run_20261030_1.BIN", _events(1)),
        ]
        assert VX2730BinReader().count_total_rows(paths) == 2

    def test_count_only_reads_layout_metadata(self, tmp_path, monkeypatch):
        events = _events(2)
        events[1]["n_samples"] = 5
        paths = [_write(tmp_path / "run.BIN", events)]

        def forbid_memmap(*args, **kwargs):
            pytest.fail("count_total_rows must not map event or waveform payloads")

        monkeypatch.setattr(np, "memmap", forbid_memmap)
        # Later event lengths are checked by actual reads, not a metadata-only count.
        assert VX2730BinReader().count_total_rows(paths) == 2

    def test_header_only_anchor_cannot_establish_headerless_layout(self, tmp_path):
        paths = [
            _write(tmp_path / "run.BIN", []),
            _write_continuation(tmp_path / "run_1.BIN", _events(1)),
        ]
        with pytest.raises(ValueError, match="No event layout established"):
            VX2730BinReader().count_total_rows(paths)

    def test_empty_intermediate_segment_preserves_established_layout(self, tmp_path):
        first = _write(tmp_path / "run.BIN", _events(1))
        empty = tmp_path / "run_1.BIN"
        empty.touch()
        last = _write_continuation(tmp_path / "run_2.BIN", _events(2))
        paths = [first, empty, last]
        reader = VX2730BinReader()
        assert reader.count_total_rows(paths) == 3
        assert len(reader.read_files(paths)) == 3
        assert sum(len(chunk) for chunk in reader.read_files_generator(paths)) == 3

    def test_empty_first_segment_cannot_establish_layout(self, tmp_path):
        first = tmp_path / "run.BIN"
        first.touch()
        second = _write_continuation(tmp_path / "run_1.BIN", _events(1))
        with pytest.raises(ValueError, match="Invalid VX2730 BIN header"):
            VX2730BinReader().count_total_rows([first, second])

    def test_valid_header_with_damaged_payload_never_uses_offset_zero(self, tmp_path):
        first = _write(tmp_path / "run.BIN", _events(1))
        second = _write(tmp_path / "run_1.BIN", _events(2))
        second.write_bytes(second.read_bytes()[:-2])
        with pytest.raises(ValueError, match="trailing bytes"):
            VX2730BinReader().count_total_rows([first, second])

    def test_headerless_continuation_without_waveform(self, tmp_path):
        events = _events(3)
        paths = [
            _write(tmp_path / "run.BIN", events[:1], header=0xCAE5),
            _write_continuation(tmp_path / "run_1.BIN", events[1:], header=0xCAE5),
        ]
        reader = VX2730BinReader()
        data = reader.read_files(paths)
        assert data.shape == (3, 7)
        assert reader.count_total_rows(paths) == 3
        np.testing.assert_array_equal(data[:, 2], [event["timestamp"] for event in events])

    def test_oversized_sample_count_is_rejected_before_dtype_allocation(self, tmp_path):
        events = _events(1)
        events[0]["n_samples"] = 2**32 - 1
        path = _write(tmp_path / "run.BIN", events)
        with pytest.raises(ValueError, match="Truncated VX2730 BIN waveform length"):
            VX2730BinReader().count_total_rows([path])


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
    def test_records_and_wave_pool_plugins_read_headerless_segments(self, tmp_path):
        events = _events(5, n_samples=60, board=1, channel=3)
        paths = [
            _write(tmp_path / "CH3_0.BIN", events[:2]),
            _write_continuation(tmp_path / "CH3_1.BIN", events[2:]),
        ]
        records_plugin = RecordsPlugin()
        pool_plugin = WavePoolPlugin()
        ctx = FakeContext(
            config={"daq_adapter": "vx2730_bin"},
            data={"raw_files": [[str(path) for path in paths]]},
            plugins={"records": records_plugin, "wave_pool": pool_plugin},
        )
        records = records_plugin.compute(ctx, "continuation")
        pool = pool_plugin.compute(ctx, "continuation")
        assert len(records) == len(events)
        assert np.all(records["board"] == 1)
        assert np.all(records["channel"] == 3)
        assert np.all(records["dt"] == 2)
        np.testing.assert_array_equal(
            records["timestamp"], [event["timestamp"] for event in events]
        )
        for rec, event in zip(records, events, strict=True):
            start = int(rec["wave_offset"])
            np.testing.assert_array_equal(pool[start : start + 60], event["samples"])

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
