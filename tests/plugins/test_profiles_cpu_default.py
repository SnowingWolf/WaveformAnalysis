from waveform_analysis.core.plugins import profiles


def test_cpu_default_includes_hit_plugin():
    plugins = profiles.cpu_default()
    provides = [plugin.provides for plugin in plugins]
    assert "hit" in provides


def test_cpu_default_includes_threshold_hit_plugin():
    plugins = profiles.cpu_default()
    provides = [plugin.provides for plugin in plugins]
    assert "hit_threshold" in provides
