import json
from pathlib import Path

import numpy as np

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


class _DFEventsPlugin(_ConstPlugin):
    provides = "df_events"
    depends_on = ["df"]


class _DFPairedPlugin(_ConstPlugin):
    provides = "df_paired"
    depends_on = ["df_events"]


def _register_test_plugins(ctx: Context):
    ctx.register(
        _DFPlugin(),
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
    ctx._maybe_invalidate_run_config_cache(run_id)
    state_path = Path(ctx._get_run_config_hash_state_path(run_id))
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
    ctx2._maybe_invalidate_run_config_cache(run_id)
    assert clear_calls == []

    # Changed hash: should invalidate df branch and its downstream.
    _write_run_config(config_path, gain_value=11.0)
    ctx2._maybe_invalidate_run_config_cache(run_id)

    assert (run_id, "df", True) in clear_calls


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
