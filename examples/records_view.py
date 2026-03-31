"""Minimal events usage example."""

from waveform_analysis.core.context import Context
from waveform_analysis.core.data import records_view
from waveform_analysis.core.plugins.builtin.cpu import (
    EventFramePlugin,
    EventsPlugin,
    RawFilesPlugin,
    WaveformsPlugin,
)


def main() -> None:
    run_id = "run_001"
    daq_adapter = "vx2730"  # TODO: set to your adapter name

    ctx = Context(config={"data_root": "DAQ", "n_channels": 2})
    ctx.register(RawFilesPlugin())
    ctx.register(WaveformsPlugin())
    ctx.register(EventsPlugin())
    ctx.register(EventFramePlugin())

    # Required: set DAQ adapter (or pass daq_run/daq_info to get_raw_files)
    ctx.set_config({"daq_adapter": daq_adapter})

    # Optional: set dt (ns) explicitly on the upstream waveform/records plugin if needed
    # ctx.set_config({"dt": 2}, plugin_name="waveforms")

    events = ctx.get_data(run_id, "events")
    print(f"events={len(events)}")

    rv = records_view(ctx, run_id)
    first_record_id = int(rv.records[0]["record_id"])

    wave0 = rv.waves(first_record_id, baseline_correct=True)
    signal0 = rv.signals(first_record_id, sample_start=0, sample_end=10)

    print("record_id=", first_record_id)
    print("wave0 head:", wave0[:10])
    print("signal0 head:", signal0[:10])

    subset = rv.query_time_window(t_min=0, t_max=1_000_000)
    print(f"subset={len(subset)}")


if __name__ == "__main__":
    main()
