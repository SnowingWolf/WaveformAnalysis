"""
Cache analysis plugin.

Collects cache statistics and optionally returns filtered cache entries and
diagnostic issues. This is meant for interactive inspection and does not
write to the main cache by default.
"""

import csv
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from waveform_analysis.core.foundation.utils import exporter
from waveform_analysis.core.plugins.core.base import Option, Plugin
from waveform_analysis.core.storage.cache_analyzer import CacheAnalyzer, CacheEntry
from waveform_analysis.core.storage.cache_diagnostics import CacheDiagnostics, DiagnosticIssue
from waveform_analysis.core.storage.cache_statistics import CacheStatsCollector

export, __all__ = exporter()

# Fields for CSV export of cache entries
_ENTRY_FIELDS = [
    "run_id",
    "data_name",
    "key",
    "size_bytes",
    "size_human",
    "age_days",
    "created_at",
    "created_at_str",
    "plugin_version",
    "dtype_str",
    "count",
    "compressed",
    "has_checksum",
    "file_path",
    "metadata",
]


def _entry_to_dict(entry: CacheEntry, include_metadata: bool) -> Dict[str, Any]:
    result = {
        "run_id": entry.run_id,
        "data_name": entry.data_name,
        "key": entry.key,
        "size_bytes": entry.size_bytes,
        "size_human": entry.size_human,
        "age_days": entry.age_days,
        "created_at": entry.created_at,
        "created_at_str": entry.created_at_str,
        "plugin_version": entry.plugin_version,
        "dtype_str": entry.dtype_str,
        "count": entry.count,
        "compressed": entry.compressed,
        "has_checksum": entry.has_checksum,
        "file_path": entry.file_path,
    }
    if include_metadata:
        result["metadata"] = entry.metadata
    else:
        result["metadata"] = None
    return result


def _issue_to_dict(issue: DiagnosticIssue) -> Dict[str, Any]:
    return {
        "issue_type": issue.issue_type.value,
        "severity": issue.severity,
        "run_id": issue.run_id,
        "data_name": issue.data_name,
        "key": issue.key,
        "description": issue.description,
        "details": issue.details,
        "fixable": issue.fixable,
        "fix_action": issue.fix_action,
    }


def _resolve_export_target(
    export_path: Optional[str],
    export_format: Optional[str],
    export_name: str,
    output_dir: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    if export_path:
        fmt = export_format
        lower_path = export_path.lower()
        if lower_path.endswith(".json"):
            fmt = "json"
        elif lower_path.endswith(".csv"):
            fmt = "csv"
        if fmt is None:
            fmt = "json"
        return export_path, fmt

    if export_format is None:
        return None, None

    fmt = export_format.lower()
    if fmt not in ("json", "csv"):
        raise ValueError(f"Unsupported export_format '{export_format}'. Use 'json' or 'csv'.")

    base_dir = output_dir or os.getcwd()
    return os.path.join(base_dir, f"{export_name}.{fmt}"), fmt


def _export_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True, sort_keys=True)


