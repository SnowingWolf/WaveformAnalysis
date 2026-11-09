"""BatchProcessor storage, custom func, and config-grid tests."""

import pytest

from tests.batch_processor_helpers import ConfigurableDataPlugin, SimpleDataPlugin
from waveform_analysis.core.context import Context
from waveform_analysis.core.data.batch_processor import BatchProcessor

pytestmark = pytest.mark.integration


class TestBatchProcessorStorage:
    def test_storage_strategy_shared(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        result = processor.process_runs(
            run_ids=["run_1", "run_2"],
            data_name="simple_data",
            max_workers=1,
            storage_dir_strategy="shared",
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 2

    def test_invalid_executor_type(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        with pytest.raises(ValueError, match="executor_type must be"):
            processor.process_runs(
                run_ids=["run_1"],
                data_name="simple_data",
                executor_type="invalid",
                show_progress=False,
                jupyter_mode=True,
            )

    def test_invalid_storage_strategy(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        with pytest.raises(ValueError, match="storage_dir_strategy must be"):
            processor.process_runs(
                run_ids=["run_1"],
                data_name="simple_data",
                storage_dir_strategy="invalid",
                show_progress=False,
                jupyter_mode=True,
            )


class TestBatchProcessorFunc:
    def test_process_func_serial(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        def custom_func(context, run_id):
            data = context.get_data(run_id, "simple_data")
            return data[0]["value"] * 10

        result = processor.process_func(
            run_ids=["run_1", "run_2", "run_3"],
            func=custom_func,
            max_workers=1,
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 3
        assert result["results"]["run_1"] == 10
        assert result["results"]["run_2"] == 20
        assert result["results"]["run_3"] == 30

    def test_process_func_parallel(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        def custom_func(context, run_id):
            data = context.get_data(run_id, "simple_data")
            return data[0]["value"] * 2

        result = processor.process_func(
            run_ids=["run_1", "run_2", "run_3", "run_4"],
            func=custom_func,
            max_workers=2,
            executor_type="thread",
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 4

    def test_process_func_with_error(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        processor = BatchProcessor(ctx)

        def failing_func(context, run_id):
            if run_id == "run_fail":
                raise ValueError("Custom failure")
            return run_id

        result = processor.process_func(
            run_ids=["run_1", "run_fail", "run_2"],
            func=failing_func,
            max_workers=1,
            on_error="continue",
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 2
        assert len(result["errors"]) == 1


class TestBatchProcessorConfigGrid:
    def test_config_grid_basic(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(ConfigurableDataPlugin)
        processor = BatchProcessor(ctx)

        configs = [{"multiplier": 1}, {"multiplier": 2}, {"multiplier": 3}]
        result = processor.process_runs_with_config_grid(
            run_ids=["run_1"],
            data_name="configurable_data",
            plugin_name="configurable_data",
            configs=configs,
            max_workers=1,
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 3
        assert result["configs"] == configs

        for i, config_result in enumerate(result["results"]):
            assert config_result["config_index"] == i
            assert len(config_result["batch"]["results"]) == 1

    def test_config_grid_multiple_runs(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(ConfigurableDataPlugin)
        processor = BatchProcessor(ctx)

        configs = [{"multiplier": 1}, {"multiplier": 10}]
        result = processor.process_runs_with_config_grid(
            run_ids=["run_1", "run_2"],
            data_name="configurable_data",
            plugin_name="configurable_data",
            configs=configs,
            max_workers=1,
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 2
        batch0 = result["results"][0]["batch"]
        assert batch0["results"]["run_1"][0]["value"] == 1
        assert batch0["results"]["run_2"][0]["value"] == 2

        batch1 = result["results"][1]["batch"]
        assert len(batch1["results"]) == 2
        assert batch1["results"]["run_1"][0]["value"] == 10
        assert batch1["results"]["run_2"][0]["value"] == 20
        assert batch1["meta"]["run_1"]["status"] == "success"
        assert batch1["meta"]["run_2"]["status"] == "success"

    @pytest.mark.parametrize("mode", ["serial", "thread", "process"])
    @pytest.mark.parametrize("explicit_factory", [False, True])
    def test_config_values_reach_each_worker(self, tmp_path, mode, explicit_factory):
        ctx = Context(storage_dir=str(tmp_path / "base"))
        ctx.register(ConfigurableDataPlugin)
        factory_ctx = Context(storage_dir=str(tmp_path / "factory"))
        factory_ctx.register(ConfigurableDataPlugin)
        factory_ctx.set_config({"multiplier": 11}, plugin_name="configurable_data")
        configs = [{"multiplier": 2}, {"multiplier": 7}, {}]

        result = BatchProcessor(ctx).process_runs_with_config_grid(
            ["run_1", "run_3"],
            "configurable_data",
            "configurable_data",
            configs,
            max_workers=1 if mode == "serial" else 2,
            executor_type="process" if mode == "process" else "thread",
            context_factory=factory_ctx.create_context_factory() if explicit_factory else None,
            show_progress=False,
            jupyter_mode=True,
        )

        assert result["configs"] == configs
        # The no-factory serial path updates the original Context cumulatively;
        # factories start from their captured configuration for every run.
        last_multiplier = 11 if explicit_factory else (7 if mode == "serial" else 1)
        for index, multiplier in enumerate((2, 7, last_multiplier)):
            item = result["results"][index]
            assert item["config_index"] == index
            assert item["config"] == configs[index]
            assert item["batch"]["errors"] == {}
            assert item["batch"]["ordered_run_ids"] == ["run_1", "run_3"]
            for run_id, base in (("run_1", 1), ("run_3", 3)):
                assert item["batch"]["results"][run_id][0]["value"] == base * multiplier

    def test_empty_config_grid_does_not_invoke_factory(self, tmp_path):
        def fail_factory():
            pytest.fail("Empty grid must not create a worker Context")

        result = BatchProcessor(Context(storage_dir=str(tmp_path))).process_runs_with_config_grid(
            ["run_1"],
            "configurable_data",
            "configurable_data",
            [],
            context_factory=fail_factory,
            show_progress=False,
        )
        assert result == {"configs": [], "results": []}
