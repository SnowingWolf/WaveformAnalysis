import pytest

from waveform_analysis.core.plugins.builtin.cpu.channel_metadata import resolve_channel_metadata


def test_resolve_channel_metadata_supports_run_scoped_config():
    config = {
        "run_001": {
            "0": {"polarity": "negative", "geometry": "A0", "adc_bits": 14},
        }
    }
    resolved = resolve_channel_metadata(config, "run_001", [0], "unit_test_plugin")

    assert resolved[0]["polarity"] == "negative"
    assert resolved[0]["geometry"] == "A0"
    assert resolved[0]["adc_bits"] == 14


def test_resolve_channel_metadata_warns_once_for_missing_or_invalid_fields():
    config = {
        "0": {"polarity": "bad", "geometry": "", "adc_bits": "invalid"},
    }

    with pytest.warns(UserWarning, match="missing/invalid channel_metadata"):
        resolved = resolve_channel_metadata(config, "run_001", [0, 1], "unit_test_plugin")

    assert resolved[0]["polarity"] == "unknown"
    assert resolved[0]["geometry"] == "unknown"
    assert resolved[0]["adc_bits"] is None
    assert resolved[1]["polarity"] == "unknown"
    assert resolved[1]["geometry"] == "unknown"
    assert resolved[1]["adc_bits"] is None
