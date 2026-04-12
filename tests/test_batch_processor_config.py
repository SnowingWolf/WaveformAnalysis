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
        assert batch1["meta"]["run_1"]["status"] == "success"
        assert batch1["meta"]["run_2"]["status"] == "success"
