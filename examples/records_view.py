# -*- coding: utf-8 -*-
"""Minimal records usage example."""

from waveform_analysis.core.context import Context
from waveform_analysis.core.data import records_view
from waveform_analysis.core.plugins.builtin.cpu import (
    RawFilesPlugin,
    RecordsPlugin,
    StWaveformsPlugin,
    WaveformsPlugin,
)


def main() -> None:
    run_id = "run_001"
    daq_adapter = "vx2730"  # TODO: set to your adapter name

    ctx = Context(config={"data_root": "DAQ", "n_channels": 2})
    ctx.register_plugin(RawFilesPlugin())
    ctx.register_plugin(WaveformsPlugin())
    ctx.register_plugin(StWaveformsPlugin())
    ctx.register_plugin(RecordsPlugin())

    # Required: set DAQ adapter (or pass daq_run/daq_info to get_raw_files)
    ctx.set_config({"daq_adapter": daq_adapter})

    # Optional: set dt (ns) if not provided by the adapter
    # ctx.set_config({"records_dt_ns": 2}, plugin_name="records")

    records = ctx.get_data(run_id, "records")
    print(f"records={len(records)}")

    rv = records_view(ctx, run_id)
    wave0 = rv.wave(0, baseline_correct=True)
    print("wave0 head:", wave0[:10])

    subset = rv.query_time_window(t_min=0, t_max=1_000_000)
    print(f"subset={len(subset)}")


if __name__ == "__main__":
    main()
