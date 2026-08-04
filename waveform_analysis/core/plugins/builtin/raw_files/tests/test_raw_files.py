"""Tests for RawFileNamesPlugin (raw_files bundle)."""

import pytest

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.raw_files import (
    RawFileNamesPlugin as ShimPlugin,
)
from waveform_analysis.core.plugins.builtin.raw_files import (
    RawFileNamesPlugin,
)


def test_old_path_is_new_bundle():
    """旧 shim 路径与新 bundle 路径指向同一 RawFileNamesPlugin 类对象。"""
    from waveform_analysis.core.plugins.builtin.cpu.waveforms import (
        RawFileNamesPlugin as FromWaveforms,
    )

    assert ShimPlugin is RawFileNamesPlugin
    assert FromWaveforms is RawFileNamesPlugin


def test_plugin_metadata():
    plugin = RawFileNamesPlugin()
    assert plugin.provides == "raw_files"
    assert plugin.version == "0.0.2"
    assert plugin.output_schema.kind == "list"


def test_compute_groups_files_by_channel(monkeypatch):
    """compute 应委托 get_raw_files 并按配置传参。"""
    captured = {}

    def fake_get_raw_files(**kwargs):
        captured.update(kwargs)
        return [["a.csv", "b.csv"], ["c.csv"]]

    import waveform_analysis.core.processing.loader as loader

    monkeypatch.setattr(loader, "get_raw_files", fake_get_raw_files)

    plugin = RawFileNamesPlugin()
    ctx = DummyContext({"data_root": "/tmp/data", "daq_adapter": "vx2730"})
    out = plugin.compute(ctx, "run_001")

    assert out == [["a.csv", "b.csv"], ["c.csv"]]
    assert captured["run_name"] == "run_001"
    assert captured["data_root"] == "/tmp/data"
    assert captured["daq_adapter"] == "vx2730"
    assert captured["daq_run"] is None


def test_compute_resolves_default_config(monkeypatch):
    captured = {}

    def fake_get_raw_files(**kwargs):
        captured.update(kwargs)
        return []

    import waveform_analysis.core.processing.loader as loader

    monkeypatch.setattr(loader, "get_raw_files", fake_get_raw_files)

    plugin = RawFileNamesPlugin()
    ctx = DummyContext({})
    plugin.compute(ctx, "run_002")

    assert captured["data_root"] == "DAQ"
    assert captured["daq_adapter"] == "vx2730"
