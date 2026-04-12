"""Integration tests for DAQ adapters."""

from waveform_analysis.utils.formats import get_adapter


class TestIntegration:
    def test_full_workflow(self, tmp_path):
        raw_dir = tmp_path / "run_001" / "RAW"
        raw_dir.mkdir(parents=True)

        for ch in range(2):
            for idx in range(2):
                csv_file = raw_dir / f"CH{ch}_{idx}.CSV"
                if idx == 0:
                    content = f"""HEADER 1
HEADER 2
0;{ch};{1000 + idx * 100};0;0;0;0;100;200;300
"""
                else:
                    content = f"""0;{ch};{1000 + idx * 100};0;0;0;0;100;200;300
"""
                csv_file.write_text(content, encoding="utf-8")

        adapter = get_adapter("vx2730")

        channel_files = adapter.scan_run(str(tmp_path), "run_001")
        assert len(channel_files) == 2
        assert 0 in channel_files
        assert 1 in channel_files
        assert len(channel_files[0]) == 2
        assert len(channel_files[1]) == 2

        data = adapter.load_channel(str(tmp_path), "run_001", channel=0)
        assert data.shape[0] == 2

        extracted = adapter.extract_and_convert(data)
        assert "timestamp" in extracted
        assert "channel" in extracted
        assert extracted["channel"][0] == 0
        assert extracted["timestamp"][0] == 1000

        extracted_ns = adapter.extract_and_convert_ns(data)
        assert extracted_ns["timestamp"][0] == 1
