import numpy as np

from waveform_analysis.core.plugins.builtin.shared.record_utils import RecordLookup


def _records(record_ids):
    dtype = np.dtype([("record_id", "i8")])
    records = np.zeros(len(record_ids), dtype=dtype)
    records["record_id"] = record_ids
    return records


def test_record_lookup_uses_direct_mode_for_identity_ids():
    records = _records(np.arange(2_000_003, dtype=np.int64))

    lookup = RecordLookup(records)

    assert lookup.mode == "direct"
    np.testing.assert_array_equal(
        lookup.get_indices(np.array([0, 1_000_000, 2_000_002], dtype=np.int64)),
        np.array([0, 1_000_000, 2_000_002], dtype=np.int64),
    )


def test_record_lookup_keeps_sorted_mode_for_non_identity_ids():
    records = _records(np.array([10, 20, 30], dtype=np.int64))

    lookup = RecordLookup(records)

    assert lookup.mode == "sorted"
    np.testing.assert_array_equal(
        lookup.get_indices(np.array([30, 10], dtype=np.int64)),
        np.array([2, 0], dtype=np.int64),
    )


def test_record_lookup_checks_identity_chunks_beyond_first_and_last():
    record_ids = np.arange(2_000_003, dtype=np.int64)
    record_ids[1_234_567], record_ids[1_234_568] = (
        record_ids[1_234_568],
        record_ids[1_234_567],
    )

    lookup = RecordLookup(_records(record_ids))

    assert lookup.mode == "sorted"
