import numpy as np

from tests.utils import DummyContext, make_st_waveforms
from waveform_analysis.core.plugins.builtin.cpu.filtering import FilteredWaveformsPlugin


def test_filtered_waveforms_uses_explicit_fs():
    st_waveforms = make_st_waveforms(n_events=1, n_samples=64)
    st_waveforms["wave"][0] = np.linspace(0, 1, 64)
    ctx = DummyContext(
        {
            "filtered_waveforms": {
                "filter_type": "BW",
                "lowcut": 0.1,
                "highcut": 0.4,
                "fs": 1.0,
            }
        },
        {"st_waveforms": st_waveforms},
    )
    plugin = FilteredWaveformsPlugin()

    result = plugin.compute(ctx, "run_001")

    assert isinstance(result, np.ndarray)
    assert result.shape[0] == 1
