"""VX2730 and generic CSV reader tests."""

import numpy as np

from waveform_analysis.utils.formats import (
    ColumnMapping,
    FormatSpec,
    GenericCSVReader,
    VX2730Reader,
)


class TestVX2730Reader:
    def test_reader_init(self):
        assert VX2730Reader().spec.name == "vx2730_csv"

    def test_read_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.CSV"
        empty_file.touch()

        data = VX2730Reader().read_file(empty_file)
        assert data.size == 0

    def test_read_nonexistent_file(self, tmp_path):
        data = VX2730Reader().read_file(tmp_path / "nonexistent.CSV")
        assert data.size == 0

    def test_read_simple_csv(self, tmp_path):
        csv_file = tmp_path / "CH0_0.CSV"
        csv_file.write_text(
            """HEADER LINE 1
HEADER LINE 2
0;0;1000;0;0;0;0;100;200;300;400
0;0;2000;0;0;0;0;110;210;310;410
""",
            encoding="utf-8",
        )

        data = VX2730Reader().read_file(csv_file, is_first_file=True)

        assert data.shape[0] == 2
        assert data[0, 2] == 1000
        assert data[1, 2] == 2000

    def test_read_file_auto_detects_single_header_row(self, tmp_path):
        csv_file = tmp_path / "CH0_0.CSV"
        csv_file.write_text(
            """BOARD;CHANNEL;TIMETAG;ENERGY;ENERGYSHORT;FLAGS;PROBE_CODE;SAMPLES
0;0;1000;0;0;0;1;100;200;300;400
0;0;2000;0;0;0;1;110;210;310;410
""",
            encoding="utf-8",
        )

        data = VX2730Reader().read_file(csv_file, is_first_file=True)

        assert data.shape[0] == 2
        assert int(data[0, 2]) == 1000
        assert int(data[1, 2]) == 2000

    def test_count_total_rows_auto_detects_single_header_first_segment(self, tmp_path):
        first = tmp_path / "CH0_0.CSV"
        first.write_text(
            """BOARD;CHANNEL;TIMETAG;ENERGY;ENERGYSHORT;FLAGS;PROBE_CODE;SAMPLES
0;0;1000;0;0;0;1;100;200
0;0;2000;0;0;0;1;110;210
""",
            encoding="utf-8",
        )
        second = tmp_path / "CH0_1.CSV"
        second.write_text(
            """0;0;3000;0;0;0;1;120;220
0;0;4000;0;0;0;1;130;230
""",
            encoding="utf-8",
        )

        reader = VX2730Reader()
        total_rows = reader.count_total_rows([first, second])
        data = reader.read_files([first, second])

        assert total_rows == 4
        assert data.shape[0] == total_rows

    def test_read_files_streaming_auto_detects_single_header_row(self, tmp_path):
        first = tmp_path / "CH0_0.CSV"
        first.write_text(
            """BOARD;CHANNEL;TIMETAG;ENERGY;ENERGYSHORT;FLAGS;PROBE_CODE;SAMPLES
0;0;1000;0;0;0;1;100;200
0;0;2000;0;0;0;1;110;210
""",
            encoding="utf-8",
        )
        second = tmp_path / "CH0_1.CSV"
        second.write_text(
            """0;0;3000;0;0;0;1;120;220
0;0;4000;0;0;0;1;130;230
""",
            encoding="utf-8",
        )

        output_dtype = np.dtype([("timestamp", "i8"), ("wave", "i2", (2,))])
        output_path = tmp_path / "out.dat"

        def structurizer(raw, output, offset):
            n = len(raw)
            output[offset : offset + n]["timestamp"] = raw[:, 2].astype(np.int64)
            output[offset : offset + n]["wave"] = raw[:, 7:9].astype(np.int16)
            return n

        result = VX2730Reader().read_files_streaming(
            [first, second],
            output_dtype=output_dtype,
            output_path=output_path,
            structurizer=structurizer,
            show_progress=False,
        )

        assert len(result) == 4
        np.testing.assert_array_equal(
            result["timestamp"],
            np.array([1000, 2000, 3000, 4000], dtype=np.int64),
        )


class TestGenericCSVReaderStreaming:
    def test_generic_reader_supports_streaming_fallback(self, tmp_path):
        spec = FormatSpec(
            name="generic_test",
            columns=ColumnMapping(timestamp=2, samples_start=3, samples_end=None),
            delimiter=";",
            header_rows_first_file=1,
            header_rows_other_files=0,
        )
        reader = GenericCSVReader(spec)

        first = tmp_path / "g0.csv"
        first.write_text(
            """A;B;TIMETAG;S0;S1
0;0;100;11;12
0;0;200;21;22
""",
            encoding="utf-8",
        )
        second = tmp_path / "g1.csv"
        second.write_text(
            """0;0;300;31;32
0;0;400;41;42
""",
            encoding="utf-8",
        )

        output_dtype = np.dtype([("timestamp", "i8"), ("wave", "i2", (2,))])
        output_path = tmp_path / "generic.dat"

        def structurizer(raw, output, offset):
            n = len(raw)
            output[offset : offset + n]["timestamp"] = raw[:, 2].astype(np.int64)
            output[offset : offset + n]["wave"] = raw[:, 3:5].astype(np.int16)
            return n

        result = reader.read_files_streaming(
            [first, second],
            output_dtype=output_dtype,
            output_path=output_path,
            structurizer=structurizer,
            show_progress=False,
        )

        assert len(result) == 4
        np.testing.assert_array_equal(
            result["timestamp"],
            np.array([100, 200, 300, 400], dtype=np.int64),
        )

    def test_extract_columns(self, tmp_path):
        csv_file = tmp_path / "CH0_0.CSV"
        csv_file.write_text(
            """H1
H2
0;1;1000;0;0;0;0;100;200;300;400;500;600;700;800;900;1000;1100;1200;1300;1400;1500;1600;1700;1800;1900;2000;2100;2200;2300;2400;2500;2600;2700;2800;2900;3000;3100;3200;3300;3400;3500;3600;3700;3800;3900;4000
""",
            encoding="utf-8",
        )

        data = VX2730Reader().read_file(csv_file)
        extracted = VX2730Reader().extract_columns(data)

        assert extracted["board"][0] == 0
        assert extracted["channel"][0] == 1
        assert extracted["timestamp"][0] == 1000
        assert extracted["samples"].shape[1] > 0
