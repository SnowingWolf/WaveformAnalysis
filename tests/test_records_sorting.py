from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from tests.daq_adapter_helpers import make_v1725_single_wave_blob
from waveform_analysis.core.foundation.utils import Profiler
from waveform_analysis.core.processing.dtypes import create_record_dtype
from waveform_analysis.core.processing.records_builder import (
    RECORDS_DTYPE,
    RecordsBundle,
    RecordsBundleRef,
    _concat_wave_pool_part_refs_to_disk,
    _copy_wave_pool_part_bytes,
    _merge_records_only_part_refs_to_disk,
    _merge_records_part_refs,
    _merge_records_part_refs_batched_to_disk,
    _merge_records_part_refs_records_only_to_disk,
    _RecordsPartRef,
    _resolve_v1725_file_workers,
    _write_records_part,
    build_records_from_raw_files,
    build_records_from_st_waveforms,
    build_records_from_st_waveforms_sharded,
    build_records_from_v1725_files,
)

# 本模块默认使用 4 个采样点的 v1725 blob（区别于共享 helper 的默认 2 个采样点）。
_DEFAULT_V1725_SAMPLES = np.array([11, 12, 13, 14], dtype=np.int16)


def _make_st_waveforms() -> np.ndarray:
    dtype = create_record_dtype(4)
    data = np.zeros(6, dtype=dtype)
    data["board"] = [0, 0, 0, 1, 1, 1]
    data["channel"] = [1, 0, 1, 0, 1, 0]
    data["timestamp"] = [300, 100, 100, 250, 100, 200]
    data["baseline"] = 0.0
    data["record_id"] = [30, 10, 11, 25, 12, 20]
    data["event_length"] = [4, 4, 4, 4, 4, 4]
    data["wave"] = np.arange(4, dtype=np.int16)
    return data


def _waves_by_timestamp(records: np.ndarray, wave_pool: np.ndarray) -> dict[int, np.ndarray]:
    waves = {}
    for rec in records:
        offset = int(rec["wave_offset"])
        length = int(rec["event_length"])
        waves[int(rec["timestamp"])] = np.asarray(wave_pool[offset : offset + length])
    return waves


def test_build_records_from_st_waveforms_sorts_globally_by_timestamp():
    bundle = build_records_from_st_waveforms(_make_st_waveforms(), default_dt_ns=2)

    np.testing.assert_array_equal(
        bundle.records["timestamp"], np.array([100, 100, 100, 200, 250, 300])
    )
    np.testing.assert_array_equal(
        bundle.records["board"], np.array([0, 0, 1, 1, 1, 0], dtype=np.int16)
    )
    np.testing.assert_array_equal(
        bundle.records["channel"], np.array([0, 1, 1, 0, 0, 1], dtype=np.int16)
    )
    np.testing.assert_array_equal(
        bundle.records["record_id"], np.array([10, 11, 12, 20, 25, 30], dtype=np.int64)
    )


def test_build_records_from_st_waveforms_sharded_keeps_global_timestamp_order():
    st_waveforms = _make_st_waveforms()

    baseline = build_records_from_st_waveforms(st_waveforms, default_dt_ns=2)
    sharded = build_records_from_st_waveforms_sharded(st_waveforms, part_size=2, default_dt_ns=2)

    np.testing.assert_array_equal(sharded.records["timestamp"], baseline.records["timestamp"])
    np.testing.assert_array_equal(sharded.records["board"], baseline.records["board"])
    np.testing.assert_array_equal(sharded.records["channel"], baseline.records["channel"])
    np.testing.assert_array_equal(sharded.records["record_id"], baseline.records["record_id"])
    np.testing.assert_array_equal(sharded.wave_pool, baseline.wave_pool)


