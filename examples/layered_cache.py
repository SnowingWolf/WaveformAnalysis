"""Publish synthetic records once and run two independent analyses.

Run: python examples/layered_cache.py --output-dir /path/to/new-directory
This example uses only synthetic integers, not DAQ data or a real run.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins.core.base import Option, Plugin

RUN = "synthetic_run"
DTYPE = np.dtype([("value", "i4")])
CALLS = []


class Records(Plugin):
    provides = "records"
    options = {"records_scale": Option(default=1, type=int)}
    output_dtype = DTYPE
    save_when = "always"
    version = "1.0.0"

    def compute(self, context, run_id, **kwargs):
        CALLS.append(self.provides)
        scale = context.get_config(self, "records_scale")
        return np.array([(2 * scale,), (4 * scale,)], dtype=DTYPE)


class WavePool(Plugin):
    provides = "wave_pool"
    depends_on = ["records"]
    output_dtype = DTYPE
    save_when = "always"
    version = "1.0.0"

    def compute(self, context, run_id, **kwargs):
        CALLS.append(self.provides)
        return context.get_data(run_id, "records").copy()


class Analysis(Plugin):
    provides = "synthetic_analysis"
    depends_on = ["wave_pool"]
    options = {"scale": Option(default=1, type=int)}
    output_dtype = DTYPE
    save_when = "always"
    version = "1.0.0"

    def compute(self, context, run_id, **kwargs):
        CALLS.append(self.provides)
        result = context.get_data(run_id, "wave_pool").copy()
        result["value"] *= context.get_config(self, "scale")
        return result


def make_context(storage, *, base=None, scale=1):
    kwargs = {"base": str(base)} if base is not None else {}
    ctx = Context(
        storage_dir=str(storage), config={"scale": scale, "show_progress": False}, **kwargs
    )
    ctx.register(Records, WavePool, Analysis)
    return ctx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="new directory for the synthetic caches and report",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    root = args.output_dir.resolve()
    producer = make_context(root / "producer")
    producer.get_data(RUN, "wave_pool")
    base = root / "published_v1"
    producer.publish(RUN, targets=["records", "wave_pool"], destination=str(base))
    CALLS.clear()
    consumers = [
        make_context(root / f"private_{scale}", base=base, scale=scale) for scale in (2, 3)
    ]
    layers = [ctx.get_data(RUN, "wave_pool") for ctx in consumers]
    assert all(isinstance(layer, np.memmap) and not layer.flags.writeable for layer in layers)
    assert Path(layers[0].filename).samefile(Path(layers[1].filename))
    results = {
        str(scale): ctx.get_data(RUN, "synthetic_analysis")["value"].tolist()
        for scale, ctx in zip((2, 3), consumers, strict=False)
    }
    assert results == {"2": [4, 8], "3": [6, 12]}
    assert CALLS == ["synthetic_analysis", "synthetic_analysis"]
    private_files = {
        str(scale): {
            str(path.relative_to(root / f"private_{scale}")): path.stat().st_size
            for path in (root / f"private_{scale}").rglob("*.bin")
        }
        for scale in (2, 3)
    }
    assert all(
        len(files) == 1 and "synthetic_analysis" in next(iter(files))
        for files in private_files.values()
    )
    changed = make_context(root / "private_changed", base=base)
    changed.set_config({"records_scale": 2})
    try:
        changed.get_data(RUN, "synthetic_analysis")
    except ValueError as exc:
        rejected_low_change = str(exc)
    else:
        raise AssertionError("changed records configuration was accepted")
    try:
        producer.publish(RUN, targets="records", destination=str(base))
    except FileExistsError:
        existing_destination_rejected = True
    else:
        raise AssertionError("existing published destination was overwritten")
    next_base = root / "published_v2"
    consumers[0].publish(RUN, targets="synthetic_analysis", destination=str(next_base))
    next_consumer = make_context(root / "private_v2", base=next_base, scale=2)
    next_layer = next_consumer.get_data(RUN, "wave_pool")
    same_inode = Path(layers[0].filename).samefile(Path(next_layer.filename))
    assert same_inode
    new_shared_analysis = next_consumer.get_data(RUN, "synthetic_analysis")
    assert isinstance(new_shared_analysis, np.memmap) and not new_shared_analysis.flags.writeable
    assert new_shared_analysis["value"].tolist() == [4, 8]
    assert not list((root / "private_v2").rglob("*.bin"))
    old_still_readable = consumers[1].get_data(RUN, "wave_pool")["value"].tolist()
    assert old_still_readable == [2, 4]
    assert CALLS == ["synthetic_analysis", "synthetic_analysis"]
    result = {
        "input": "synthetic integers; no detector data",
        "run_id": RUN,
        "shared_payload_readonly": True,
        "higher_level_results_by_scale": results,
        "lower_level_config_rejected": rejected_low_change,
        "lower_level_computations_by_consumers": 0,
        "private_bin_files_and_bytes": private_files,
        "existing_destination_rejected": existing_destination_rejected,
        "v2_reuses_v1_payload_inode": same_inode,
        "v2_shared_new_analysis": new_shared_analysis["value"].tolist(),
        "v2_consumer_private_bin_files": 0,
        "v1_values_after_v2_publish": old_still_readable,
    }
    report = json.dumps(result, ensure_ascii=False, indent=2)
    (root / "report.json").write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"Report and caches: {root}")


if __name__ == "__main__":
    main()
