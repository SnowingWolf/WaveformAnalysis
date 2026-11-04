"""Device grouping must preserve module, registry and pickle identities."""

import importlib
import pickle
import subprocess
import sys

import numpy as np
import pytest

pytestmark = pytest.mark.contract

PREFIX = "waveform_analysis.acquisition.formats"
LEGACY = "waveform_analysis.utils.formats"


@pytest.mark.parametrize("legacy_first", [True, False])
def test_device_modules_are_shared_in_fresh_interpreter(legacy_first):
    # Fresh processes exercise the lazy alias loader in both import orders.
    pairs = [
        (f"{LEGACY}.{leaf}", f"{PREFIX}.{leaf}")
        for leaf in (
            "v1725",
            "v1725.reader",
            "v1725.numba",
            "vx2730",
            "vx2730.csv",
            "vx2730.binary",
        )
    ] + [
        (f"{prefix}.{old}", f"{PREFIX}.{new}")
        for prefix in (PREFIX, LEGACY)
        for old, new in (("v1725_numba", "v1725.numba"), ("vx2730_bin", "vx2730.binary"))
    ]
    code = f"""
import importlib
pairs = {pairs!r}
for old, new in pairs:
    first, second = (old, new) if {legacy_first!r} else (new, old)
    assert importlib.import_module(first) is importlib.import_module(second), (first, second)
from waveform_analysis.acquisition.formats import get_adapter, get_format_reader
from waveform_analysis.acquisition.formats.v1725 import V1725_ADAPTER, V1725Reader
from waveform_analysis.acquisition.formats.vx2730 import VX2730_ADAPTER, VX2730_BIN_ADAPTER, VX2730BinReader
assert get_adapter('v1725') is V1725_ADAPTER
assert get_adapter('vx2730') is VX2730_ADAPTER
assert get_adapter('vx2730_bin') is VX2730_BIN_ADAPTER
assert isinstance(get_format_reader('v1725_bin'), V1725Reader)
assert isinstance(get_format_reader('vx2730_bin'), VX2730BinReader)
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, text=True)


@pytest.mark.parametrize(
    "module_name,class_names",
    [
        (f"{LEGACY}.v1725", ("V1725Reader", "V1725Adapter", "V1725Spec")),
        (f"{LEGACY}.vx2730", ("VX2730Reader", "VX2730Spec")),
        (f"{LEGACY}.vx2730_bin", ("VX2730BinReader", "VX2730BinSpec", "VX2730BinLayout")),
        (f"{PREFIX}.v1725", ("V1725Wave",)),
    ],
)
def test_old_pickle_class_paths_still_resolve(module_name, class_names):
    module = importlib.import_module(module_name)
    for name in class_names:
        cls = getattr(module, name)
        assert cls.__module__ == module_name
        # Protocol 0 GLOBAL encodes the pre-migration path independently of the current class.
        old_pickle = f"c{module_name}\n{name}\n.".encode()
        assert pickle.loads(old_pickle) is cls
        assert pickle.loads(pickle.dumps(cls)) is cls


def test_v1725_wave_pickle_roundtrip():
    from waveform_analysis.acquisition.formats.v1725 import V1725Wave

    wave = V1725Wave(1, 2, 123, False, 10, np.array([1, 2, 3], dtype=np.int16))
    restored = pickle.loads(pickle.dumps(wave))
    assert type(restored) is V1725Wave
    assert (
        restored.board,
        restored.channel,
        restored.timestamp,
        restored.trunc,
        restored.baseline,
    ) == (1, 2, 123, False, 10)
    np.testing.assert_array_equal(restored.waveform, wave.waveform)
