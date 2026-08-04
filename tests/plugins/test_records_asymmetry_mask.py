import numpy as np

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.records_asymmetry import RecordsAsymmetryMaskPlugin
from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE


def make_test_records(n, polarity=None):
    records = np.zeros(n, dtype=RECORDS_DTYPE)
    records["wave_offset"] = np.arange(n) * 100
    records["event_length"] = 60
    records["baseline"] = 100.0
    if polarity is not None:
        if isinstance(polarity, str):
            records["polarity"] = polarity
        else:
            records["polarity"] = polarity
    return records


def test_negative_polarity():
    """验证负极性信号（baseline=100, w_min=50, w_max=110）."""
    records = make_test_records(1, polarity="negative")
    wave_pool = np.full(100, 100.0, dtype=np.float32)
    wave_pool[10:30] = 50.0
    wave_pool[40:45] = 110.0

    plugin = RecordsAsymmetryMaskPlugin()
    ctx = DummyContext(
        {"asymmetry_cut_min": 0.7, "asymmetry_polarity_mode": "auto"},
        {"records": records, "wave_pool": wave_pool},
    )
    mask = plugin.compute(ctx, "run_001")

    assert mask[0]


def test_positive_polarity():
    """验证正极性信号（baseline=100, w_min=90, w_max=150）."""
    records = make_test_records(1, polarity="positive")
    wave_pool = np.full(100, 100.0, dtype=np.float32)
    wave_pool[10:30] = 150.0
    wave_pool[40:45] = 90.0

    plugin = RecordsAsymmetryMaskPlugin()
    ctx = DummyContext(
        {"asymmetry_cut_min": 0.7, "asymmetry_polarity_mode": "auto"},
        {"records": records, "wave_pool": wave_pool},
    )
    mask = plugin.compute(ctx, "run_001")

    assert mask[0]


def test_mixed_polarity():
    """验证混合极性 records."""
    records = make_test_records(2)
    records[0]["polarity"] = "negative"
    records[1]["polarity"] = "positive"

    wave_pool = np.full(200, 100.0, dtype=np.float32)
    wave_pool[10:30] = 50.0
    wave_pool[110:130] = 150.0

    plugin = RecordsAsymmetryMaskPlugin()
    ctx = DummyContext(
        {"asymmetry_cut_min": 0.7, "asymmetry_polarity_mode": "auto"},
        {"records": records, "wave_pool": wave_pool},
    )
    mask = plugin.compute(ctx, "run_001")

    assert mask[0]
    assert mask[1]


def test_polarity_mode_override():
    """验证配置强制覆盖."""
    records = make_test_records(1, polarity="positive")
    wave_pool = np.full(100, 100.0, dtype=np.float32)
    wave_pool[10:30] = 50.0

    plugin = RecordsAsymmetryMaskPlugin()
    ctx = DummyContext(
        {"asymmetry_cut_min": 0.7, "asymmetry_polarity_mode": "negative"},
        {"records": records, "wave_pool": wave_pool},
    )
    mask = plugin.compute(ctx, "run_001")

    assert mask[0]


def test_no_polarity_field():
    """验证无 polarity 字段时回退到负极性."""
    records = np.zeros(
        1,
        dtype=[
            ("wave_offset", "i8"),
            ("event_length", "i4"),
            ("baseline", "f8"),
        ],
    )
    records["wave_offset"] = 0
    records["event_length"] = 60
    records["baseline"] = 100.0

    wave_pool = np.full(100, 100.0, dtype=np.float32)
    wave_pool[10:30] = 50.0

    plugin = RecordsAsymmetryMaskPlugin()
    ctx = DummyContext(
        {"asymmetry_cut_min": 0.7, "asymmetry_polarity_mode": "auto"},
        {"records": records, "wave_pool": wave_pool},
    )
    mask = plugin.compute(ctx, "run_001")

    assert mask[0]
