from datetime import datetime, timezone

import numpy as np
import pytest

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin


def test_context_time_range_builds_index_single_array(tmp_path):
    dtype = np.dtype([("time", "<i8"), ("value", "<f8")])

    class TimeDataPlugin(Plugin):
        provides = "time_data"
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            return np.array(
                [(100, 1.0), (200, 2.0), (300, 3.0), (400, 4.0), (500, 5.0)], dtype=dtype
            )

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(TimeDataPlugin)

    result = ctx.time_range("run1", "time_data", start_time=0, end_time=1000)
    assert len(result) == 5

    stats = ctx.get_time_index_stats()
    assert stats["total_indices"] == 1
    assert "run1.time_data" in stats["indices"]
    assert stats["indices"]["run1.time_data"]["n_records"] == 5


def test_context_time_range_builds_index_channel_field(tmp_path):
    dtype = np.dtype([("time", "<i8"), ("board", "<i2"), ("channel", "<i2"), ("value", "<f8")])

    class MultiChannelPlugin(Plugin):
        provides = "multi_channel_data"
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            return np.array(
                [(100, 0, 0, 1.0), (200, 0, 0, 2.0), (150, 0, 1, 1.5), (250, 0, 1, 2.5)],
                dtype=dtype,
            )

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(MultiChannelPlugin)

    result = ctx.time_range("run1", "multi_channel_data", start_time=0, end_time=1000)
    assert len(result) == 4

    stats = ctx.get_time_index_stats()
    assert stats["total_indices"] == 1
    assert stats["indices"]["run1.multi_channel_data"]["n_records"] == 4

    ch1 = ctx.time_range("run1", "multi_channel_data", channel="0:1")
    assert len(ch1) == 2
    assert np.all(ch1["board"] == 0)
    assert np.all(ch1["channel"] == 1)


def test_context_time_range_single(tmp_path):
    dtype = np.dtype([("time", "<i8"), ("value", "<f8")])

    class TimeDataPlugin(Plugin):
        provides = "time_data"
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            return np.array(
                [(100, 1.0), (200, 2.0), (300, 3.0), (400, 4.0), (500, 5.0)], dtype=dtype
            )

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(TimeDataPlugin)

    result = ctx.time_range("run1", "time_data", start_time=200, end_time=400)
    assert len(result) == 2
    assert result[0]["time"] == 200
    assert result[1]["time"] == 300


def test_context_time_range_boundaries(tmp_path):
    dtype = np.dtype([("time", "<i8"), ("value", "<f8")])

    class TimeDataPlugin(Plugin):
        provides = "time_data"
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            return np.array([(100, 1.0), (200, 2.0), (300, 3.0)], dtype=dtype)

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(TimeDataPlugin)

    assert len(ctx.time_range("run1", "time_data", start_time=400, end_time=500)) == 0
    assert len(ctx.time_range("run1", "time_data", start_time=0, end_time=1000)) == 3


def test_context_time_range_system_domain_derives_from_timestamp(tmp_path):
    dtype = np.dtype([("timestamp", "<i8"), ("value", "<f8")])

    class TimestampOnlyPlugin(Plugin):
        provides = "timestamp_only"
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            return np.array([(1000, 1.0), (2000, 2.0), (3000, 3.0)], dtype=dtype)

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(TimestampOnlyPlugin)

    result = ctx.time_range("run1", "timestamp_only", start_time=2, end_time=4)
    assert len(result) == 2
    np.testing.assert_array_equal(result["timestamp"], np.array([2000, 3000], dtype=np.int64))


def test_context_time_range_raw_domain_uses_timestamp_directly(tmp_path):
    dtype = np.dtype([("timestamp", "<i8"), ("value", "<f8")])

    class TimestampOnlyPlugin(Plugin):
        provides = "timestamp_only_raw"
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            return np.array([(1000, 1.0), (2000, 2.0), (3000, 3.0)], dtype=dtype)

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(TimestampOnlyPlugin)

    result = ctx.time_range(
        "run1", "timestamp_only_raw", start_time=1500, end_time=2600, time_domain="raw_ps"
    )
    assert len(result) == 1
    assert int(result[0]["timestamp"]) == 2000


def test_context_time_range_invalid_time_domain(tmp_path):
    dtype = np.dtype([("time", "<i8"), ("value", "<f8")])

    class TimeDataPlugin(Plugin):
        provides = "time_data_bad_domain"
        output_dtype = dtype

        def compute(self, context, run_id, **kwargs):
            return np.array([(1, 1.0)], dtype=dtype)

    ctx = Context(storage_dir=str(tmp_path))
    ctx.register(TimeDataPlugin)

    with pytest.raises(ValueError, match="Unsupported time_domain"):
        ctx.time_range("run1", "time_data_bad_domain", time_domain="ns")


def test_context_set_get_epoch_datetime(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    epoch = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ctx.set_epoch("run1", epoch)

    epoch_info = ctx.get_epoch("run1")
    assert epoch_info is not None
    assert epoch_info.epoch_source == "manual"


def test_context_set_epoch_timestamp(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.set_epoch("run1", 1704110400.0)
    assert ctx.get_epoch("run1") is not None


def test_context_set_epoch_iso_string(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    ctx.set_epoch("run1", "2024-01-01T12:00:00Z")
    assert ctx.get_epoch("run1") is not None


def test_context_get_epoch_not_set(tmp_path):
    ctx = Context(storage_dir=str(tmp_path))
    assert ctx.get_epoch("run1") is None
