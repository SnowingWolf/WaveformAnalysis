import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.hit_threshold.tests.test_hit_threshold import (
    _make_many_records_view,
)
from waveform_analysis.core.plugins.builtin.records_veto_mask import RecordsVetoMaskPlugin


def _compute_veto(config, asymmetry_mask=None):
    rv = _make_many_records_view(n_records=4)
    records = rv.records if hasattr(rv, "records") else rv
    data = {"records": records}
    if asymmetry_mask is None:
        asymmetry_mask = np.ones(len(records), dtype=np.bool_)
    data["records_asymmetry_mask"] = asymmetry_mask
    ctx = DummyContext(config, data)
    return RecordsVetoMaskPlugin().compute(ctx, "run_001")


def test_veto_default_all_false():
    veto = _compute_veto({})

    np.testing.assert_array_equal(veto, np.array([False, False, False, False]))


def test_veto_marks_configured_channel():
    veto = _compute_veto(
        {
            "channel_config": {
                "channels": {
                    "1:3": {"role": "veto"},
                }
            },
        }
    )

    np.testing.assert_array_equal(veto, np.array([False, False, False, True]))


def test_veto_applies_asymmetry_after_role_split():
    veto = _compute_veto(
        {
            "channel_config": {
                "channels": {
                    "1:3": {"role": "veto"},
                }
            },
        },
        asymmetry_mask=np.array([True, False, True, True], dtype=np.bool_),
    )

    np.testing.assert_array_equal(veto, np.array([False, False, False, True]))


def test_veto_asymmetry_all_false_returns_all_false():
    veto = _compute_veto(
        {
            "channel_config": {"channels": {"1:3": {"role": "veto"}}},
        },
        asymmetry_mask=np.zeros(4, dtype=np.bool_),
    )

    np.testing.assert_array_equal(veto, np.zeros(4, dtype=np.bool_))


def test_veto_metadata():
    plugin = RecordsVetoMaskPlugin()
    assert plugin.provides == "records_veto_mask"
    assert plugin.version == "0.1.0"
    assert plugin.role == "veto"
