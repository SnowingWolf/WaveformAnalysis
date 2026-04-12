"""BatchProcessor cancellation and meta tests."""

import threading
import time

import pytest

from tests.batch_processor_helpers import SimpleDataPlugin, SlowPlugin
from waveform_analysis.core.cancellation import CancellationToken
from waveform_analysis.core.context import Context
from waveform_analysis.core.data.batch_processor import BatchProcessor

pytestmark = pytest.mark.integration


class TestBatchProcessorCancellation:
    def test_cancellation_skips_remaining(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SlowPlugin)
        processor = BatchProcessor(ctx)

        cancellation_token = CancellationToken()

        def cancel_soon():
            time.sleep(0.02)
            cancellation_token.cancel()

        thread = threading.Thread(target=cancel_soon)
        thread.start()

        result = processor.process_runs(
            run_ids=["run_1", "run_2", "run_3"],
            data_name="slow_data",
            max_workers=1,
            show_progress=False,
            cancellation_token=cancellation_token,
            jupyter_mode=True,
        )

        thread.join()

        assert result["meta"]["run_1"]["status"] == "success"
        skipped_count = sum(1 for m in result["meta"].values() if m["status"] == "skipped")
        assert skipped_count >= 1


class TestBatchProcessorMeta:
    def test_meta_contains_elapsed_time(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        result = processor.process_runs(
            run_ids=["run_1"],
            data_name="simple_data",
            max_workers=1,
            show_progress=False,
            jupyter_mode=True,
        )

        assert "elapsed" in result["meta"]["run_1"]
        assert result["meta"]["run_1"]["elapsed"] >= 0

    def test_meta_contains_attempts(self, tmp_path):
        ctx = Context(storage_dir=str(tmp_path))
        ctx.register(SimpleDataPlugin)
        processor = BatchProcessor(ctx)

        result = processor.process_runs(
            run_ids=["run_1"],
            data_name="simple_data",
            max_workers=1,
            show_progress=False,
            jupyter_mode=True,
        )

        assert "attempts" in result["meta"]["run_1"]
        assert result["meta"]["run_1"]["attempts"] == 1
