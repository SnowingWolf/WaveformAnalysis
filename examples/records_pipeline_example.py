"""Records、基础特征及按 record_id 访问波形的示例。"""

import pandas as pd

from waveform_analysis import Context
from waveform_analysis.core.data import records_view
from waveform_analysis.plugins import (
    BasicFeaturesPlugin,
    RawFileNamesPlugin,
    RecordsPlugin,
    WaveformsPlugin,
    WavePoolPlugin,
)


def main() -> None:
    run_id = "run_001"
    daq_adapter = "vx2730"  # TODO: set to your adapter name

    ctx = Context(
        config={
            "data_root": "DAQ",
            "n_channels": 2,
            "show_progress": True,
        }
    )
    ctx.register(RawFileNamesPlugin())
    ctx.register(WaveformsPlugin())
    ctx.register(RecordsPlugin())
    ctx.register(WavePoolPlugin())
    ctx.register(BasicFeaturesPlugin())

    # Required: set DAQ adapter (or pass daq_run/daq_info to get_raw_files)
    ctx.set_config({"daq_adapter": daq_adapter})

    # Optional: set dt (ns) explicitly for records if not provided by the adapter
    # ctx.set_config({"dt": 2}, plugin_name="records")
    # basic_features has one row per record, not one row per multi-channel event.

    records = ctx.get_data(run_id, "records")
    print(f"records={len(records)}")

    features = ctx.get_data(run_id, "basic_features")
    df = pd.DataFrame(features)
    print(f"basic_features records={len(df)}")
    print(df.head())

    if len(records) == 0:
        return

    rv = records_view(ctx, run_id)
    first_record_id = int(records[0]["record_id"])

    wave0 = rv.waves(first_record_id, baseline_correct=True)
    signal0 = rv.signals(first_record_id, sample_start=0, sample_end=10)

    print("record_id=", first_record_id)
    print("wave0 head:", wave0[:10])
    print("signal0 head:", signal0[:10])

    subset = rv.query_time_window(t_min=0, t_max=1_000_000)
    print(f"subset={len(subset)}")


if __name__ == "__main__":
    main()
