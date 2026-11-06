"""Adapter metadata follows the live registry and propagates invalid metadata."""

from dataclasses import replace
import inspect

import pytest

from waveform_analysis import Context
from waveform_analysis.acquisition.formats import (
    FLAT_LAYOUT,
    DAQAdapter,
    FormatSpec,
    GenericCSVReader,
    get_adapter,
    register_adapter,
    unregister_adapter,
)
from waveform_analysis.core import config
from waveform_analysis.core.config import AdapterInfo, ConfigSource, get_adapter_info
from waveform_analysis.core.config import adapter_info as adapter_info_module
from waveform_analysis.core.plugins.core.base import Option, Plugin


@pytest.fixture
def registered_adapter(request):
    name = f"adapter_info_{request.node.name}"

    def register(**metadata):
        spec = FormatSpec(name=name, sampling_rate_hz=500e6)
        spec = replace(spec, **metadata)
        adapter = DAQAdapter(name, GenericCSVReader(spec), FLAT_LAYOUT)
        register_adapter(adapter)
        return adapter

    adapter = register()
    yield adapter, register
    unregister_adapter(name)


def test_registry_replacement_updates_adapter_info(registered_adapter):
    adapter, register = registered_adapter
    assert get_adapter_info(adapter.name).dt_ns == 2

    register(sampling_rate_hz=250e6)

    info = get_adapter_info(adapter.name)
    assert info.sampling_rate_hz == 250e6
    assert info.dt_ns == 4
    assert info.dt_ps == 4000


def test_unregistered_adapter_has_no_metadata(registered_adapter):
    adapter, _ = registered_adapter
    assert get_adapter_info(adapter.name) is not None

    assert unregister_adapter(adapter.name)

    assert get_adapter_info(adapter.name) is None
    assert AdapterInfo.from_adapter(adapter.name) is None


@pytest.mark.parametrize(
    "metadata, error",
    [
        ({"sampling_rate_hz": "invalid"}, TypeError),
        ({"timestamp_unit": "ps"}, AttributeError),
        ({"raw_timestamp_mode": "sample_index"}, AttributeError),
    ],
)
def test_invalid_registered_metadata_raises(registered_adapter, metadata, error):
    _, register = registered_adapter
    adapter = register(**metadata)

    with pytest.raises(error):
        get_adapter_info(adapter.name)
    with pytest.raises(error):
        AdapterInfo.from_adapter_object(adapter)


def test_name_conversion_uses_object_conversion(registered_adapter, monkeypatch):
    adapter, _ = registered_adapter
    expected = AdapterInfo.from_adapter_object(adapter)
    converted = []

    def convert(cls, value):
        converted.append(value)
        return expected

    monkeypatch.setattr(AdapterInfo, "from_adapter_object", classmethod(convert))

    assert AdapterInfo.from_adapter(adapter.name) is expected
    assert converted == [adapter]


@pytest.mark.parametrize(
    "name, rate, unit, mode, dt_ns",
    [
        ("vx2730", 500e6, "ps", "unit", 2),
        ("vx2730_bin", 500e6, "ps", "unit", 2),
        ("v1725", 250e6, "ns", "sample_index", 4),
    ],
)
def test_builtin_metadata_preserves_clock_semantics(name, rate, unit, mode, dt_ns):
    expected = {
        "name": name,
        "sampling_rate_hz": rate,
        "timestamp_unit": unit,
        "raw_timestamp_mode": mode,
        "dt_ns": dt_ns,
        "dt_ps": dt_ns * 1000,
    }
    assert get_adapter_info(name).to_dict() == expected
    assert AdapterInfo.from_adapter_object(get_adapter(name)).to_dict() == expected


class MetadataConsumer(Plugin):
    provides = "adapter_info_consumer"
    depends_on = []
    options = {
        "sampling_rate_hz": Option(default=100e6, type=float),
        "dt_ns": Option(default=10, type=int),
        "dt_ps": Option(default=10000, type=int),
    }

    def compute(self, context, run_id, **kwargs):
        return None


def test_new_context_infers_replaced_registry_metadata(registered_adapter, tmp_path):
    adapter, register = registered_adapter
    before = Context(storage_dir=str(tmp_path / "before"), config={"daq_adapter": adapter.name})
    before.register(MetadataConsumer)
    assert before.get_config(MetadataConsumer.provides).get("dt_ns") == 2

    register(sampling_rate_hz=250e6)
    after = Context(storage_dir=str(tmp_path / "after"), config={"daq_adapter": adapter.name})
    after.register(MetadataConsumer)

    resolved = after.get_config(MetadataConsumer.provides)
    assert resolved.get("sampling_rate_hz") == 250e6
    assert resolved.get("dt_ns") == 4
    assert resolved.get("dt_ps") == 4000
    assert resolved.get_value("dt_ns").source == ConfigSource.ADAPTER_INFERRED


def test_cache_parameter_is_removed():
    assert list(inspect.signature(get_adapter_info).parameters) == ["adapter_name"]
    with pytest.raises(TypeError, match="use_cache"):
        get_adapter_info("vx2730", use_cache=False)


@pytest.mark.parametrize("module", [config, adapter_info_module])
def test_clear_cache_export_is_removed(module):
    assert "clear_adapter_info_cache" not in module.__all__
    assert "clear_adapter_info_cache" not in dir(module)
    assert not hasattr(module, "clear_adapter_info_cache")
