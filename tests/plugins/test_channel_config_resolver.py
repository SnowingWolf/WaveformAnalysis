import pytest

from tests.utils import DummyContext, MockPlugin
from waveform_analysis.core.hardware.channel import (
    HardwareChannel,
    resolve_channel_configs,
    resolve_effective_channel_config,
    resolve_effective_channel_option,
)


def test_resolve_effective_channel_config_merges_default_group_channel_layers():
    plugin = MockPlugin()
    plugin.provides = "mock_data"
    ctx = DummyContext({}, {})

    rule = resolve_effective_channel_config(
        context=ctx,
        plugin=plugin,
        run_id="run_001",
        board=0,
        channel=2,
        base_values={"threshold": 8.0},
        channel_config={
            "run_001": {
                "defaults": {"threshold": 10.0, "polarity": "negative"},
                "groups": {
                    "pos": {
                        "channels": ["0:1", "0:2"],
                        "config": {"polarity": "positive", "threshold": 18.0},
                    }
                },
                "channels": {
                    "0:2": {"threshold": 20.0},
                },
            }
        },
    )

    assert rule.channel == HardwareChannel(0, 2)
    assert rule.values["polarity"] == "positive"
    assert rule.values["threshold"] == 20.0


def test_resolve_effective_channel_option_supports_explicit_channel_config_override():
    plugin = MockPlugin()
    plugin.provides = "mock_data"
    ctx = DummyContext({}, {})

    value = resolve_effective_channel_option(
        context=ctx,
        plugin=plugin,
        run_id="run_001",
        board=1,
        channel=3,
        option_name="threshold",
        default=9.0,
        base_values={"threshold": 11.0},
        channel_config={
            "run_001": {
                "channels": {
                    "1:3": {"threshold": 15.0},
                }
            }
        },
    )

    assert value == pytest.approx(15.0)


def test_resolve_channel_configs_rejects_boardless_keys():
    with pytest.raises(ValueError, match="Invalid channel key"):
        resolve_channel_configs(
            channel_config={"run_001": {"1": {"polarity": "negative"}}},
            run_id="run_001",
            channels=[HardwareChannel(0, 1)],
            plugin_name="unit_test_plugin",
        )
