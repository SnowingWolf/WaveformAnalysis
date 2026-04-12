"""Execution-path tests for streaming plugins."""

import numpy as np
import pytest

from tests.streaming_helpers import (
    SourceDataPlugin,
    StatefulStreamingPlugin,
    TransformStreamingPlugin,
)
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.streaming import get_streaming_context

pytestmark = pytest.mark.integration


class TestStatefulPlugins:
    def test_stateful_plugin_forces_serial_execution(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SourceDataPlugin)

        plugin = StatefulStreamingPlugin()
        plugin.depends_on = ["source_data"]
        plugin.parallel = True
        plugin.max_workers = 2
        ctx.register(plugin)

        chunks = list(
            get_streaming_context(ctx, run_id="run1", chunk_size=5).get_stream("stateful_stream")
        )

        assert len(chunks) > 1
        assert ctx.get_plugin("stateful_stream").parallel is False

    def test_reset_state_called(self):
        plugin = StatefulStreamingPlugin()
        plugin._counter = 10

        plugin.reset_state()

        assert plugin._counter == 0

    def test_stateful_plugin_preserves_order(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SourceDataPlugin)

        plugin = StatefulStreamingPlugin()
        plugin.depends_on = ["source_data"]
        ctx.register(plugin)

        chunks = list(
            get_streaming_context(ctx, run_id="run1", chunk_size=5).get_stream("stateful_stream")
        )

        leading_values = np.array([chunk.data["value"][0] for chunk in chunks], dtype=np.float64)

        assert np.all(np.diff(leading_values) == 6.0)
        assert np.all(np.diff(leading_values) > 0.0)


class TestParallelProcessing:
    def test_compute_parallel_basic(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SourceDataPlugin)

        plugin = TransformStreamingPlugin()
        plugin.parallel = True
        plugin.max_workers = 2
        ctx.register(plugin)

        chunks = list(
            get_streaming_context(ctx, run_id="run1", chunk_size=5).get_stream("transform_stream")
        )

        assert len(chunks) > 0
        for chunk in chunks:
            assert all(value % 2 == 0 or value == 0 for value in chunk.data["value"])

    def test_parallel_preserves_order(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SourceDataPlugin)

        plugin = TransformStreamingPlugin()
        plugin.parallel = True
        plugin.max_workers = 4
        ctx.register(plugin)

        chunks = list(
            get_streaming_context(ctx, run_id="run1", chunk_size=3).get_stream("transform_stream")
        )

        for index in range(1, len(chunks)):
            assert chunks[index].start >= chunks[index - 1].start
