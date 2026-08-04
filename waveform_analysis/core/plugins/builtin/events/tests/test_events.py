"""Tests for EventPlugin (events bundle)."""

from waveform_analysis.core.plugins.builtin.cpu.event import EventPlugin as ShimPlugin
from waveform_analysis.core.plugins.builtin.events import EVENT_DTYPE, EventPlugin


def test_old_path_is_new_bundle():
    assert ShimPlugin is EventPlugin


def test_plugin_metadata():
    plugin = EventPlugin()
    assert plugin.provides == "events"
    assert plugin.version == "0.0.3"
    assert plugin.output_dtype is EVENT_DTYPE
    assert "event_id" in EVENT_DTYPE.names
