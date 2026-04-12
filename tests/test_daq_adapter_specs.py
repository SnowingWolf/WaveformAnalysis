"""Format spec and registry tests for DAQ adapters."""

from pathlib import Path
import uuid

import numpy as np
import pytest

from waveform_analysis.utils.formats import (
    FLAT_LAYOUT,
    VX2730_ADAPTER,
    VX2730_LAYOUT,
    VX2730_SPEC,
    ColumnMapping,
    FormatSpec,
    GenericCSVReader,
    RawTimestampMode,
    TimestampUnit,
    VX2730Reader,
    get_adapter,
    get_format_reader,
    list_adapters,
    list_formats,
    register_format,
    unregister_format,
)


class TestFormatSpec:
    def test_vx2730_spec(self):
        spec = VX2730_SPEC
        assert spec.name == "vx2730_csv"
        assert spec.delimiter == ";"
        assert spec.timestamp_unit == TimestampUnit.PICOSECONDS
        assert spec.raw_timestamp_mode == RawTimestampMode.UNIT
        assert spec.header_rows_first_file == 2
        assert spec.header_rows_other_files == 0
        assert spec.sampling_rate_hz == 500e6

    def test_timestamp_scale(self):
        assert (
            FormatSpec(name="test", timestamp_unit=TimestampUnit.PICOSECONDS).get_timestamp_scale()
            == 0.001
        )
        assert (
            FormatSpec(name="test", timestamp_unit=TimestampUnit.NANOSECONDS).get_timestamp_scale()
            == 1.0
        )
        assert (
            FormatSpec(name="test", timestamp_unit=TimestampUnit.MICROSECONDS).get_timestamp_scale()
            == 1e3
        )

    def test_normalize_timestamp_to_ps_for_physical_units(self):
        spec = FormatSpec(name="test", timestamp_unit=TimestampUnit.NANOSECONDS)
        timestamps = np.array([10, 20], dtype=np.int64)

        np.testing.assert_array_equal(
            spec.normalize_timestamp_to_ps(timestamps),
            np.array([10_000, 20_000], dtype=np.int64),
        )

    def test_normalize_timestamp_to_ps_for_sample_index(self):
        spec = FormatSpec(
            name="test",
            timestamp_unit=TimestampUnit.NANOSECONDS,
            raw_timestamp_mode=RawTimestampMode.SAMPLE_INDEX,
            sampling_rate_hz=250e6,
        )
        timestamps = np.array([10, 20], dtype=np.int64)

        np.testing.assert_array_equal(
            spec.normalize_timestamp_to_ps(timestamps),
            np.array([40_000, 80_000], dtype=np.int64),
        )
        np.testing.assert_array_equal(
            spec.normalize_timestamp_to_ps(timestamps, dt_ns=8),
            np.array([80_000, 160_000], dtype=np.int64),
        )

    def test_column_mapping(self):
        cols = ColumnMapping()
        assert cols.board == 0
        assert cols.channel == 1
        assert cols.timestamp == 2
        assert cols.samples_start == 7
        assert cols.samples_end is None
        assert cols.baseline_start == 7
        assert cols.baseline_end == 47


class TestDirectoryLayout:
    def test_vx2730_layout(self):
        layout = VX2730_LAYOUT
        assert layout.name == "vx2730"
        assert layout.raw_subdir == "RAW"
        assert layout.file_glob_pattern == "*CH*.CSV"

    def test_get_raw_path(self):
        assert VX2730_LAYOUT.get_raw_path("DAQ", "run_001") == Path("DAQ/run_001/RAW")

    def test_flat_layout(self):
        layout = FLAT_LAYOUT
        assert layout.name == "flat"
        assert layout.raw_subdir == ""
        assert layout.get_raw_path("DAQ", "run_001") == Path("DAQ/run_001")

    def test_extract_channel(self):
        assert VX2730_LAYOUT.extract_channel("CH0_0.CSV") == 0
        assert VX2730_LAYOUT.extract_channel("CH5_10.CSV") == 5
        assert VX2730_LAYOUT.extract_channel("data_0.csv") is None

    def test_extract_file_index(self):
        assert VX2730_LAYOUT.extract_file_index("CH0_0.CSV") == 0
        assert VX2730_LAYOUT.extract_file_index("CH0_10.CSV") == 10
        assert VX2730_LAYOUT.extract_file_index("CH0.CSV") == 0


class TestAdapterLookup:
    def test_vx2730_adapter(self):
        adapter = VX2730_ADAPTER
        assert adapter.name == "vx2730"
        assert adapter.format_spec == VX2730_SPEC
        assert adapter.directory_layout == VX2730_LAYOUT
        assert adapter.sampling_rate_hz == 500e6

    def test_get_adapter(self):
        assert get_adapter("vx2730").name == "vx2730"

    def test_get_unknown_adapter(self):
        with pytest.raises(ValueError, match="未知适配器"):
            get_adapter("unknown_adapter")

    def test_list_adapters(self):
        assert "vx2730" in list_adapters()


class TestRegistry:
    def test_list_formats(self):
        assert "vx2730_csv" in list_formats()

    def test_get_format_reader(self):
        assert isinstance(get_format_reader("vx2730_csv"), VX2730Reader)

    def test_register_custom_format(self):
        custom_name = f"custom_test_{uuid.uuid4().hex}"
        custom_spec = FormatSpec(
            name=custom_name,
            delimiter=",",
            timestamp_unit=TimestampUnit.NANOSECONDS,
        )

        register_format(custom_name, GenericCSVReader, custom_spec)
        try:
            assert custom_name in list_formats()
            reader = get_format_reader(custom_name)
            assert isinstance(reader, GenericCSVReader)
            assert reader.spec.name == custom_name
        finally:
            unregister_format(custom_name)
