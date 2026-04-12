"""Basic BatchProcessor execution tests."""

import pytest

from tests.batch_processor_helpers import SimpleDataPlugin
from waveform_analysis.core.context import Context
from waveform_analysis.core.data.batch_processor import BatchProcessor

pytestmark = pytest.mark.integration


class TestBatchProcessorBasic:
    def test_process_runs_serial_success(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        result = processor.process_runs(
            run_ids=["run_1", "run_2", "run_3"],
            data_name="simple_data",
            max_workers=1,
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 3
        assert len(result["errors"]) == 0
        assert result["results"]["run_1"][0]["value"] == 1
        assert result["results"]["run_2"][0]["value"] == 2
        assert result["results"]["run_3"][0]["value"] == 3
        assert all(m["status"] == "success" for m in result["meta"].values())

    def test_process_runs_empty_list(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        result = processor.process_runs(
            run_ids=[],
            data_name="simple_data",
            max_workers=1,
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 0
        assert len(result["errors"]) == 0

    def test_process_runs_single_run(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        result = processor.process_runs(
            run_ids=["run_42"],
            data_name="simple_data",
            max_workers=1,
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 1
        assert result["results"]["run_42"][0]["value"] == 42

    def test_process_runs_parallel_thread(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        result = processor.process_runs(
            run_ids=["run_1", "run_2", "run_3", "run_4"],
            data_name="simple_data",
            max_workers=2,
            executor_type="thread",
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 4
        assert len(result["errors"]) == 0

    def test_process_runs_ordered_run_ids(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        run_ids = ["run_3", "run_1", "run_2"]
        result = processor.process_runs(
            run_ids=run_ids,
            data_name="simple_data",
            max_workers=1,
            show_progress=False,
            jupyter_mode=True,
        )

        assert result["ordered_run_ids"] == run_ids