@pytest.mark.parametrize("use_numba", [True, False])
def test_records_only_stable_kway_matches_numpy_oracle_for_ties_and_empty_parts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, use_numba: bool
):
    """The direct out-of-core merge is byte-identical to the legacy oracle."""
    from waveform_analysis.core.processing import records_builder as builder

    if not use_numba:
        monkeypatch.setattr(builder, "_NUMBA_AVAILABLE", False)

    rows_by_part = [
        [(10, 0, 0, 0, 11), (20, 0, 0, 0, 12), (20, 0, 0, 1, 13)],
        [(10, 0, 0, 0, 21), (20, 0, 0, 0, 22), (30, 0, 0, 0, 23)],
        [(20, 0, 0, 0, 31), (20, 0, 0, 1, 32), (30, 0, 0, 0, 33)],
    ]
    (tmp_path / "parts").mkdir()
    parts = []
    for part_idx, rows in enumerate(rows_by_part):
        records = np.zeros(len(rows), dtype=RECORDS_DTYPE)
        for row_idx, (timestamp, pid, board, channel, wave_offset) in enumerate(rows):
            records[row_idx]["timestamp"] = timestamp
            records[row_idx]["pid"] = pid
            records[row_idx]["board"] = board
            records[row_idx]["channel"] = channel
            records[row_idx]["wave_offset"] = wave_offset
            records[row_idx]["event_length"] = 0
            records[row_idx]["record_id"] = 100 + part_idx * 10 + row_idx
        part = _write_records_part(
            RecordsBundle(records, np.zeros(0, dtype=np.uint16)), tmp_path / "parts", part_idx
        )
        assert part is not None
        parts.append(part)
    builder._ensure_source_sequence_starts(parts)

    # The first-level merge represents the same sorted intermediate refs used
    # by the indexed disk path when the input has multiple parts.
    batch_parts = [
        _merge_records_part_refs_records_only_to_disk(
            parts[:2], [0, 0], tmp_path / "batches", part_idx=0, assign_record_ids=False
        ),
        _merge_records_part_refs_records_only_to_disk(
            parts[2:], [0], tmp_path / "batches", part_idx=1, assign_record_ids=False
        ),
    ]
    assert all(part is not None for part in batch_parts)

    source = np.concatenate(
        [
            np.asarray(
                np.memmap(part.records_path, dtype=RECORDS_DTYPE, mode="r", shape=(part.n_records,))
            )
            for part in parts
        ]
    )
    order = np.lexsort(
        (
            np.arange(len(source), dtype=np.int64),
            source["channel"],
            source["board"],
            source["pid"],
            source["timestamp"],
        )
    )
    expected = source[order].copy()
    expected["record_id"] = np.arange(len(expected), dtype=np.int64)

    merged = _merge_records_only_part_refs_to_disk(
        [part for part in batch_parts if part is not None], tmp_path / "final"
    )
    assert merged is not None
    assert merged.source_sequence_start == 0
    assert not list((tmp_path / "final").glob("records_unsorted_*.dat"))
    actual = np.memmap(
        merged.records_path, dtype=RECORDS_DTYPE, mode="r", shape=(merged.n_records,)
    )
    assert actual.dtype == RECORDS_DTYPE
    assert actual.shape == expected.shape
    assert actual.tobytes() == expected.tobytes()
    actual._mmap.close()


def test_records_only_stable_kway_empty_input_returns_none(tmp_path: Path):
    assert _merge_records_only_part_refs_to_disk([], tmp_path) is None


def test_wave_pool_concat_copies_exact_raw_bytes_in_part_order(tmp_path: Path):
    parts = []
    expected = b""
    for part_idx, values in enumerate(([0, 1, 65535], [7, 8])):
        wave_pool_path = tmp_path / f"wave_pool_part_{part_idx}.dat"
        payload = np.asarray(values, dtype=np.uint16).tobytes()
        wave_pool_path.write_bytes(payload)
        expected += payload
        parts.append(
            _RecordsPartRef(
                records_path=tmp_path / f"records_part_{part_idx}.dat",
                wave_pool_path=wave_pool_path,
                n_records=0,
                n_samples=len(values),
            )
        )

    output = _concat_wave_pool_part_refs_to_disk(parts, tmp_path / "merged")

    assert output is not None
    assert output.read_bytes() == expected
    assert output.stat().st_size == sum(part.n_samples for part in parts) * 2
    loaded = np.memmap(output, dtype=np.uint16, mode="r", shape=(5,))
    np.testing.assert_array_equal(loaded, np.array([0, 1, 65535, 7, 8], dtype=np.uint16))
    loaded._mmap.close()


@pytest.mark.parametrize("payload", [b"\x01", b"\x01\x02\x03\x04\x05"])
def test_wave_pool_concat_rejects_non_exact_part_size(tmp_path: Path, payload: bytes):
    wave_pool_path = tmp_path / "wave_pool_part.dat"
    wave_pool_path.write_bytes(payload)
    part = _RecordsPartRef(
        records_path=tmp_path / "records_part.dat",
        wave_pool_path=wave_pool_path,
        n_records=0,
        n_samples=2,
    )

    with pytest.raises(RuntimeError, match="size mismatch.*exactly 4 bytes"):
        _concat_wave_pool_part_refs_to_disk([part], tmp_path / "merged")
    assert not (tmp_path / "merged" / "wave_pool_merged_0.dat").exists()
    assert not (tmp_path / "merged" / ".wave_pool_merged_0.dat.tmp").exists()


class _ShortReadFile:
    def __init__(self, payload: bytes):
        self._payload = payload
        self._read = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, _size: int) -> bytes:
        if self._read:
            return b""
        self._read = True
        return self._payload


class _DeclaredSizePath:
    def __init__(self, payload: bytes, declared_size: int):
        self._payload = payload
        self._declared_size = declared_size

    def stat(self):
        return SimpleNamespace(st_size=self._declared_size)

    def open(self, *_args, **_kwargs):
        return _ShortReadFile(self._payload)


