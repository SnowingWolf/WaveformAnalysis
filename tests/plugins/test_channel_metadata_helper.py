import pytest

from waveform_analysis.core.hardware.channel import HardwareChannel
from waveform_analysis.core.plugins.builtin.cpu.channel_metadata import resolve_channel_metadata


def test_resolve_channel_metadata_supports_run_scoped_config():
    config = {
        "run_001": {
            "0:0": {"polarity": "negative", "geometry": "A0", "adc_bits": 14},
        }
    }
    resolved = resolve_channel_metadata(config, "run_001", [(0, 0)], "unit_test_plugin")

    key = HardwareChannel(0, 0)
    assert resolved[key]["polarity"] == "negative"
    assert resolved[key]["geometry"] == "A0"
    assert resolved[key]["adc_bits"] == 14


def test_resolve_channel_metadata_warns_once_for_missing_or_invalid_fields():
    config = {
        "0:0": {"polarity": "bad", "geometry": "", "adc_bits": "invalid"},
    }

    with pytest.warns(UserWarning, match="missing/invalid channel_metadata"):
        resolved = resolve_channel_metadata(config, "run_001", [(0, 0), (0, 1)], "unit_test_plugin")

    key0 = HardwareChannel(0, 0)
    key1 = HardwareChannel(0, 1)
    assert resolved[key0]["polarity"] == "unknown"
    assert resolved[key0]["geometry"] == "unknown"
    assert resolved[key0]["adc_bits"] is None
    assert resolved[key1]["polarity"] == "unknown"
    assert resolved[key1]["geometry"] == "unknown"
    assert resolved[key1]["adc_bits"] is None


def test_resolve_channel_metadata_rejects_boardless_channel_selectors():
    with pytest.raises(ValueError, match="Invalid hardware channel selector"):
        resolve_channel_metadata({}, "run_001", [0], "unit_test_plugin")
