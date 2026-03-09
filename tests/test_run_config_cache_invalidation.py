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


class _EventsDFPlugin(_ConstPlugin):
    provides = "events_df"


class _EventsGroupedPlugin(_ConstPlugin):
    provides = "events_grouped"
    depends_on = ["events_df"]


def _register_test_plugins(ctx: Context):
    ctx.register(
        _DFPlugin(),
        _DFEventsPlugin(),
        _DFPairedPlugin(),
        _EventsDFPlugin(),
        _EventsGroupedPlugin(),
    )


def _write_run_config(path: Path, gain_value: float):
    payload = {
        "meta": {"version": "1"},
        "calibration": {"gain_adc_per_pe": {"0": gain_value}},
        "plugins": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_get_run_config_loads_json(tmp_path):
    run_id = "run_001"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    config_path = run_dir / "run_config.json"
    _write_run_config(config_path, gain_value=12.5)

    ctx = Context(config={"data_root": str(tmp_path)})
    loaded = ctx.get_run_config(run_id)

    assert loaded["calibration"]["gain_adc_per_pe"]["0"] == 12.5


def test_run_config_hash_change_triggers_related_cache_clear(tmp_path):
    run_id = "run_002"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    config_path = run_dir / "run_config.json"
    _write_run_config(config_path, gain_value=10.0)

    # First context: baseline hash write
    ctx = Context(config={"data_root": str(tmp_path)})
    _register_test_plugins(ctx)
    ctx._maybe_invalidate_run_config_cache(run_id)
    state_path = Path(ctx._get_run_config_hash_state_path(run_id))
    assert state_path.exists()

    # New context simulates a new session reading persisted hash state.
    ctx2 = Context(config={"data_root": str(tmp_path)})
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

    # Changed hash: should invalidate df/events_df branches.
    _write_run_config(config_path, gain_value=11.0)
    ctx2._maybe_invalidate_run_config_cache(run_id)

    assert (run_id, "df", True) in clear_calls
    assert (run_id, "events_df", True) in clear_calls
