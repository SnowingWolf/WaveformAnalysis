"""Behavior preserved while consolidating Context's cache and config paths."""

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from waveform_analysis import Context
from waveform_analysis.core.plugins.core.base import Option, Plugin

LONG_HELP = "Description of the untracked option. " * 4
LONG_VALUE = "value" * 20
OPTION_COLUMNS = ["type", "default", "current", "status", "help", "track"]


class _AlphaConfigPlugin(Plugin):
    provides = "alpha_config"
    description = "Alpha options"
    version = "1.2.3"
    options = {
        "z_default": Option(default=1, type=int),
        "no_type": Option(default=None),
        "a_modified": Option(default="baseline", type=str),
        "global_option": Option(default=7, type=int),
    }

    def compute(self, context, run_id):
        return np.array([1])


class _ZetaConfigPlugin(Plugin):
    provides = "zeta_config"
    options = {
        "untracked": Option(default="default", type=str, help=LONG_HELP, track=False),
        "tuple_type": Option(default=2, type=(int, float), help="Numeric value"),
    }

    def compute(self, context, run_id):
        return np.array([1])


@pytest.fixture
def config_context(tmp_path):
    ctx = Context(
        storage_dir=str(tmp_path),
        config={
            "zeta_config": {"untracked": LONG_VALUE, "tuple_type": 4.0},
            "alpha_config": {"a_modified": "changed", "z_default": 1, "no_type": None},
            "global_option": 7,
        },
    )
    # Registration and option declaration order deliberately differ from display order.
    ctx.register(_ZetaConfigPlugin, _AlphaConfigPlugin)
    return ctx


@pytest.fixture
def displayed(monkeypatch):
    import IPython.display

    items = []
    monkeypatch.setattr(IPython.display, "display", items.append)
    return items


@pytest.mark.parametrize("show_full_help", [False, True])
def test_option_metadata_and_tables_match_both_config_views(
    config_context, displayed, show_full_help
):
    result = config_context.list_plugin_configs(show_full_help=show_full_help)
    overview, option_style = displayed
    options = option_style.data

    assert list(overview.index) == ["zeta_config", "alpha_config"]
    assert list(overview.columns) == ["class", "version", "description", "options", "modified"]
    assert overview["modified"].tolist() == [2, 1]
    assert overview["options"].tolist() == [2, 4]
    assert result["alpha_config"]["version"] == "1.2.3"
    assert result["alpha_config"]["options"]["no_type"] == {
        "default": None,
        "type": "Any",
        "help": "",
        "track": True,
        "current_value": None,
        "is_default": True,
    }
    assert result["zeta_config"]["options"]["tuple_type"]["type"] == str((int, float))
    assert list(options.columns) == OPTION_COLUMNS
    assert options.index.names == ["plugin", "option"]
    assert list(options.index) == [
        ("alpha_config", "a_modified"),
        ("zeta_config", "tuple_type"),
        ("zeta_config", "untracked"),
        ("alpha_config", "global_option"),
        ("alpha_config", "no_type"),
        ("alpha_config", "z_default"),
    ]
    untracked = options.loc[("zeta_config", "untracked")]
    assert untracked["default"] == "'default'"
    assert untracked["current"] == repr(LONG_VALUE)[:57] + "..."
    assert untracked["status"] == "已修改"
    assert not untracked["track"]
    assert untracked["help"] == (LONG_HELP if show_full_help else repr(LONG_HELP)[:77] + "...")
    assert options.loc[("alpha_config", "no_type"), "current"] == "None"
    html = option_style.to_html()
    assert "var(--jp-error-color2" in html  # Untracked options have their own highlight.
    assert "var(--jp-warn-color2" in html
    assert "font-weight: 600" in html

    displayed.clear()
    config_context.show_config(show_full_help=show_full_help)
    global_table, summary_style, context_table = displayed[:3]
    assert list(global_table.columns) == ["value", "used_by"]
    assert global_table.loc["global_option"].tolist() == ["7", "'alpha_config'"]
    expected = options.drop(index=("alpha_config", "global_option"))
    pd.testing.assert_frame_equal(summary_style.data, expected)
    assert "storage_dir" in context_table.index
    assert "var(--jp-error-color2" in summary_style.to_html()


