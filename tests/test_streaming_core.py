"""Core StreamingPlugin behavior tests."""

import numpy as np
import pytest

from tests.streaming_helpers import (
    RECORD_DTYPE,
    SimpleStreamingPlugin,
    make_simple_data,
    make_test_records,
)
from waveform_analysis.core.processing.chunk import Chunk

pytestmark = pytest.mark.integration


class TestStreamingPluginCore:
    def test_postprocess_result_wrap_non_chunk(self):
        plugin = SimpleStreamingPlugin()
        input_chunk = Chunk(
            data=make_simple_data(5),
            start=0,
            end=500,
            run_id="run1",
            data_type="input",
            time_field="timestamp",
            metadata={"main_start": 0, "main_end": 500},
        )

        result = plugin._postprocess_result(make_simple_data(3), input_chunk)

        assert isinstance(result, Chunk)
        assert result.data_type == plugin.provides

    def test_postprocess_result_none_input(self):
        plugin = SimpleStreamingPlugin()
        input_chunk = Chunk(
            data=make_simple_data(5),
            start=0,
            end=500,
            run_id="run1",
            data_type="input",
            time_field="timestamp",
        )

        assert plugin._postprocess_result(None, input_chunk) is None

    def test_postprocess_result_clip_to_range(self):
        plugin = SimpleStreamingPlugin()
        plugin.output_time_field = "timestamp"
        input_chunk = Chunk(
            data=make_simple_data(6, start_time=0, step=100),
            start=0,
            end=600,
            run_id="run1",
            data_type="input",
            time_field="timestamp",
            metadata={"main_start": 100, "main_end": 400},
        )
        result_chunk = Chunk(
            data=make_simple_data(6, start_time=0, step=100),
            start=0,
            end=600,
            run_id="run1",
            data_type=plugin.provides,
            time_field="timestamp",
        )

        result = plugin._postprocess_result(result_chunk, input_chunk)

        assert result is not None
        assert len(result.data) >= 2
        assert all(100 <= t < 400 for t in result.data["timestamp"])

    def test_validate_chunk_valid(self):
        chunk = Chunk(
            data=make_test_records(5, start_time=0, dt=10, length=100),
            start=0,
            end=5000,
            run_id="run1",
            data_type="test",
            time_field="time",
        )

        SimpleStreamingPlugin()._validate_chunk(chunk)

    def test_validate_chunk_empty(self):
        chunk = Chunk(
            data=np.array([], dtype=RECORD_DTYPE),
            start=0,
            end=100,
            run_id="run1",
            data_type="test",
            time_field="time",
        )

        SimpleStreamingPlugin()._validate_chunk(chunk)

    def test_validate_chunk_boundary_violation(self):
        data = make_test_records(5, start_time=0, dt=10, length=100)
        chunk = Chunk(
            data=data,
            start=0,
            end=5000,
            run_id="run1",
            data_type="test",
            time_field="time",
        )
        chunk.end = 100

        with pytest.raises(ValueError, match="boundary violation"):
            SimpleStreamingPlugin()._validate_chunk(chunk)


class TestStreamingPluginDataConversion:
    def test_data_to_chunks_numpy_array(self):
        plugin = SimpleStreamingPlugin()
        plugin.chunk_size = 5
        plugin.time_field = "timestamp"

        chunks = list(plugin._data_to_chunks(make_simple_data(12, start_time=0, step=100), "run1"))

        assert len(chunks) == 3
        assert all(isinstance(chunk, Chunk) for chunk in chunks)

    def test_data_to_chunks_preserves_time_field(self):
        plugin = SimpleStreamingPlugin()
        plugin.chunk_size = 5
        plugin.time_field = "timestamp"

        chunks = list(
            plugin._data_to_chunks(make_simple_data(10, start_time=1000, step=100), "run1")
        )

        assert chunks[0].start == 1000

    def test_data_to_chunks_list(self):
        plugin = SimpleStreamingPlugin()
        plugin.chunk_size = 10
        plugin.time_field = "timestamp"

        chunks = list(
            plugin._data_to_chunks(
                [
                    make_simple_data(5, start_time=0, step=100),
                    make_simple_data(5, start_time=1000, step=100),
                ],
                "run1",
            )
        )

        assert len(chunks) == 2

    def test_data_to_chunks_with_metadata(self):
        plugin = SimpleStreamingPlugin()
        plugin.chunk_size = 5
        plugin.time_field = "timestamp"

        for chunk in plugin._data_to_chunks(make_simple_data(10, start_time=0, step=100), "run1"):
            assert "main_start" in chunk.metadata
            assert "main_end" in chunk.metadata
            assert "segment_id" in chunk.metadata


class TestHaloConfig:
    def test_get_required_halo_symmetric(self):
        plugin = SimpleStreamingPlugin()
        plugin.required_halo_ns = 100

        assert plugin._get_required_halo() == (100, 100)

    def test_get_required_halo_asymmetric(self):
        plugin = SimpleStreamingPlugin()
        plugin.required_halo_left_ns = 50
        plugin.required_halo_right_ns = 150

        assert plugin._get_required_halo() == (50, 150)

    def test_get_required_halo_combined(self):
        plugin = SimpleStreamingPlugin()
        plugin.required_halo_ns = 100
        plugin.required_halo_left_ns = 50
        plugin.required_halo_right_ns = 200

        assert plugin._get_required_halo() == (100, 200)
