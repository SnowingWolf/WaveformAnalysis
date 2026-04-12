"""Shared helpers for BatchProcessor tests."""

from __future__ import annotations

import time

import numpy as np

from waveform_analysis.core.plugins.core.base import Option, Plugin


class SimpleDataPlugin(Plugin):
    """Simple plugin that returns run_id based data."""

    provides = "simple_data"
    output_dtype = np.dtype([("value", "i4")])

    def compute(self, context, run_id, **kwargs):
        val = int(run_id.replace("run_", "")) if run_id.startswith("run_") else 1
        return np.array([(val,)], dtype=self.output_dtype)


class SlowPlugin(Plugin):
    """Plugin that takes time to compute."""

    provides = "slow_data"
    output_dtype = np.dtype([("value", "i4")])

    def compute(self, context, run_id, **kwargs):
        time.sleep(0.05)
        return np.array([(1,)], dtype=self.output_dtype)


class FailingPlugin(Plugin):
    """Plugin that always fails."""

    provides = "failing_data"
    output_dtype = np.dtype([("value", "i4")])

    def compute(self, context, run_id, **kwargs):
        raise ValueError(f"Intentional failure for {run_id}")


class ConditionalFailPlugin(Plugin):
    """Plugin that fails for specific run_ids."""

    provides = "conditional_data"
    output_dtype = np.dtype([("value", "i4")])

    def compute(self, context, run_id, **kwargs):
        if "fail" in run_id:
            raise ValueError(f"Failure for {run_id}")
        return np.array([(1,)], dtype=self.output_dtype)


class ConfigurableDataPlugin(Plugin):
    """Plugin with configurable multiplier."""

    provides = "configurable_data"
    options = {"multiplier": Option(default=1, type=int)}
    output_dtype = np.dtype([("value", "i4")])

    def compute(self, context, run_id, **kwargs):
        multiplier = context.get_config(self, "multiplier")
        base = int(run_id.replace("run_", "")) if run_id.startswith("run_") else 1
        return np.array([(base * multiplier,)], dtype=self.output_dtype)
