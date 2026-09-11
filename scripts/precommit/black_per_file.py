#!/usr/bin/env python3
"""
Run black one file at a time.

Workaround for environments where a single black invocation with multiple files
may hang during process exit.
"""

import subprocess
import sys


def _split_args(argv: list[str]) -> tuple[list[str], list[str]]:
    black_args: list[str] = []
    files: list[str] = []
    for token in argv:
        if token.startswith("-"):
            black_args.append(token)
        else:
            files.append(token)
    return black_args, files


def main() -> int:
    black_args, files = _split_args(sys.argv[1:])
    base_cmd = [sys.executable, "-m", "black"] + black_args

    if not files:
        return subprocess.run(base_cmd).returncode

    for file_path in files:
        result = subprocess.run(base_cmd + [file_path])
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
