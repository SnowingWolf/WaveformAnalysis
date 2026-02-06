#!/usr/bin/env python3
"""
Clear downstream cache entries for a given data type and run.

This script computes downstream plugins based on registered dependencies and
clears their caches (memory + disk) for a specific run_id.
"""

import argparse
from collections import deque
import sys
from typing import Dict, Iterable, List, Optional, Set

from waveform_analysis.core.context import Context
from waveform_analysis.core.plugins import profiles as plugin_profiles


def _build_context(
    data_root: Optional[str],
    storage_dir: Optional[str],
    profile: str,
    discover: bool,
    plugin_dirs: List[str],
) -> Context:
    config = {}
    if data_root:
        config["data_root"] = data_root

    ctx = Context(
        config=config or None,
        storage_dir=storage_dir,
        external_plugin_dirs=plugin_dirs or None,
        auto_discover_plugins=discover,
    )

    if not discover:
        try:
            profile_factory = plugin_profiles.get_profile(profile)
        except KeyError:
            available = ", ".join(sorted(plugin_profiles.PROFILES.keys()))
            raise ValueError(f"Unknown profile '{profile}'. Available: {available}")
        ctx.register(*profile_factory())

    return ctx


def _build_reverse_dependencies(ctx: Context, run_id: str) -> Dict[str, List[str]]:
    reverse: Dict[str, List[str]] = {}
    for name, plugin in ctx._plugins.items():
        deps = ctx._get_plugin_dependency_names(plugin, run_id=run_id)
        for dep in deps:
            reverse.setdefault(dep, []).append(name)
    return reverse


def _collect_downstream(reverse: Dict[str, List[str]], data_name: str) -> List[str]:
    seen: Set[str] = set()
    queue: deque = deque(reverse.get(data_name, []))
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        for child in reverse.get(node, []):
            queue.append(child)
    return list(seen)


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clear downstream cache entries for a given data type and run_id."
    )
    parser.add_argument("run_id", help="Target run_id")
    parser.add_argument("data_name", help="Data name with bad/changed data")
    parser.add_argument(
        "--profile",
        default="cpu_default",
        help="Plugin profile to register (default: cpu_default)",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Auto-discover plugins (ignores --profile)",
    )
    parser.add_argument(
        "--plugin-dir",
        action="append",
        default=[],
        help="Additional plugin directories (repeatable)",
    )
    parser.add_argument(
        "--data-root",
        default=None,
        help="Data root for cache storage (default: DAQ)",
    )
    parser.add_argument(
        "--storage-dir",
        default=None,
        help="Override storage directory (if set, overrides data_root)",
    )
    parser.add_argument(
        "--exclude-self",
        action="store_true",
        help="Do not clear cache for the target data_name itself",
    )
    parser.add_argument(
        "--memory-only",
        action="store_true",
        help="Only clear memory cache",
    )
    parser.add_argument(
        "--disk-only",
        action="store_true",
        help="Only clear disk cache",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show downstream targets without clearing caches",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output",
    )
    return parser.parse_args(argv)


def _resolve_clear_flags(args: argparse.Namespace) -> tuple:
    if args.memory_only and args.disk_only:
        raise ValueError("--memory-only and --disk-only cannot be used together")
    if args.memory_only:
        return True, False
    if args.disk_only:
        return False, True
    return True, True


def _print_targets(targets: Iterable[str], run_id: str, data_name: str) -> None:
    targets = list(targets)
    print(f"[Downstream] run_id={run_id}, data_name={data_name}")
    if not targets:
        print("  (no downstream targets)")
        return
    for name in sorted(targets):
        print(f"  - {name}")


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)

    try:
        clear_memory, clear_disk = _resolve_clear_flags(args)
    except ValueError as exc:
        print(f"[Error] {exc}")
        return 2

    try:
        ctx = _build_context(
            data_root=args.data_root,
            storage_dir=args.storage_dir,
            profile=args.profile,
            discover=args.discover,
            plugin_dirs=args.plugin_dir,
        )
    except ValueError as exc:
        print(f"[Error] {exc}")
        return 2

    reverse = _build_reverse_dependencies(ctx, run_id=args.run_id)

    if args.data_name not in reverse and args.data_name not in ctx._plugins:
        print(
            "[Error] data_name not found in plugin dependencies. "
            "Check profile/discovery settings."
        )
        return 2

    downstream = _collect_downstream(reverse, args.data_name)
    targets: List[str] = []
    if not args.exclude_self:
        targets.append(args.data_name)
    targets.extend(downstream)

    if args.verbose or args.dry_run:
        _print_targets(targets, args.run_id, args.data_name)

    if args.dry_run:
        print("[Dry-run] No cache cleared.")
        return 0

    total_cleared = 0
    for name in targets:
        cleared = ctx.clear_cache_for(
            args.run_id,
            name,
            clear_memory=clear_memory,
            clear_disk=clear_disk,
            verbose=False,
        )
        total_cleared += cleared
        if args.verbose:
            print(f"[Cleared] {name}: {cleared}")

    print(
        f"[Done] Cleared {total_cleared} cache entries "
        f"(memory={clear_memory}, disk={clear_disk})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
