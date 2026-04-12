"""StreamingContext tests."""

import pytest

from tests.streaming_helpers import SourceDataPlugin, TransformStreamingPlugin, make_simple_data
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.streaming import StreamingContext, get_streaming_context
from waveform_analysis.core.processing.chunk import Chunk

pytestmark = pytest.mark.integration


class TestStreamingContext:
    def test_get_stream_streaming_plugin(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SourceDataPlugin)
        ctx.register(TransformStreamingPlugin)

        chunks = list(
            get_streaming_context(ctx, run_id="run1", chunk_size=5).get_stream("transform_stream")
        )

        assert len(chunks) > 0
        assert all(isinstance(chunk, Chunk) for chunk in chunks)

    def test_get_stream_static_plugin(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SourceDataPlugin)

        chunks = list(
            get_streaming_context(ctx, run_id="run1", chunk_size=5).get_stream("source_data")
        )

        assert len(chunks) > 0
        assert sum(len(chunk.data) for chunk in chunks) > 0
        for chunk in chunks:
            assert "timestamp" in chunk.data.dtype.names
            assert "value" in chunk.data.dtype.names

    def test_get_stream_with_time_range(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SourceDataPlugin)

        chunks = list(
            get_streaming_context(ctx, run_id="run1", chunk_size=10).get_stream(
                "source_data",
                time_range=(500, 1500),
            )
        )

        for chunk in chunks:
            assert chunk.start < 1500
            assert chunk.end > 500

    def test_get_stream_plugin_not_found(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))

        with pytest.raises(ValueError, match="No plugin registered"):
            list(get_streaming_context(ctx, run_id="run1").get_stream("nonexistent"))

    def test_clip_chunk_to_time_range(self, tmp_path):
        chunk = Chunk(
            data=make_simple_data(10, start_time=0, step=100),
            start=0,
            end=1000,
            run_id="run1",
            data_type="test",
            time_field="timestamp",
        )

        clipped = StreamingContext(Context(storage_dir=str(tmp_path)), run_id="run1")._clip_chunk(
            chunk,
            200,
            700,
        )

        assert clipped.start >= 200
        assert clipped.end <= 700

    def test_iter_chunks(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SourceDataPlugin)

        chunks = list(
            get_streaming_context(ctx, run_id="run1", chunk_size=5).iter_chunks("source_data")
        )

        assert len(chunks) > 0

    def test_merge_stream(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SourceDataPlugin)
        stream_ctx = get_streaming_context(ctx, run_id="run1", chunk_size=10)

        stream1 = stream_ctx.get_stream("source_data", time_range=(0, 500))
        stream2 = stream_ctx.get_stream("source_data", time_range=(1000, 1500))
        merged = list(stream_ctx.merge_stream([stream1, stream2], sort=True))

        assert len(merged) == 1