def test_wave_pool_concat_rejects_short_read_after_exact_stat():
    part = _RecordsPartRef(
        records_path=Path("records.dat"),
        wave_pool_path=_DeclaredSizePath(b"\x01\x02", declared_size=4),
        n_records=0,
        n_samples=2,
    )

    with pytest.raises(RuntimeError, match="short read.*2 bytes remaining"):
        _copy_wave_pool_part_bytes(part, BytesIO(), part_idx_local=0)


class _ShortWriter:
    def write(self, payload: bytes) -> int:
        return len(payload) - 1


def test_wave_pool_concat_rejects_short_write(tmp_path: Path):
    wave_pool_path = tmp_path / "wave_pool_part.dat"
    wave_pool_path.write_bytes(b"\x01\x02")
    part = _RecordsPartRef(
        records_path=tmp_path / "records_part.dat",
        wave_pool_path=wave_pool_path,
        n_records=0,
        n_samples=1,
    )

    with pytest.raises(RuntimeError, match="short write.*expected 2 bytes, got 1"):
        _copy_wave_pool_part_bytes(part, _ShortWriter(), part_idx_local=0)


def test_build_records_from_v1725_files_sorts_approximately_ordered_input(tmp_path: Path):
    raw0 = tmp_path / "test_raw_b3_seg0.bin"
    raw1 = tmp_path / "test_raw_b4_seg1.bin"
    raw0.write_bytes(
        make_v1725_single_wave_blob(
            channel=1, timestamp=30, baseline=100, samples=_DEFAULT_V1725_SAMPLES
        )
    )
    raw1.write_bytes(
        make_v1725_single_wave_blob(
            channel=0, timestamp=10, baseline=200, samples=_DEFAULT_V1725_SAMPLES
        )
    )

    bundle = build_records_from_v1725_files([str(raw0), str(raw1)], dt_ns=4)

    np.testing.assert_array_equal(
        bundle.records["timestamp"], np.array([40_000, 120_000], dtype=np.int64)
    )
    np.testing.assert_array_equal(bundle.records["board"], np.array([4, 3], dtype=np.int16))
    np.testing.assert_array_equal(bundle.records["channel"], np.array([0, 1], dtype=np.int16))
    np.testing.assert_array_equal(bundle.records["record_id"], np.arange(2, dtype=np.int64))


@pytest.mark.parametrize("batch_size", [1, 50])
@pytest.mark.parametrize("executor_type", ["thread", "process"])
def test_build_records_from_v1725_files_keeps_disk_refs_after_tempdir_cleanup(
    tmp_path: Path, batch_size: int, executor_type: str
):
    raws = []
    for idx, timestamp in enumerate([30, 10, 20]):
        raw = tmp_path / f"test_raw_b{idx}_seg0.bin"
        raw.write_bytes(
            make_v1725_single_wave_blob(
                channel=idx,
                timestamp=timestamp,
                baseline=100 + idx,
                samples=np.array([idx, idx + 1, idx + 2, idx + 3], dtype=np.int16),
            )
        )
        raws.append(str(raw))

    bundle_ref = build_records_from_v1725_files(
        raws,
        dt_ns=4,
        batch_size=batch_size,
        executor_type=executor_type,
        n_jobs=2,
        keep_on_disk=True,
    )

    assert isinstance(bundle_ref, RecordsBundleRef)
    assert bundle_ref.temp_dir is not None
    assert bundle_ref.temp_dir.exists()
    assert all(part.records_path.exists() for part in bundle_ref.part_refs)
    assert all(part.wave_pool_path.exists() for part in bundle_ref.part_refs)
    assert set(bundle_ref.temp_dir.rglob("*.dat")) == {
        bundle_ref.part_refs[0].records_path,
        bundle_ref.part_refs[0].wave_pool_path,
    }
    assert list(bundle_ref.temp_dir.iterdir()) == [bundle_ref.temp_dir / "merged"]
    assert all(part.records_path.parent != Path("/tmp/merged") for part in bundle_ref.part_refs)

    loaded = bundle_ref.load_full()
    np.testing.assert_array_equal(
        loaded.records["timestamp"], np.array([40_000, 80_000, 120_000], dtype=np.int64)
    )
    np.testing.assert_array_equal(loaded.records["record_id"], np.arange(3, dtype=np.int64))
    np.testing.assert_array_equal(loaded.records["wave_offset"], np.array([4, 8, 0]))
    np.testing.assert_array_equal(
        loaded.wave_pool,
        np.array([0, 1, 2, 3, 1, 2, 3, 4, 2, 3, 4, 5], dtype=np.uint16),
    )
    waves = _waves_by_timestamp(loaded.records, loaded.wave_pool)
    np.testing.assert_array_equal(waves[40_000], np.array([1, 2, 3, 4], dtype=np.uint16))
    np.testing.assert_array_equal(waves[80_000], np.array([2, 3, 4, 5], dtype=np.uint16))
    np.testing.assert_array_equal(waves[120_000], np.array([0, 1, 2, 3], dtype=np.uint16))

    ref_dir = bundle_ref.temp_dir
    bundle_ref.cleanup()
    assert not ref_dir.exists()


