"""Compatibility aliases for generic file I/O."""

import sys

from waveform_analysis._module_aliases import alias_module, register_module_aliases

register_module_aliases(
    {
        "waveform_analysis.acquisition.readers.base_csv": "waveform_analysis.acquisition.file_io.csv_pandas",
        "waveform_analysis.acquisition.readers.polars_backend": "waveform_analysis.acquisition.file_io.csv_polars",
        "waveform_analysis.acquisition.readers.pyarrow_backend": "waveform_analysis.acquisition.file_io.csv_pyarrow",
        "waveform_analysis.acquisition.readers.orchestrator": "waveform_analysis.acquisition.file_io.orchestration",
    }
)
sys.modules[__name__] = alias_module(__name__, "waveform_analysis.acquisition.file_io")
