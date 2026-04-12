"""Dependency resolution tests for BasicFeaturesPlugin."""

from tests.utils import FakeContext
from waveform_analysis.core.plugins.builtin.cpu.basic_features import BasicFeaturesPlugin


class TestResolveDependsOn:
    def test_default_depends_on_st_waveforms(self):
        assert BasicFeaturesPlugin().resolve_depends_on(FakeContext(config={})) == ["st_waveforms"]

    def test_use_filtered_depends_on_filtered(self):
        ctx = FakeContext(config={"use_filtered": True})
        assert BasicFeaturesPlugin().resolve_depends_on(ctx) == ["filtered_waveforms"]

    def test_use_filtered_false_explicit(self):
        ctx = FakeContext(config={"use_filtered": False})
        assert BasicFeaturesPlugin().resolve_depends_on(ctx) == ["st_waveforms"]

    def test_wave_source_records_depends_on_records_and_wave_pool(self):
        ctx = FakeContext(config={"wave_source": "records", "use_filtered": False})
        assert BasicFeaturesPlugin().resolve_depends_on(ctx) == ["records", "wave_pool"]

    def test_wave_source_records_and_use_filtered_depends_on_filtered_pool(self):
        ctx = FakeContext(config={"wave_source": "records", "use_filtered": True})
        assert BasicFeaturesPlugin().resolve_depends_on(ctx) == ["records", "wave_pool_filtered"]

    def test_wave_source_filtered_depends_on_filtered(self):
        ctx = FakeContext(config={"wave_source": "filtered_waveforms"})
        assert BasicFeaturesPlugin().resolve_depends_on(ctx) == ["filtered_waveforms"]

    def test_wave_source_st_depends_on_st(self):
        ctx = FakeContext(config={"wave_source": "st_waveforms", "use_filtered": True})
        assert BasicFeaturesPlugin().resolve_depends_on(ctx) == ["st_waveforms"]