def test_build_records_from_v1725_files_run_merge_keeps_variable_wave_offsets(tmp_path: Path):
    raws = []
    expected_waves_by_timestamp = []
    for board, timestamps in enumerate(([10, 20, 30], [25, 35])):
        raw = tmp_path / f"test_raw_b{board}_seg0.bin"
        blobs = []
        for idx, timestamp in enumerate(timestamps):
            samples = np.arange(
                board * 100 + idx * 10,
                board * 100 + idx * 10 + (idx + 1) * 2,
                dtype=np.int16,
            )
            blobs.append(
                make_v1725_single_wave_blob(
                    channel=board,
                    timestamp=timestamp,
                    baseline=100 + board,
                    samples=samples,
                )
            )
            expected_waves_by_timestamp.append((timestamp * 4_000, samples.astype(np.uint16)))
        raw.write_bytes(b"".join(blobs))
        raws.append(str(raw))

    bundle = build_records_from_v1725_files(raws, dt_ns=4, v1725_part_size=3)

    expected_waves_by_timestamp.sort(key=lambda item: item[0])
    expected_timestamps = np.array(
        [item[0] for item in expected_waves_by_timestamp], dtype=np.int64
    )
    expected_lengths = np.array(
        [len(item[1]) for item in expected_waves_by_timestamp], dtype=np.int32
    )
    expected_offsets = np.concatenate(([0], np.cumsum(expected_lengths[:-1]))).astype(np.int64)
    expected_pool = np.concatenate([item[1] for item in expected_waves_by_timestamp])

    np.testing.assert_array_equal(bundle.records["timestamp"], expected_timestamps)
    np.testing.assert_array_equal(bundle.records["event_length"], expected_lengths)
    np.testing.assert_array_equal(bundle.records["wave_offset"], expected_offsets)
    np.testing.assert_array_equal(bundle.records["record_id"], np.arange(5, dtype=np.int64))
    np.testing.assert_array_equal(bundle.wave_pool, expected_pool)


@pytest.mark.parametrize("batch_size", [1, 50])
def test_v1725_reclaim_closes_mappings_and_preserves_variable_waves(
    tmp_path, monkeypatch, batch_size
):
    from waveform_analysis.core.processing import records_builder as builder

    raw = tmp_path / "test_raw_b0_seg0.bin"
    raw.write_bytes(
        b"".join(
            make_v1725_single_wave_blob(
                channel=0, timestamp=timestamp, samples=np.arange(length, dtype=np.int16)
            )
            for timestamp, length in [(30, 6), (10, 2), (20, 4)]
        )
    )
    mappings = []
    original_memmap = np.memmap

    class TrackedMemmap(original_memmap):
        def __new__(cls, *args, **kwargs):
            value = super().__new__(cls, *args, **kwargs)
            mappings.append(value._mmap)
            return value

    reclaim = builder._reclaim_v1725_merge_inputs
    reclaimed = []

    def checked_reclaim(part_dir, parts, result):
        assert mappings and all(mapping.closed for mapping in mappings)
        before = sum(path.stat().st_size for path in part_dir.rglob("*.dat"))
        reclaim(part_dir, parts, result)
        assert all(mapping.closed for mapping in mappings)
        after = sum(path.stat().st_size for path in part_dir.rglob("*.dat"))
        assert after == result.total_records * RECORDS_DTYPE.itemsize + result.total_samples * 2
        assert before >= 2 * after
        reclaimed.append(part_dir)

    monkeypatch.setattr(builder.np, "memmap", TrackedMemmap)
    monkeypatch.setattr(builder, "_reclaim_v1725_merge_inputs", checked_reclaim)
    result = build_records_from_v1725_files(
        [str(raw)],
        dt_ns=4,
        n_jobs=1,
        v1725_part_size=1,
        batch_size=batch_size,
        keep_on_disk=True,
    )
    try:
        assert reclaimed == [result.temp_dir]
        loaded = result.load_full()
        waves = _waves_by_timestamp(loaded.records, loaded.wave_pool)
        for timestamp, length in [(30, 6), (10, 2), (20, 4)]:
            np.testing.assert_array_equal(waves[timestamp * 4000], np.arange(length))
    finally:
        result.cleanup()