def test_config_summary_keeps_explicit_value_while_option_list_resolves_it(tmp_path, displayed):
    class ConvertedPlugin(Plugin):
        provides = "converted_config"
        options = {"threshold": Option(default=2, type=int)}

        def compute(self, context, run_id):
            return np.array([1])

    ctx = Context(storage_dir=str(tmp_path), config={"converted_config": {"threshold": "2"}})
    ctx.register(ConvertedPlugin)
    result = ctx.list_plugin_configs()
    listed = displayed[1].data.loc[("converted_config", "threshold")]
    assert result["converted_config"]["options"]["threshold"]["current_value"] == 2
    assert listed["current"] == "2"
    assert listed["status"] == "默认"

    displayed.clear()
    ctx.show_config()
    summary = displayed[0].data.loc[("converted_config", "threshold")]
    assert summary["current"] == "'2'"
    assert summary["status"] == "已修改"


def test_default_only_config_view_keeps_columns_without_current_values(config_context, displayed):
    result = config_context.list_plugin_configs(show_current_values=False)
    overview, option_style = displayed
    assert list(overview.index) == ["alpha_config", "zeta_config"]
    assert overview["modified"].isna().all()
    assert list(option_style.data.columns) == OPTION_COLUMNS
    assert list(option_style.data.index) == sorted(option_style.data.index)
    assert option_style.data[["current", "status"]].isna().all().all()
    for plugin in result.values():
        for option in plugin["options"].values():
            assert "current_value" not in option
            assert "is_default" not in option
    html = option_style.to_html()
    assert "var(--jp-error-color2" not in html
    assert "var(--jp-warn-color2" not in html


@pytest.mark.parametrize("entry_point", ["list", "summary"])
def test_config_tables_fall_back_to_terminal_without_ipython(
    config_context, monkeypatch, capsys, entry_point
):
    monkeypatch.setitem(sys.modules, "IPython.display", None)
    if entry_point == "list":
        config_context.list_plugin_configs(show_full_help=True)
    else:
        config_context.show_config(show_usage=False, show_full_help=True)
    output = capsys.readouterr().out
    heading = "配置选项明细" if entry_point == "list" else "插件特定配置"
    assert heading in output
    assert "tuple_type" in output
    assert "Any" in output
    assert LONG_HELP in output
    assert repr(LONG_VALUE)[:57] + "..." in output
    assert "_is_default" not in output
    assert "_current_raw" not in output
    if entry_point == "summary":
        assert "used_by" not in output


@pytest.mark.parametrize("cache_source", ["memory", "disk"])
def test_cached_get_data_records_one_hit_and_preserves_array(tmp_path, cache_source):
    calls = []

    class CachedPlugin(Plugin):
        provides = "simplification_cached"
        save_when = "always"
        output_dtype = np.dtype([("value", "i4")])

        def compute(self, context, run_id):
            calls.append(run_id)
            return np.array([(2,), (5,)], dtype=self.output_dtype)

    writer = Context(storage_dir=str(tmp_path), stats_mode="basic")
    writer.register(CachedPlugin)
    original = writer.get_data("run_001", "simplification_cached")
    if cache_source == "memory":
        reader = writer
        reader.stats_collector.reset()
    else:
        reader = Context(storage_dir=str(tmp_path), stats_mode="basic")
        reader.register(CachedPlugin)

    result = reader.get_data("run_001", "simplification_cached", output="array")
    assert isinstance(result, np.ndarray)
    np.testing.assert_array_equal(result, original)
    if cache_source == "memory":
        assert result is original
    assert calls == ["run_001"]
    stats = reader.stats_collector.get_statistics("simplification_cached")["simplification_cached"]
    assert (stats.total_calls, stats.cache_hits, stats.cache_misses) == (1, 1, 0)
    assert (stats.successful_calls, stats.failed_calls) == (1, 0)


