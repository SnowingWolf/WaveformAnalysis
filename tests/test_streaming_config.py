"""Streaming configuration tests."""

import warnings

import pytest

from tests.streaming_helpers import SimpleStreamingPlugin
from waveform_analysis.core.context import Context

pytestmark = pytest.mark.integration


class TestStreamingConfig:
    def test_collect_streaming_config_defaults(self):
        plugin = SimpleStreamingPlugin()
        config = plugin._collect_streaming_config(None, None)

        assert "chunk_size" in config
        assert config["chunk_size"] == plugin.chunk_size

    def test_collect_streaming_config_override(self):
        config = SimpleStreamingPlugin()._collect_streaming_config(
            None,
            {"chunk_size": 100, "parallel": True},
        )

        assert config["chunk_size"] == 100
        assert config["parallel"] is True

    def test_legacy_config_warning(self, tmp_path):
        plugin = SimpleStreamingPlugin()
        ctx = Context(storage_dir=str(tmp_path), config={"chunk_size": 50})

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            plugin._collect_streaming_config(ctx, None)

        assert any(issubclass(warning.category, DeprecationWarning) for warning in caught)

    def test_unknown_config_warning(self):
        plugin = SimpleStreamingPlugin()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            plugin._filter_streaming_config({"unknown_key": "value"})

        assert any(issubclass(warning.category, UserWarning) for warning in caught)

    def test_apply_streaming_config(self):
        plugin = SimpleStreamingPlugin()
        original_chunk_size = plugin.chunk_size

        plugin._apply_streaming_config({"chunk_size": 999, "parallel": True})

        assert plugin.chunk_size == 999
        assert plugin.parallel is True

        plugin.chunk_size = original_chunk_size
