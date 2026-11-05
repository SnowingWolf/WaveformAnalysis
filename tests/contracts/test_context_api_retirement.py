"""Context API retirement must preserve configuration and cache behavior."""

import importlib
import inspect
import warnings

import numpy as np
import pytest

from waveform_analysis import Context
from waveform_analysis.core import storage
from waveform_analysis.core.data.batch_processor import BatchProcessor
from waveform_analysis.plugins import Option, Plugin

pytestmark = pytest.mark.contract


class ConfigSource(Plugin):
    provides = "api_source"
    save_when = "always"
    options = {"threshold": Option(default=2, type=int)}
    output_dtype = np.dtype([("value", "i4")])

    def __init__(self):
        super().__init__()
        self.compute_calls = 0

    def compute(self, context, run_id, **kwargs):
        self.compute_calls += 1
        return np.array([(context.get_config(self, "threshold"),)], dtype=self.output_dtype)


class DerivedData(Plugin):
    provides = "api_derived"
    save_when = "always"
    depends_on = ("api_source",)
    output_dtype = ConfigSource.output_dtype

    def compute(self, context, run_id, **kwargs):
        source = context.get_data(run_id, "api_source")
        return np.array([(source["value"][0] * 3,)], dtype=self.output_dtype)


@pytest.fixture
def api_context(tmp_path):
    ctx = Context(storage_dir=str(tmp_path / "cache"), config={"daq_adapter": "v1725"})
    ctx.register(ConfigSource)
    ctx.register(DerivedData)
    return ctx


def test_retired_context_members_are_absent(api_context):
    for name in (
        "clear_config_cache",
        "clear_performance_caches",
        "profiling_summary",
        "validate_run_config",
        "get_run_hardware_channels",
        "get_plugin_run_config",
        "preview_execution",
        "analyze_dependencies",
        "analyze_cache",
        "cache_stats",
    ):
        assert not hasattr(Context, name)
        assert not hasattr(api_context, name)

    with api_context.profiler.timeit("api_task"):
        pass
    assert "api_task" in api_context.profiler.summary()


def test_runtime_cache_manager_public_export_and_module_are_removed():
    assert "RuntimeCacheManager" not in storage.__all__
    assert not hasattr(storage, "RuntimeCacheManager")
    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module("waveform_analysis.core.storage.cache_manager")
    assert exc_info.value.name == "waveform_analysis.core.storage.cache_manager"


def test_context_signatures_expose_only_supported_parameters():
    assert tuple(inspect.signature(Context.get_lineage).parameters) == ("self", "data_name")
    assert tuple(inspect.signature(Context.diagnose_cache).parameters) == (
        "self",
        "run_id",
        "verbose",
    )
    assert tuple(inspect.signature(Context.show_config).parameters) == (
        "self",
        "data_name",
        "show_usage",
        "show_full_help",
        "run_name",
    )


def test_removed_parameters_are_rejected(api_context):
    with pytest.raises(TypeError, match="_visited"):
        api_context.get_lineage("api_derived", _visited=set())
    for keyword in ("auto_fix", "dry_run"):
        with pytest.raises(TypeError, match=keyword):
            api_context.diagnose_cache(**{keyword: True})
    with pytest.raises(TypeError, match="run_id"):
        api_context.show_config(run_id="run_1")


def test_set_config_refreshes_downstream_lineage_keys_and_data(api_context):
    ctx = api_context
    source = ctx.get_plugin("api_source")
    run_id = "run_1"
    initial_lineage = ctx.get_lineage("api_derived")
    initial_key = ctx.key_for(run_id, "api_derived")
    assert ctx.get_data(run_id, "api_derived")["value"].tolist() == [6]
    assert source.compute_calls == 1
    assert "adapter_info" in initial_lineage
    assert "adapter_info" not in initial_lineage["depends_on"]["api_source"]

    ctx.set_config({"threshold": 5}, plugin_name="api_source")

    changed_lineage = ctx.get_lineage("api_derived")
    assert changed_lineage["depends_on"]["api_source"]["config"]["threshold"] == 5
    assert ctx.key_for(run_id, "api_derived") != initial_key
    assert ctx.get_data(run_id, "api_derived")["value"].tolist() == [15]
    assert source.compute_calls == 2

    ctx.set_config({"threshold": 2}, plugin_name="api_source")

    assert ctx.get_lineage("api_derived") == initial_lineage
    assert ctx.key_for(run_id, "api_derived") == initial_key
    assert ctx.get_data(run_id, "api_derived")["value"].tolist() == [6]
    assert source.compute_calls == 2


@pytest.mark.parametrize("use_factory", [False, True])
def test_batch_config_grid_uses_each_configuration(api_context, use_factory):
    result = BatchProcessor(api_context).process_runs_with_config_grid(
        run_ids=["run_1"],
        data_name="api_derived",
        plugin_name="api_source",
        configs=[{"threshold": 4}, {"threshold": 7}],
        max_workers=2 if use_factory else 1,
        context_factory=api_context.clone if use_factory else None,
        executor_type="thread",
        show_progress=False,
        jupyter_mode=False,
        on_error="raise",
    )
    assert [
        entry["batch"]["results"]["run_1"]["value"].tolist() for entry in result["results"]
    ] == [
        [12],
        [21],
    ]


def test_retiring_dependency_analysis_preserves_static_dag(api_context):
    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module("waveform_analysis.core.data.dependency_analysis")
    assert exc_info.value.name == "waveform_analysis.core.data.dependency_analysis"
    assert api_context.resolve_dependencies("api_derived") == ["api_source", "api_derived"]
    assert "api_source" in api_context.get_lineage("api_derived")["depends_on"]


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({}, "<run_id>"),
        ({"run_name": "display_run"}, "display_run"),
        ({"data_name": "api_source"}, "api_source"),
        ({"data_name": "api_source", "run_name": "display_run"}, "api_source"),
    ],
)
def test_show_config_views_work_without_warnings(api_context, capsys, kwargs, expected):
    before_key = api_context.key_for("run_1", "api_derived")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        api_context.show_config(**kwargs)
    assert not caught
    assert expected in capsys.readouterr().out
    assert api_context.key_for("run_1", "api_derived") == before_key
