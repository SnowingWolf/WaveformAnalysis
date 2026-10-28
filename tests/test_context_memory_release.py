import gc
import weakref

import numpy as np
import pytest

from tests.utils import DependentPlugin, MockPlugin
from waveform_analysis import Context
from waveform_analysis.core.processing.dtypes import RECORDS_DTYPE
from waveform_analysis.core.processing.records_builder import RecordsBundle, RecordsBundleRef


@pytest.fixture
def context(tmp_path):
    ctx = Context(storage_dir=str(tmp_path / "cache"))
    ctx.register(MockPlugin)
    return ctx


@pytest.mark.parametrize("data_name", ["mock_data", None])
def test_clear_memory_releases_product_attribute(context, data_name):
    data = context.get_data("run1", "mock_data")
    data_ref = weakref.ref(data)
    assert context.mock_data is data
    del data

    count = context.clear_cache_for("run1", data_name, clear_disk=False, verbose=False)
    gc.collect()

    assert count == 1
    assert ("run1", "mock_data") not in context._results
    assert ("run1", "mock_data") not in context._results_lineage
    assert "mock_data" not in vars(context)
    assert data_ref() is None
    assert context._get_data_from_memory("run1", "mock_data") is None

    reloaded = context.get_data("run1", "mock_data")
    assert len(reloaded) == 2


@pytest.mark.parametrize("cleared_run", ["run1", "run2"])
def test_clear_memory_preserves_other_run(context, cleared_run):
    first = context.get_data("run1", "mock_data")
    second = context.get_data("run2", "mock_data")
    first_ref = weakref.ref(first)
    second_ref = weakref.ref(second)
    del first, second

    context.clear_cache_for(cleared_run, "mock_data", clear_disk=False, verbose=False)
    gc.collect()

    if cleared_run == "run1":
        assert first_ref() is None
        assert context.mock_data is second_ref()
        assert context.get_data("run2", "mock_data") is second_ref()
    else:
        assert second_ref() is None
        assert "mock_data" not in vars(context)
        assert context.get_data("run1", "mock_data") is first_ref()


def test_clear_memory_preserves_shared_object_for_other_run(context):
    data = np.zeros(2, dtype=MockPlugin.output_dtype)
    data_ref = weakref.ref(data)
    context._set_data("run1", "mock_data", data)
    context._set_data("run2", "mock_data", data)
    del data

    context.clear_cache_for("run1", "mock_data", clear_disk=False, verbose=False)

    assert context.mock_data is data_ref()
    assert context.get_data("run2", "mock_data") is data_ref()

    context.clear_cache_for("run2", "mock_data", clear_disk=False, verbose=False)
    gc.collect()

    assert "mock_data" not in vars(context)
    assert data_ref() is None


def test_clear_memory_preserves_replaced_attribute(context):
    data = context.get_data("run1", "mock_data")
    data_ref = weakref.ref(data)
    replacement = data.copy()
    context.mock_data = replacement
    assert context.get_data("run1", "mock_data") is data
    del data

    context.clear_cache_for("run1", "mock_data", clear_disk=False, verbose=False)
    gc.collect()

    assert data_ref() is None
    assert context.mock_data is replacement
    assert context._get_data_from_memory("run1", "mock_data") is None


@pytest.mark.parametrize("name", ["logger", "manual-data", "class_data"])
def test_clear_memory_preserves_attributes_not_exposed_by_set_data(context, monkeypatch, name):
    if name == "logger":
        value = context.logger
    else:
        value = np.zeros(2)
        if name == "class_data":
            monkeypatch.setattr(Context, name, object(), raising=False)
        setattr(context, name, value)

    if name == "manual-data":
        context._set_data("run1", name, value)
    else:
        with pytest.warns(
            UserWarning, match="conflicts with a Context method or reserved attribute"
        ):
            context._set_data("run1", name, value)

    context.clear_cache_for("run1", name, clear_disk=False, verbose=False)

    assert vars(context)[name] is value
    assert ("run1", name) not in context._results


def test_clear_memory_false_keeps_product_and_attribute(context):
    data = context.get_data("run1", "mock_data")

    count = context.clear_cache_for(
        "run1", "mock_data", clear_memory=False, clear_disk=False, verbose=False
    )

    assert count == 0
    assert context.mock_data is data
    assert context.get_data("run1", "mock_data") is data


def test_clear_memory_releases_downstream_attributes(context):
    context.register(DependentPlugin)
    data = context.get_data("run1", "dependent_data")
    data_ref = weakref.ref(data)
    source_ref = weakref.ref(context.mock_data)
    del data

    count = context.clear_cache_for(
        "run1", "mock_data", downstream=True, clear_disk=False, verbose=False
    )
    gc.collect()

    assert count == 2
    assert data_ref() is None
    assert source_ref() is None
    assert "mock_data" not in vars(context)
    assert "dependent_data" not in vars(context)


def test_clear_memory_releases_records_bundle_and_product_arrays(context):
    bundle = RecordsBundle(
        records=np.zeros(2, dtype=RECORDS_DTYPE),
        wave_pool=np.zeros(4, dtype=np.uint16),
    )
    bundle_name = "_records_bundle-run1-records-lineage"
    bundle_ref = weakref.ref(bundle)
    records_ref = weakref.ref(bundle.records)
    pool_ref = weakref.ref(bundle.wave_pool)
    context._set_data("run1", bundle_name, bundle)
    context._set_data("run1", "records", bundle.records)
    context._set_data("run1", "wave_pool", bundle.wave_pool)
    assert bundle_name not in vars(context)
    del bundle

    count = context.clear_cache_for("run1", "records", clear_disk=False, verbose=False)
    gc.collect()

    assert count == 2
    assert bundle_ref() is None
    assert records_ref() is None
    assert context.wave_pool is pool_ref()

    assert context.clear_cache_for("run1", "wave_pool", clear_disk=False, verbose=False) == 1
    gc.collect()
    assert pool_ref() is None


def test_clear_memory_cleans_only_requested_run_bundle(context, tmp_path):
    first_dir = tmp_path / "run1-parts"
    second_dir = tmp_path / "run2-parts"
    first_dir.mkdir()
    second_dir.mkdir()
    first = RecordsBundleRef([], 0, 0, temp_dir=first_dir)
    second = RecordsBundleRef([], 0, 0, temp_dir=second_dir)
    name = "_records_bundle-records-lineage"
    first_ref = weakref.ref(first)
    context._set_data("run1", name, first)
    context._set_data("run2", name, second)
    del first

    count = context.clear_cache_for("run1", "records", clear_disk=False, verbose=False)
    gc.collect()

    assert count == 1
    assert first_ref() is None
    assert not first_dir.exists()
    assert second_dir.is_dir()
    assert context._results[("run2", name)] is second
