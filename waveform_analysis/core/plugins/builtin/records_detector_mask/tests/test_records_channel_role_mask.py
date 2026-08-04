import numpy as np
import pytest

from tests.plugins.test_threshold_hit_plugin import _make_many_records_view
from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.records_detector_mask import (
    RecordsDetectorMaskPlugin,
)
from waveform_analysis.core.plugins.builtin.records_veto_mask import RecordsVetoMaskPlugin


def _compute_masks(config, records=None, asymmetry_mask=None):
    rv = _make_many_records_view(n_records=4) if records is None else records
    records_arr = rv.records if hasattr(rv, "records") else rv
    data = {"records": records_arr}
    if asymmetry_mask is None:
        asymmetry_mask = np.ones(len(records_arr), dtype=np.bool_)
    if asymmetry_mask is not None:
        data["records_asymmetry_mask"] = asymmetry_mask
    ctx = DummyContext(config, data)

    detector = RecordsDetectorMaskPlugin().compute(ctx, "run_001")
    veto = RecordsVetoMaskPlugin().compute(ctx, "run_001")
    return detector, veto


def test_records_channel_role_default_all_detector_after_asymmetry():
    detector, veto = _compute_masks({})

    np.testing.assert_array_equal(detector, np.array([True, True, True, True]))
    np.testing.assert_array_equal(veto, np.array([False, False, False, False]))


def test_records_channel_role_marks_configured_channel_as_veto():
    detector, veto = _compute_masks(
        {
            "channel_config": {
                "channels": {
                    "1:3": {"role": "veto"},
                }
            },
        }
    )

    np.testing.assert_array_equal(detector, np.array([True, True, True, False]))
    np.testing.assert_array_equal(veto, np.array([False, False, False, True]))


def test_records_channel_role_groups_and_channels_override():
    detector, veto = _compute_masks(
        {
            "channel_config": {
                "groups": [
                    {
                        "name": "veto_board0",
                        "channels": ["0:0", "0:2"],
                        "config": {"role": "veto"},
                    }
                ],
                "channels": {
                    "0:2": {"role": "detector"},
                },
            },
        }
    )

    np.testing.assert_array_equal(detector, np.array([False, True, True, True]))
    np.testing.assert_array_equal(veto, np.array([True, False, False, False]))


def test_records_channel_role_applies_asymmetry_after_role_split():
    detector, veto = _compute_masks(
        {
            "channel_config": {
                "channels": {
                    "1:3": {"role": "veto"},
                }
            },
        },
        asymmetry_mask=np.array([True, False, True, True], dtype=np.bool_),
    )

    np.testing.assert_array_equal(detector, np.array([True, False, True, False]))
    np.testing.assert_array_equal(veto, np.array([False, False, False, True]))


def test_records_channel_role_asymmetry_all_false_returns_all_false():
    detector, veto = _compute_masks(
        {
            "channel_config": {"channels": {"1:3": {"role": "veto"}}},
        },
        asymmetry_mask=np.zeros(4, dtype=np.bool_),
    )

    np.testing.assert_array_equal(detector, np.zeros(4, dtype=np.bool_))
    np.testing.assert_array_equal(veto, np.zeros(4, dtype=np.bool_))


def test_records_channel_role_rejects_invalid_role():
    with pytest.raises(ValueError, match="invalid role"):
        _compute_masks(
            {
                "channel_config": {"channels": {"0:0": {"role": "guard"}}},
            }
        )


def test_records_channel_role_rejects_boardless_keys():
    with pytest.raises(ValueError, match="Invalid channel key"):
        _compute_masks(
            {
                "channel_config": {"channels": {"0": {"role": "veto"}}},
            }
        )


def test_records_channel_role_rejects_asymmetry_length_mismatch():
    with pytest.raises(ValueError, match="records_asymmetry_mask length mismatch"):
        _compute_masks(
            {},
            asymmetry_mask=np.array([True], dtype=np.bool_),
        )