@pytest.mark.parametrize("damage", ["size", "offset", "length", "count", "alias"])
def test_v1725_reclaim_validates_all_output_before_deleting(tmp_path, damage):
    from waveform_analysis.core.processing.records_builder import _reclaim_v1725_merge_inputs

    source = tmp_path / "file_0"
    source.mkdir()
    records = np.zeros(2, dtype=RECORDS_DTYPE)
    records["timestamp"] = [1, 2]
    records["event_length"] = 2
    records["wave_offset"] = [0, 2]
    part = _write_records_part(RecordsBundle(records, np.arange(4, dtype=np.uint16)), source, 0)
    result = _merge_records_part_refs(
        [part],
        keep_on_disk=True,
        output_dir=tmp_path,
        transfer_temp_dir_ownership=True,
    )
    # The shared merger must leave caller-owned inputs available for reuse.
    originals = {path: path.read_bytes() for path in (part.records_path, part.wave_pool_path)}
    final = result.part_refs[0]
    if damage == "size":
        final.wave_pool_path.write_bytes(b"\0")
    elif damage in {"offset", "length"}:
        mapped = np.memmap(final.records_path, dtype=RECORDS_DTYPE, mode="r+")
        mapped["wave_offset" if damage == "offset" else "event_length"][0] = 100
        mapped.flush()
        mapped._mmap.close()
    elif damage == "count":
        result.total_records += 1
    else:
        final.wave_pool_path = part.wave_pool_path
    with pytest.raises(RuntimeError, match="V1725"):
        _reclaim_v1725_merge_inputs(tmp_path, [part], result)
    assert all(path.read_bytes() == data for path, data in originals.items())


def test_build_records_from_v1725_files_disk_batch_merge_uses_disk_parts(tmp_path: Path):
    raws = []
    for board, timestamp in enumerate([10, 20, 30, 40]):
        raw = tmp_path / f"test_raw_b{board}_seg0.bin"
        raw.write_bytes(
            make_v1725_single_wave_blob(
                channel=board,
                timestamp=timestamp,
                baseline=board,
                samples=np.array([board, board + 10, board + 20, board + 30], dtype=np.int16),
            )
        )
        raws.append(str(raw))

    bundle_ref = build_records_from_v1725_files(
        raws,
        dt_ns=4,
        batch_size=2,
        keep_on_disk=True,
    )

    assert isinstance(bundle_ref, RecordsBundleRef)
    assert bundle_ref.temp_dir is not None
    assert bundle_ref.part_refs[0].records_path.parent.name == "merged"
    assert not (bundle_ref.temp_dir / "merged" / "records_only_batches").exists()

    loaded = bundle_ref.load_full()
    np.testing.assert_array_equal(
        loaded.records["timestamp"], np.array([40_000, 80_000, 120_000, 160_000])
    )
    np.testing.assert_array_equal(loaded.records["wave_offset"], np.array([0, 4, 8, 12]))
    np.testing.assert_array_equal(
        loaded.wave_pool,
        np.array(
            [0, 10, 20, 30, 1, 11, 21, 31, 2, 12, 22, 32, 3, 13, 23, 33],
            dtype=np.uint16,
        ),
    )
    bundle_ref.cleanup()


def test_build_records_from_v1725_files_shows_disk_batch_merge_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    progress_bars = []

    class FakeTqdm:
        def __init__(self, total, desc, leave):  # noqa: ANN001
            self.total = total
            self.desc = desc
            self.leave = leave
            self.updates = 0
            self.closed = False
            progress_bars.append(self)

        def update(self, value):  # noqa: ANN001
            self.updates += value

        def close(self):
            self.closed = True

    monkeypatch.setitem(sys.modules, "tqdm", SimpleNamespace(tqdm=FakeTqdm))

    raws = []
    for board, timestamp in enumerate([10, 20, 30, 40]):
        raw = tmp_path / f"test_raw_b{board}_seg0.bin"
        raw.write_bytes(
            make_v1725_single_wave_blob(
                channel=board,
                timestamp=timestamp,
                baseline=board,
                samples=np.array([board, board + 1], dtype=np.int16),
            )
        )
        raws.append(str(raw))

    bundle_ref = build_records_from_v1725_files(
        raws,
        dt_ns=4,
        batch_size=2,
        keep_on_disk=True,
        show_progress=True,
    )
    bundle_ref.cleanup()

    merge_progress = next(bar for bar in progress_bars if bar.desc == "Merging records (disk)")
    assert merge_progress.total == 2
    assert merge_progress.updates == 2
    assert merge_progress.closed is True
    assert merge_progress.leave is False


def test_build_records_from_v1725_files_disk_concat_fast_path(tmp_path: Path):
    raws = []
    for board, timestamp in enumerate([10, 20, 30]):
        raw = tmp_path / f"test_raw_b{board}_seg0.bin"
        raw.write_bytes(
            make_v1725_single_wave_blob(
                channel=board,
                timestamp=timestamp,
                baseline=board,
                samples=np.array([board, board + 1], dtype=np.int16),
            )
        )
        raws.append(str(raw))

    profiler = Profiler()
    bundle_ref = build_records_from_v1725_files(
        raws,
        dt_ns=4,
        batch_size=10,
        keep_on_disk=True,
        profiler=profiler,
    )

    assert isinstance(bundle_ref, RecordsBundleRef)
    assert len(bundle_ref.part_refs) == 1
    assert profiler.counts["records.merge.records_only.disk"] == 1
    assert profiler.counts["records.merge.wave_pool_concat.disk"] == 1

    loaded = bundle_ref.load_full()
    np.testing.assert_array_equal(loaded.records["timestamp"], np.array([40_000, 80_000, 120_000]))
    np.testing.assert_array_equal(loaded.records["wave_offset"], np.array([0, 2, 4]))
    np.testing.assert_array_equal(
        loaded.wave_pool,
        np.array([0, 1, 1, 2, 2, 3], dtype=np.uint16),
    )
    bundle_ref.cleanup()


