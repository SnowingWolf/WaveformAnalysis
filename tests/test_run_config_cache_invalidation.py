import json
from pathlib import Path

import numpy as np
import pytest

from waveform_analysis.core.config import RunConfigValidationError, validate_run_config
from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Plugin


class _ConstPlugin(Plugin):
    provides = "const"
    depends_on = []
    output_dtype = np.dtype([("value", "i4")])

    def compute(self, context, run_id, **kwargs):
        return np.array([(1,)], dtype=self.output_dtype)


class _DFPlugin(_ConstPlugin):
    provides = "df"
    uses_run_config = True


class _RunConfigDrivenPlugin(_ConstPlugin):
    provides = "run_cfg_root"
    uses_run_config = True


class _DFEventsPlugin(_ConstPlugin):
    provides = "df_events"
    depends_on = ["df"]


class _DFPairedPlugin(_ConstPlugin):
    provides = "df_paired"
    depends_on = ["df_events"]


def _register_test_plugins(ctx: Context):
    ctx.register(
        _DFPlugin(),
        _RunConfigDrivenPlugin(),
        _DFEventsPlugin(),
        _DFPairedPlugin(),
    )


def _write_run_config(path: Path, gain_value: float):
    payload = {
        "meta": {"version": "1"},
        "calibration": {"gain_adc_per_pe": {"0": gain_value}},
        "plugins": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_payload(path: Path, payload: dict):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_get_run_config_loads_json_from_default_sibling_path(tmp_path):
    run_id = "run_001"
    data_root = tmp_path / "DAQ"
    data_root.mkdir(parents=True)
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    config_path = run_dir / "run_config.json"
    _write_run_config(config_path, gain_value=12.5)

    ctx = Context(config={"data_root": str(data_root)})
    loaded = ctx.get_run_config(run_id)

    assert loaded["calibration"]["gain_adc_per_pe"]["0"] == 12.5


def test_run_config_hash_change_triggers_related_cache_clear(tmp_path):
    run_id = "run_002"
    data_root = tmp_path / "DAQ"
    data_root.mkdir(parents=True)
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    config_path = run_dir / "run_config.json"
    _write_run_config(config_path, gain_value=10.0)

    # First context: baseline hash write
    ctx = Context(config={"data_root": str(data_root)})
    _register_test_plugins(ctx)
    ctx._config_domain.maybe_invalidate_run_config_cache(run_id)
    state_path = Path(ctx._config_domain.get_run_config_hash_state_path(run_id))
    assert state_path.exists()

    # New context simulates a new session reading persisted hash state.
    ctx2 = Context(config={"data_root": str(data_root)})
    _register_test_plugins(ctx2)
    clear_calls = []

    def _fake_clear_cache_for(
        run_id_arg,
        data_name=None,
        downstream=False,
        clear_memory=True,
        clear_disk=True,
        verbose=True,
    ):
        clear_calls.append((run_id_arg, data_name, downstream))
        return 0

    ctx2.clear_cache_for = _fake_clear_cache_for

    # Same hash: should not invalidate.
    ctx2._config_domain.maybe_invalidate_run_config_cache(run_id)
    assert clear_calls == []

    # Changed hash: should invalidate df branch and its downstream.
    _write_run_config(config_path, gain_value=11.0)
    ctx2._config_domain.maybe_invalidate_run_config_cache(run_id)

    assert (run_id, "df", True) in clear_calls
    assert (run_id, "run_cfg_root", True) in clear_calls


def test_get_run_config_path_supports_explicit_template(tmp_path):
    run_id = "run_003"
    data_root = tmp_path / "DAQ"
    data_root.mkdir(parents=True)
    config_dir = tmp_path / "configs"
    config_dir.mkdir(parents=True)
    config_path = config_dir / (run_id + ".json")
    _write_run_config(config_path, gain_value=9.5)

    ctx = Context(
        config={
            "data_root": str(data_root),
            "run_config_path": str(config_dir / "{run_id}.json"),
        }
    )

    loaded = ctx.get_run_config(run_id)

    assert loaded["calibration"]["gain_adc_per_pe"]["0"] == 9.5


def test_run_config_supports_run_number_daq_and_hardware_channels(tmp_path):
    run_id = "50V_OV_circulation_20thr"
    data_root = tmp_path / "DAQ"
    data_root.mkdir(parents=True)
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    config_path = run_dir / "run_config.json"
    _write_payload(
        config_path,
        {
            "schema_version": "1.0",
            "run_number": "001000",
            "run_id": run_id,
            "run_name": run_id,
            "daq": {
                "status": "acquired",
                "start_time": "2026-05-26T10:30:00.000000Z",
                "end_time": None,
                "daq_adapter": "vx2730",
                "trigger_mode": "external",
                "threshold_lsb": 20,
                "sampling_rate_hz": 500000000,
            },
            "hardware": {
                "electrodes": {
                    "anode": {"enabled": True, "voltage_v": 1200.0},
                    "dynode": {"enabled": True, "voltage_v": 800.0},
                    "gate": {"enabled": True, "voltage_v": -50.0},
                },
                "channel_groups": [
                    {
                        "name": "tpc_top_sipm",
                        "channels": ["0:0", "0:1"],
                        "config": {
                            "enabled": True,
                            "detector": "TPC",
                            "role": "top_sipm",
                            "sensor_type": "SiPM",
                            "polarity": "negative",
                            "bias_voltage_v": 48.5,
                        },
                    },
                    {
                        "name": "external_trigger_pmt",
                        "channels": ["1:0"],
                        "config": {
                            "enabled": True,
                            "detector": "PMT_trigger",
                            "role": "external_trigger",
                            "sensor_type": "PMT",
                            "polarity": "positive",
                            "bias_voltage_v": 52.0,
                        },
                    },
                ],
                "channels": {
                    "0:1": {"sensor_id": "S13370-0001", "bias_voltage_v": 49.0},
                    "1:0": {"sensor_id": "R7725-XXX"},
                },
            },
            "calibration": {"gain_adc_per_pe": {"0:0": 12.5}},
            "plugins": {"hit": {"channel_config": {"defaults": {"threshold": 22.0}}}},
        },
    )

    ctx = Context(config={"data_root": str(data_root)})
    loaded = ctx.get_run_config(run_id)
    ctx.validate_run_config(run_id, require_identity=True)
    channels = ctx.get_run_hardware_channels(run_id)

    assert loaded["run_number"] == "001000"
    assert loaded["daq"]["start_time"] == "2026-05-26T10:30:00.000000Z"
    assert channels["0:0"]["polarity"] == "negative"
    assert channels["0:0"]["bias_voltage_v"] == 48.5
    assert channels["0:1"]["bias_voltage_v"] == 49.0
    assert channels["0:1"]["sensor_id"] == "S13370-0001"
    assert channels["1:0"]["detector"] == "PMT_trigger"
    assert channels["1:0"]["sensor_id"] == "R7725-XXX"


@pytest.mark.parametrize(
    "payload, match",
    [
        ({"run_number": "1000"}, "run_number"),
        ({"run_number": "001000", "daq": {"status": "done"}}, "daq.status"),
        (
            {"hardware": {"channels": {"0": {"polarity": "negative"}}}},
            "board:channel",
        ),
        (
            {"hardware": {"channels": {"0:0": {"polarity": "inverted"}}}},
            "polarity",
        ),
    ],
)
def test_run_config_validation_rejects_invalid_metadata(payload, match):
    with pytest.raises(RunConfigValidationError, match=match):
        validate_run_config(payload)


def test_legacy_run_config_without_identity_still_validates():
    validate_run_config(
        {
            "calibration": {"gain_adc_per_pe": {"0:0": 12.5}},
            "plugins": {},
        }
    )