def _export_csv(path: str, entries: List[Dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_ENTRY_FIELDS)
        writer.writeheader()
        for entry in entries:
            row = dict(entry)
            if row.get("metadata") is not None:
                row["metadata"] = json.dumps(row["metadata"], ensure_ascii=True, sort_keys=True)
            writer.writerow(row)


@export
class CacheAnalysisPlugin(Plugin):
    """Analyze cache usage and return a structured report."""

    provides = "cache_analysis"
    description = "Analyze cache usage and return summary, entries, and diagnostics."
    version = "0.1.0"
    save_when = "never"
    is_side_effect = True

    options = {
        "scan_all_runs": Option(
            default=False,
            type=bool,
            help="Scan all runs instead of only the requested run_id.",
        ),
        "data_name": Option(
            default=None,
            type=str,
            help="Optional data name filter for cache entries.",
        ),
        "min_size_bytes": Option(
            default=None,
            type=int,
            help="Minimum cache entry size in bytes for filtering.",
        ),
        "max_size_bytes": Option(
            default=None,
            type=int,
            help="Maximum cache entry size in bytes for filtering.",
        ),
        "min_age_days": Option(
            default=None,
            type=float,
            help="Minimum cache entry age in days for filtering.",
        ),
        "max_age_days": Option(
            default=None,
            type=float,
            help="Maximum cache entry age in days for filtering.",
        ),
        "compressed_only": Option(
            default=None,
            type=bool,
            help="Filter entries by compression state (True/False).",
        ),
        "include_entries": Option(
            default=True,
            type=bool,
            help="Include per-entry details in the result payload.",
        ),
        "max_entries": Option(
            default=None,
            type=int,
            help="Limit the number of entries returned (largest by size).",
        ),
        "include_metadata": Option(
            default=False,
            type=bool,
            help="Include full metadata dict for each cache entry.",
        ),
        "include_diagnostics": Option(
            default=False,
            type=bool,
            help="Run cache diagnostics and include issue list.",
        ),
        "export_format": Option(
            default=None,
            type=str,
            help="Export report to output_dir as 'json' or 'csv'.",
        ),
        "export_name": Option(
            default="cache_analysis",
            type=str,
            help="Base filename for exported report.",
        ),
        "export_path": Option(
            default=None,
            type=str,
            help="Explicit export path. Overrides export_name/output_dir.",
        ),
        "verbose": Option(
            default=False,
            type=bool,
            help="Print scan and diagnostic progress.",
        ),
    }

    def compute(self, context: Any, run_id: str, **kwargs) -> Dict[str, Any]:
        scan_all_runs = context.get_config(self, "scan_all_runs")
        data_name = context.get_config(self, "data_name")
        min_size_bytes = context.get_config(self, "min_size_bytes")
        max_size_bytes = context.get_config(self, "max_size_bytes")
        min_age_days = context.get_config(self, "min_age_days")
        max_age_days = context.get_config(self, "max_age_days")
        compressed_only = context.get_config(self, "compressed_only")
        include_entries = context.get_config(self, "include_entries")
        max_entries = context.get_config(self, "max_entries")
        include_metadata = context.get_config(self, "include_metadata")
        include_diagnostics = context.get_config(self, "include_diagnostics")
        export_format = context.get_config(self, "export_format")
        export_name = context.get_config(self, "export_name")
        export_path = context.get_config(self, "export_path")
        verbose = context.get_config(self, "verbose")

        output_dir = kwargs.get("output_dir")
        target_run_id = None if scan_all_runs else run_id

        analyzer = CacheAnalyzer(context)
        run_ids = None if target_run_id is None else [target_run_id]
        analyzer.scan(verbose=verbose, run_ids=run_ids)

        collector = CacheStatsCollector(analyzer)
        stats = collector.collect(run_id=target_run_id)

        result: Dict[str, Any] = {
            "run_id": target_run_id or "all",
            "summary": stats.to_dict(),
        }

        entries: List[Dict[str, Any]] = []
        if include_entries:
            raw_entries = analyzer.get_entries(
                run_id=target_run_id,
                data_name=data_name,
                min_size=min_size_bytes,
                max_size=max_size_bytes,
                min_age_days=min_age_days,
                max_age_days=max_age_days,
                compressed_only=compressed_only,
            )
            if max_entries is not None and max_entries > 0:
                raw_entries = sorted(raw_entries, key=lambda e: e.size_bytes, reverse=True)[
                    :max_entries
                ]
            entries = [_entry_to_dict(entry, include_metadata) for entry in raw_entries]
            result["entries"] = entries

        if include_diagnostics:
            diagnostics = CacheDiagnostics(analyzer)
            issues = diagnostics.diagnose(run_id=target_run_id, verbose=verbose)
            result["diagnostics"] = [_issue_to_dict(issue) for issue in issues]

        export_target, export_kind = _resolve_export_target(
            export_path=export_path,
            export_format=export_format,
            export_name=export_name,
            output_dir=output_dir,
        )
        if export_target and export_kind:
            if export_kind == "json":
                _export_json(export_target, result)
            elif export_kind == "csv":
                _export_csv(export_target, entries)

        return result