@pytest.mark.parametrize(
    ("auto_fix", "dry_run", "verbose"),
    [(False, True, True), (True, True, True), (True, False, False)],
)
def test_diagnose_cache_scans_all_runs_then_filters_and_forwards_fix_options(
    tmp_path, monkeypatch, auto_fix, dry_run, verbose
):
    ctx = Context(storage_dir=str(tmp_path))
    analyzer_factory = Mock()
    diagnostics_factory = Mock()
    monkeypatch.setattr(
        "waveform_analysis.core.storage.cache_analyzer.CacheAnalyzer", analyzer_factory
    )
    monkeypatch.setattr(
        "waveform_analysis.core.storage.cache_diagnostics.CacheDiagnostics", diagnostics_factory
    )
    diagnostics = diagnostics_factory.return_value
    issues = [SimpleNamespace(fixable=True), SimpleNamespace(fixable=False)]
    diagnostics.diagnose.return_value = issues
    diagnostics.auto_fix.return_value = {"total": 2, "fixable": 1, "fixed": 1}

    assert ctx.diagnose_cache("run_001", auto_fix, dry_run, verbose) is issues
    analyzer_factory.assert_called_once_with(ctx)
    scan = analyzer_factory.return_value.scan
    scan.assert_called_once()
    assert scan.call_args.kwargs.get("run_ids") is None
    assert scan.call_args.kwargs["verbose"] is False
    diagnostics_factory.assert_called_once_with(analyzer_factory.return_value)
    diagnostics.diagnose.assert_called_once_with(run_id="run_001", verbose=verbose)
    if verbose:
        diagnostics.print_report.assert_called_once_with(issues)
    else:
        diagnostics.print_report.assert_not_called()
    if auto_fix:
        diagnostics.auto_fix.assert_called_once_with(issues, dry_run=dry_run)
    else:
        diagnostics.auto_fix.assert_not_called()


@pytest.mark.parametrize(
    ("run_id", "detailed", "export_name", "export_format"),
    [
        (None, False, None, None),
        ("run_001", True, "stats.csv", "csv"),
        ("run_001", False, "stats.json", "json"),
    ],
)
def test_cache_stats_scans_all_runs_then_filters_and_exports(
    tmp_path, monkeypatch, run_id, detailed, export_name, export_format
):
    ctx = Context(storage_dir=str(tmp_path))
    analyzer_factory = Mock()
    collector_factory = Mock()
    monkeypatch.setattr(
        "waveform_analysis.core.storage.cache_analyzer.CacheAnalyzer", analyzer_factory
    )
    monkeypatch.setattr(
        "waveform_analysis.core.storage.cache_statistics.CacheStatsCollector", collector_factory
    )
    collector = collector_factory.return_value
    export_path = str(tmp_path / export_name) if export_name else None

    assert ctx.cache_stats(run_id, detailed, export_path) is collector.collect.return_value
    analyzer_factory.assert_called_once_with(ctx)
    scan = analyzer_factory.return_value.scan
    scan.assert_called_once()
    assert scan.call_args.kwargs.get("run_ids") is None
    assert scan.call_args.kwargs["verbose"] is False
    collector_factory.assert_called_once_with(analyzer_factory.return_value)
    collector.collect.assert_called_once_with(run_id=run_id)
    collector.print_summary.assert_called_once_with(
        collector.collect.return_value, detailed=detailed
    )
    if export_path:
        collector.export_stats.assert_called_once_with(
            collector.collect.return_value, export_path, format=export_format
        )
    else:
        collector.export_stats.assert_not_called()


@pytest.mark.parametrize("parallel", [False, True])
@pytest.mark.parametrize("cache_source", ["memory", "disk"])
def test_cached_dependency_is_loaded_once_in_execution_plan(tmp_path, parallel, cache_source):
    calls = []

    class Source(Plugin):
        provides = "cached_source"
        save_when = "always"
        output_dtype = np.dtype([("value", "i4")])

        def compute(self, context, run_id):
            calls.append("source")
            return np.array([(3,)], dtype=self.output_dtype)

    class Left(Plugin):
        provides = "cached_left"
        depends_on = ["cached_source"]

        def compute(self, context, run_id):
            return np.array([1])

    class Right(Plugin):
        provides = "cached_right"
        depends_on = ["cached_source"]

        def compute(self, context, run_id):
            return np.array([2])

    class Target(Plugin):
        provides = "cached_target"
        depends_on = ["cached_left", "cached_right"]

        def compute(self, context, run_id):
            return np.array([4])

    def make_context():
        ctx = Context(
            storage_dir=str(tmp_path),
            stats_mode="basic",
            config={"show_progress": False, "enable_plugin_parallelism": parallel},
        )
        ctx.register(Source, Left, Right, Target)
        return ctx

    writer = make_context()
    writer.get_data("run_001", "cached_source")
    if cache_source == "memory":
        reader = writer
        reader.stats_collector.reset()
    else:
        reader = make_context()

    np.testing.assert_array_equal(reader.get_data("run_001", "cached_target"), [4])
    assert calls == ["source"]
    assert ("run_001", "cached_source") in reader._results
    stats = reader.stats_collector.get_statistics("cached_source")["cached_source"]
    assert (stats.total_calls, stats.cache_hits, stats.cache_misses) == (1, 1, 0)
