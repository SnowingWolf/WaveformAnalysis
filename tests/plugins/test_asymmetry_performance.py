import time

import numpy as np
import pytest

from tests.utils import DummyContext
from waveform_analysis.core.plugins.builtin.cpu.records_asymmetry import RecordsAsymmetryMaskPlugin
from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE


@pytest.mark.parametrize("n_records", [10000, 100000])
@pytest.mark.parametrize("polarity_mode", ["negative", "positive", "auto"])
def test_asymmetry_performance(n_records, polarity_mode):
    """性能基准测试."""
    records = np.zeros(n_records, dtype=RECORDS_DTYPE)
    records["wave_offset"] = np.arange(n_records) * 100
    records["event_length"] = 60
    records["baseline"] = 100.0
    records["polarity"] = np.where(np.arange(n_records) % 2 == 0, "negative", "positive")

    wave_pool = np.random.uniform(50, 150, size=n_records * 100).astype(np.float32)

    plugin = RecordsAsymmetryMaskPlugin()
    ctx = DummyContext(
        {
            "asymmetry_cut_min": 0.7,
            "asymmetry_polarity_mode": polarity_mode,
            "asymmetry_parallel": False,
        },
        {"records": records, "wave_pool": wave_pool},
    )

    start = time.perf_counter()
    mask = plugin.compute(ctx, "run_001")
    elapsed = (time.perf_counter() - start) * 1000

    print(f"\n{n_records} records, {polarity_mode} mode: {elapsed:.2f}ms")
    assert len(mask) == n_records
