"""Negative coverage for the records-backed schema smoke gate."""

from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import pytest


@pytest.fixture
def checker(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from scripts import schema_compat_check

    return schema_compat_check


@pytest.fixture
def smoke_summary(checker):
    return {
        "run_id": "run_smoke_001",
        "raw_file_groups": 2,
        "products": {
            target: {"count": 1, "fields": deepcopy(checker.REQUIRED_FIELDS.get(target, {}))}
            for target in checker.SMOKE_TARGETS
        },
    }


@pytest.mark.parametrize("target", ["records", "hit_threshold", "peaklet_waveforms", "peaks"])
def test_schema_gate_rejects_empty_smoke_product(checker, smoke_summary, monkeypatch, target):
    smoke_summary["products"][target]["count"] = 0
    monkeypatch.setattr(checker, "run_smoke_chain", lambda: smoke_summary)
    monkeypatch.setattr(checker, "_changed_python_files", lambda *args, **kwargs: [])
    monkeypatch.setattr(sys, "argv", ["schema_compat_check.py", "--run-smoke"])

    assert checker.main() == 1


@pytest.mark.parametrize(
    ("target", "field", "bad_type"),
    [("records", "board", None), ("hit_threshold", "record_id", "int32"), ("peaks", "area", None)],
)
def test_schema_gate_rejects_missing_or_changed_fields(
    checker, smoke_summary, monkeypatch, target, field, bad_type
):
    fields = smoke_summary["products"][target]["fields"]
    if bad_type is None:
        del fields[field]
    else:
        fields[field] = bad_type
    monkeypatch.setattr(checker, "run_smoke_chain", lambda: smoke_summary)
    monkeypatch.setattr(checker, "_changed_python_files", lambda *args, **kwargs: [])
    monkeypatch.setattr(sys, "argv", ["schema_compat_check.py", "--run-smoke"])

    assert checker.main() == 1


def test_schema_gate_rejects_changed_declared_record_dtype(checker, monkeypatch):
    from waveform_analysis.core.plugins.builtin.records import RecordsPlugin

    dtype = np.dtype(
        [
            (name, "i4" if name == "record_id" else dt)
            for name, dt in RecordsPlugin.output_dtype.descr
        ]
    )
    monkeypatch.setattr(RecordsPlugin, "output_dtype", dtype)

    assert any(
        "records.record_id 类型不匹配" in issue for issue in checker._check_runtime_contracts()
    )


def test_schema_gate_rejects_smoke_execution_failure(checker, monkeypatch):
    def fail_smoke():
        raise ValueError("malformed records input")

    monkeypatch.setattr(checker, "run_smoke_chain", fail_smoke)
    monkeypatch.setattr(checker, "_changed_python_files", lambda *args, **kwargs: [])
    monkeypatch.setattr(sys, "argv", ["schema_compat_check.py", "--run-smoke"])

    assert checker.main() == 1


def test_benchmark_rejects_empty_output(monkeypatch):
    from scripts import _quality_common

    class EmptyContext:
        def get_data(self, run_id, target):
            return np.zeros(0)

    monkeypatch.setattr(_quality_common, "_build_context", lambda **kwargs: EmptyContext())

    with pytest.raises(ValueError, match="empty benchmark output for peaks"):
        _quality_common.benchmark_hot_targets(["peaks"], repeats=1)