def test_disk_batch_merge_uses_requested_executor_type(tmp_path: Path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    part_dir = tmp_path / "parts"
    part_dir.mkdir()
    parts = []
    for idx, timestamp in enumerate([10, 20, 30, 40]):
        records = np.zeros(1, dtype=RECORDS_DTYPE)
        records["timestamp"] = timestamp
        records["pid"] = 0
        records["board"] = idx
        records["channel"] = idx
        records["record_id"] = idx
        records["event_length"] = 2
        records["wave_offset"] = 0
        records["time"] = timestamp
        bundle = RecordsBundle(
            records=records,
            wave_pool=np.array([idx, idx + 1], dtype=np.uint16),
        )
        part = _write_records_part(bundle, part_dir, idx)
        assert part is not None
        parts.append(part)

    captured = {}

    def fake_get_executor(name, executor_type, max_workers, reuse):  # noqa: ANN001
        captured["name"] = name
        captured["executor_type"] = executor_type
        captured["max_workers"] = max_workers
        captured["reuse"] = reuse
        return ThreadPoolExecutor(max_workers=max_workers)

    monkeypatch.setattr(
        "waveform_analysis.core.execution.manager.get_executor",
        fake_get_executor,
    )

    merged = _merge_records_part_refs_batched_to_disk(
        parts,
        batch_size=1,
        output_dir=tmp_path / "merged",
        n_workers=2,
        executor_type="process",
    )

    assert captured == {
        "name": "records_batch_merge",
        "executor_type": "process",
        "max_workers": 2,
        "reuse": True,
    }
    assert len(merged) == 4


def test_disk_indexed_merge_uses_requested_executor_type(tmp_path: Path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    part_dir = tmp_path / "parts"
    part_dir.mkdir()
    parts = []
    for idx, timestamp in enumerate([30, 10, 40, 20]):
        records = np.zeros(1, dtype=RECORDS_DTYPE)
        records["timestamp"] = timestamp
        records["pid"] = 0
        records["board"] = idx
        records["channel"] = idx
        records["record_id"] = idx
        records["event_length"] = 2
        records["wave_offset"] = 0
        records["time"] = timestamp
        bundle = RecordsBundle(
            records=records,
            wave_pool=np.array([idx, idx + 1], dtype=np.uint16),
        )
        part = _write_records_part(bundle, part_dir, idx)
        assert part is not None
        parts.append(part)

    captured = {}

    def fake_get_executor(name, executor_type, max_workers, reuse):  # noqa: ANN001
        captured["name"] = name
        captured["executor_type"] = executor_type
        captured["max_workers"] = max_workers
        captured["reuse"] = reuse
        return ThreadPoolExecutor(max_workers=max_workers)

    monkeypatch.setattr(
        "waveform_analysis.core.execution.manager.get_executor",
        fake_get_executor,
    )

    bundle_ref = _merge_records_part_refs(
        parts,
        batch_size=1,
        keep_on_disk=True,
        output_dir=tmp_path / "bundle",
        n_workers=2,
        executor_type="process",
    )

    assert isinstance(bundle_ref, RecordsBundleRef)
    assert captured == {
        "name": "records_only_batch_merge",
        "executor_type": "process",
        "max_workers": 2,
        "reuse": True,
    }
    loaded = bundle_ref.load_full()
    np.testing.assert_array_equal(loaded.records["timestamp"], np.array([10, 20, 30, 40]))
    np.testing.assert_array_equal(loaded.records["wave_offset"], np.array([2, 6, 0, 4]))
    np.testing.assert_array_equal(
        loaded.wave_pool,
        np.array([0, 1, 1, 2, 2, 3, 3, 4], dtype=np.uint16),
    )


def test_resolve_v1725_file_workers_uses_io_friendly_auto_default():
    assert _resolve_v1725_file_workers(0, None) == 1
    assert _resolve_v1725_file_workers(2, None) == 2
    assert _resolve_v1725_file_workers(14, None) == 4
    assert _resolve_v1725_file_workers(14, 8) == 8
    assert _resolve_v1725_file_workers(14, 0) == 1


def test_build_records_from_v1725_files_rejects_implicit_over_budget_disk_ref(tmp_path: Path):
    raw = tmp_path / "test_raw_b0_seg0.bin"
    raw.write_bytes(
        make_v1725_single_wave_blob(
            channel=0, timestamp=10, baseline=100, samples=_DEFAULT_V1725_SAMPLES
        )
    )

    with pytest.raises(MemoryError, match="keep_on_disk=True"):
        build_records_from_v1725_files(
            [str(raw)],
            dt_ns=4,
            memory_budget_gb=0.0,
        )


def test_build_records_from_raw_files_sorts_globally_without_materializing_st_waveforms():
    file_map = {
        "ch1_0.csv": np.array(
            [
                [0, 1, 3000, 0, 0, 0, 0, 1, 2, 3, 4],
                [0, 1, 1000, 0, 0, 0, 0, 5, 6, 7, 8],
            ],
            dtype=np.int64,
        ),
        "ch0_0.csv": np.array(
            [
                [0, 0, 2000, 0, 0, 0, 0, 9, 10, 11, 12],
            ],
            dtype=np.int64,
        ),
    }

    class MockReader:
        def __init__(self):
            self.calls = []

        def read_file(self, file_path, is_first_file=True):  # noqa: ARG002
            return file_map[str(file_path)]

        def read_files_generator(
            self,
            file_paths,
            chunk_size=1,
            **kwargs,
        ):  # noqa: ARG002
            self.calls.append({"file_paths": list(file_paths), "chunk_size": chunk_size, **kwargs})
            for idx, file_path in enumerate(file_paths):
                yield self.read_file(file_path, is_first_file=(idx == 0))

    reader = MockReader()
    mock_adapter = SimpleNamespace(
        format_reader=reader,
        format_spec=SimpleNamespace(
            columns=SimpleNamespace(
                board=0,
                channel=1,
                timestamp=2,
                samples_start=7,
                samples_end=None,
                baseline_start=7,
                baseline_end=9,
            ),
            normalize_timestamp_to_ps=lambda timestamps, dt_ns: timestamps,
        ),
    )

    with patch("waveform_analysis.utils.formats.get_adapter", return_value=mock_adapter):
        bundle = build_records_from_raw_files(
            [["ch1_0.csv"], ["ch0_0.csv"]],
            adapter_name="mock",
            default_dt_ns=2,
            part_size=1,
            epoch_ns=100,
            parse_engine="pyarrow",
            n_jobs=3,
            chunksize=512,
            use_process_pool=True,
        )

    np.testing.assert_array_equal(bundle.records["timestamp"], np.array([1000, 2000, 3000]))
    np.testing.assert_array_equal(bundle.records["channel"], np.array([1, 0, 1], dtype=np.int16))
    np.testing.assert_array_equal(bundle.records["record_id"], np.arange(3, dtype=np.int64))
    np.testing.assert_allclose(bundle.records["baseline"], np.array([5.5, 9.5, 1.5]))
    np.testing.assert_array_equal(bundle.records["time"], np.array([101, 102, 103], dtype=np.int64))
    np.testing.assert_array_equal(
        bundle.wave_pool,
        np.array([5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4], dtype=np.uint16),
    )
    assert reader.calls[0]["parse_engine"] == "pyarrow"
    assert reader.calls[0]["n_jobs"] == 3
    assert reader.calls[0]["chunksize"] == 512
    assert reader.calls[0]["use_process_pool"] is True


def test_build_records_from_raw_files_does_not_use_python_wave_list_path():
    raw_arr = np.array(
        [
            [0, 0, 1000, 0, 0, 0, 0, 10, 11, 12, 13],
            [0, 0, 2000, 0, 0, 0, 0, 20, 21, 22, 23],
        ],
        dtype=np.int64,
    )

    class MockReader:
        def read_files_generator(self, file_paths, chunk_size=1, **kwargs):  # noqa: ARG002
            yield raw_arr

    mock_adapter = SimpleNamespace(
        format_reader=MockReader(),
        format_spec=SimpleNamespace(
            columns=SimpleNamespace(
                board=0,
                channel=1,
                timestamp=2,
                samples_start=7,
                samples_end=None,
                baseline_start=7,
                baseline_end=9,
            ),
            normalize_timestamp_to_ps=lambda timestamps, dt_ns: timestamps,
        ),
    )

    with patch("waveform_analysis.utils.formats.get_adapter", return_value=mock_adapter):
        with patch(
            "waveform_analysis.core.processing.records_builder._build_records_from_wave_list",
            side_effect=AssertionError("raw builder should not call _build_records_from_wave_list"),
        ):
            bundle = build_records_from_raw_files(
                [["ch0_0.csv"]],
                adapter_name="mock",
                default_dt_ns=2,
                part_size=None,
            )

    np.testing.assert_array_equal(
        bundle.records["timestamp"], np.array([1000, 2000], dtype=np.int64)
    )
    np.testing.assert_array_equal(
        bundle.wave_pool,
        np.array([10, 11, 12, 13, 20, 21, 22, 23], dtype=np.uint16),
    )


def test_build_records_from_raw_files_profiles_read_build_and_merge():
    raw_arr = np.array(
        [
            [0, 0, 3000, 0, 0, 0, 0, 1, 2],
            [0, 0, 1000, 0, 0, 0, 0, 3, 4],
            [0, 0, 2000, 0, 0, 0, 0, 5, 6],
        ],
        dtype=np.int64,
    )

    class MockReader:
        def read_files_generator(self, file_paths, chunk_size=1, **kwargs):  # noqa: ARG002
            yield raw_arr[:2]
            yield raw_arr[2:]

    mock_adapter = SimpleNamespace(
        format_reader=MockReader(),
        format_spec=SimpleNamespace(
            columns=SimpleNamespace(
                board=0,
                channel=1,
                timestamp=2,
                samples_start=7,
                samples_end=None,
                baseline_start=7,
                baseline_end=9,
            ),
            normalize_timestamp_to_ps=lambda timestamps, dt_ns: timestamps,
        ),
    )
    profiler = Profiler()

    with patch("waveform_analysis.utils.formats.get_adapter", return_value=mock_adapter):
        build_records_from_raw_files(
            [["ch0_0.csv"]],
            adapter_name="mock",
            default_dt_ns=2,
            part_size=2,
            profiler=profiler,
        )

    assert profiler.counts["records.read"] == 2
    assert profiler.counts["records.part_build"] == 2
    assert profiler.counts["records.merge"] == 1


def test_build_records_from_raw_files_supports_channel_parallelism():
    file_map = {
        "ch0_0.csv": np.array([[0, 0, 2000, 0, 0, 0, 0, 9, 10, 11, 12]], dtype=np.int64),
        "ch1_0.csv": np.array([[0, 1, 1000, 0, 0, 0, 0, 5, 6, 7, 8]], dtype=np.int64),
    }

    class MockReader:
        def read_files_generator(self, file_paths, chunk_size=1, **kwargs):  # noqa: ARG002
            for file_path in file_paths:
                yield file_map[str(file_path)]

    def make_adapter():
        return SimpleNamespace(
            format_reader=MockReader(),
            format_spec=SimpleNamespace(
                columns=SimpleNamespace(
                    board=0,
                    channel=1,
                    timestamp=2,
                    samples_start=7,
                    samples_end=None,
                    baseline_start=7,
                    baseline_end=9,
                ),
                normalize_timestamp_to_ps=lambda timestamps, dt_ns: timestamps,
            ),
        )

    profiler = Profiler()
    with patch(
        "waveform_analysis.utils.formats.get_adapter", side_effect=lambda name: make_adapter()
    ):
        bundle = build_records_from_raw_files(
            [["ch0_0.csv"], ["ch1_0.csv"]],
            adapter_name="mock",
            default_dt_ns=2,
            part_size=None,
            channel_workers=2,
            channel_executor="thread",
            profiler=profiler,
        )

    np.testing.assert_array_equal(
        bundle.records["timestamp"], np.array([1000, 2000], dtype=np.int64)
    )
    np.testing.assert_array_equal(bundle.records["channel"], np.array([1, 0], dtype=np.int16))
    np.testing.assert_array_equal(
        bundle.wave_pool,
        np.array([5, 6, 7, 8, 9, 10, 11, 12], dtype=np.uint16),
    )
    assert profiler.counts["records.read"] == 2
    assert profiler.counts["records.part_build"] == 2
    assert profiler.counts["records.merge"] == 1


def test_build_records_from_raw_files_handles_single_header_first_segment(tmp_path: Path):
    raw_dir = tmp_path / "RAW"
    raw_dir.mkdir()

    first = raw_dir / "DataR_CH0@VX2730_demo.CSV"
    first.write_text(
        """BOARD;CHANNEL;TIMETAG;ENERGY;ENERGYSHORT;FLAGS;PROBE_CODE;SAMPLES
0;0;1000;0;0;0x4000;1;10;11;12;13
0;0;2000;0;0;0x4000;1;20;21;22;23
""",
        encoding="utf-8",
    )
    second = raw_dir / "DataR_CH0@VX2730_demo_1.CSV"
    second.write_text(
        """0;0;3000;0;0;0x4000;1;30;31;32;33
0;0;4000;0;0;0x4000;1;40;41;42;43
""",
        encoding="utf-8",
    )

    bundle = build_records_from_raw_files(
        [[str(first), str(second)]],
        adapter_name="vx2730",
        default_dt_ns=2,
        part_size=None,
        show_progress=False,
    )

    np.testing.assert_array_equal(
        bundle.records["timestamp"],
        np.array([1000, 2000, 3000, 4000], dtype=np.int64),
    )
    np.testing.assert_array_equal(bundle.records["channel"], np.zeros(4, dtype=np.int16))
    np.testing.assert_array_equal(bundle.records["record_id"], np.arange(4, dtype=np.int64))
    np.testing.assert_array_equal(
        bundle.wave_pool,
        np.array(
            [10, 11, 12, 13, 20, 21, 22, 23, 30, 31, 32, 33, 40, 41, 42, 43],
            dtype=np.uint16,
        ),
    )
