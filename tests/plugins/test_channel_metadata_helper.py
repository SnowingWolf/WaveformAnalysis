import pytest

from waveform_analysis.core.hardware.channel import (
    ChannelMetadata,
    HardwareChannel,
    get_channel_metadata_config,
    resolve_channel_metadata_map,
    resolve_effective_channel_metadata,
)
from waveform_analysis.core.plugins.builtin.cpu.channel_metadata import (
    resolve_channel_metadata,
    resolve_context_channel_metadata,
)


class _RunConfigContext:
    def __init__(self, config, run_configs):
        self.config = config
        self._run_configs = run_configs

    def get_run_config(self, run_id: str):
        return self._run_configs.get(run_id, {})


def test_resolve_effective_channel_metadata_merges_defaults_groups_and_channels():
    metadata = {
        "defaults": {"adc_bits": 14},
        "groups": [
            {
                "name": "board0_negative",
                "channels": ["0:0", "0:1"],
                "metadata": {"polarity": "negative", "geometry": "bottom"},
            }
        ],
        "channels": {
            "0:1": {"geometry": "special_probe"},
        },
    }

    resolved = resolve_effective_channel_metadata(metadata, board=0, channel=1)

    assert resolved == ChannelMetadata(
        polarity="negative",
        geometry="special_probe",
        adc_bits=14,
    )


def test_resolve_channel_metadata_map_supports_unknown_defaults_for_missing_channels():
    resolved = resolve_channel_metadata_map(
        channel_metadata={
            "channels": {
                "0:0": {"polarity": "negative"},
            }
        },
        channels=[HardwareChannel(0, 0), HardwareChannel(0, 2)],
    )

    assert resolved[HardwareChannel(0, 0)].polarity == "negative"
    assert resolved[HardwareChannel(0, 2)] == ChannelMetadata()


def test_get_channel_metadata_config_merges_context_and_run_scoped_layers():
    ctx = _RunConfigContext(
        config={
            "channel_metadata": {
                "defaults": {"adc_bits": 14},
                "groups": [
                    {
                        "name": "board0_negative",
                        "channels": ["0:0", "0:1"],
                        "metadata": {"polarity": "negative"},
                    }
                ],
                "channels": {
                    "0:1": {"geometry": "context-geom"},
                },
            }
        },
        run_configs={
            "run_001": {
                "channel_metadata": {
                    "groups": [
                        {
                            "name": "board0_top",
                            "channels": ["0:1"],
                            "metadata": {"geometry": "run-geom"},
                        }
                    ],
                    "channels": {
                        "0:1": {"adc_bits": 16},
                    },
                }
            }
        },
    )

    merged = get_channel_metadata_config(ctx, "run_001")
    resolved = resolve_effective_channel_metadata(merged, board=0, channel=1)

    assert resolved == ChannelMetadata(
        polarity="negative",
        geometry="run-geom",
        adc_bits=16,
    )


def test_resolve_channel_metadata_wrapper_exposes_legacy_dict_shape():
    config = {
        "defaults": {"adc_bits": 14},
        "channels": {
            "0:0": {"polarity": "negative", "geometry": "A0"},
        },
    }
    resolved = resolve_channel_metadata(config, "run_001", [(0, 0)], "unit_test_plugin")

    key = HardwareChannel(0, 0)
    assert resolved[key]["polarity"] == "negative"
    assert resolved[key]["geometry"] == "A0"
    assert resolved[key]["adc_bits"] == 14


def test_resolve_context_channel_metadata_reads_top_level_channel_metadata():
    ctx = _RunConfigContext(
        config={
            "channel_metadata": {
                "defaults": {"adc_bits": 14},
            }
        },
        run_configs={
            "run_001": {
                "channel_metadata": {
                    "channels": {
                        "1:2": {"polarity": "positive"},
                    }
                }
            }
        },
    )

    resolved = resolve_context_channel_metadata(ctx, "run_001", [(1, 2)])

    assert resolved[HardwareChannel(1, 2)] == {
        "polarity": "positive",
        "geometry": "unknown",
        "adc_bits": 14,
    }


def test_resolve_channel_metadata_rejects_boardless_keys():
    with pytest.raises(ValueError, match="Invalid channel key"):
        resolve_effective_channel_metadata(
            {
                "channels": {
                    "1": {"polarity": "negative"},
                }
            },
            board=0,
            channel=1,
        )
