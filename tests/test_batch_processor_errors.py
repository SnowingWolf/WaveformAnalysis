"""BatchProcessor error handling tests."""

import pytest

from tests.batch_processor_helpers import ConditionalFailPlugin, FailingPlugin, SimpleDataPlugin
from waveform_analysis.core.context import Context
from waveform_analysis.core.data.batch_processor import BatchProcessor

pytestmark = pytest.mark.integration


class TestBatchProcessorErrorHandling:
    def test_error_handling_continue(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(ConditionalFailPlugin)
        processor = BatchProcessor(ctx)

        result = processor.process_runs(
            run_ids=["run_ok1", "run_fail", "run_ok2"],
            data_name="conditional_data",
            max_workers=1,
            on_error="continue",
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 2
        assert len(result["errors"]) == 1
        assert "run_fail" in result["errors"]
        assert result["meta"]["run_ok1"]["status"] == "success"
        assert result["meta"]["run_fail"]["status"] == "failed"
        assert result["meta"]["run_ok2"]["status"] == "success"

    def test_error_handling_stop(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(ConditionalFailPlugin)
        processor = BatchProcessor(ctx)

        result = processor.process_runs(
            run_ids=["run_ok1", "run_fail", "run_ok2"],
            data_name="conditional_data",
            max_workers=1,
            on_error="stop",
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 1
        assert "run_ok1" in result["results"]
        assert result["meta"]["run_fail"]["status"] == "failed"
        assert result["meta"]["run_ok2"]["status"] == "skipped"

    def test_error_handling_raise(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(FailingPlugin)
        processor = BatchProcessor(ctx)

        with pytest.raises(RuntimeError):
            processor.process_runs(
                run_ids=["run_1"],
                data_name="failing_data",
                max_workers=1,
                on_error="raise",
                show_progress=False,
                jupyter_mode=True,
            )

    def test_retry_mechanism(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        attempt_counts = {}

        def retryable_func(context, run_id):
            if run_id not in attempt_counts:
                attempt_counts[run_id] = 0
            attempt_counts[run_id] += 1
            if attempt_counts[run_id] < 2:
                raise OSError(f"Transient failure for {run_id}")
            return context.get_data(run_id, "simple_data")

        result = processor.process_func(
            run_ids=["run_1"],
            func=retryable_func,
            max_workers=1,
            retries=2,
            retry_on=(IOError,),
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 1
        assert result["meta"]["run_1"]["status"] == "success"
        assert result["meta"]["run_1"]["attempts"] == 2

    def test_mixed_success_failure(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(ConditionalFailPlugin)
        processor = BatchProcessor(ctx)

        result = processor.process_runs(
            run_ids=["run_1", "run_fail1", "run_2", "run_fail2", "run_3"],
            data_name="conditional_data",
            max_workers=1,
            on_error="continue",
            show_progress=False,
            jupyter_mode=True,
        )

        assert len(result["results"]) == 3
        assert len(result["errors"]) == 2
