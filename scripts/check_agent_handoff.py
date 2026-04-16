#!/usr/bin/env python3
"""Validate that agent handoff explicitly handles pending git changes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class StatusSummary:
    staged: int
    unstaged: int
    untracked: int

    @property
    def total(self) -> int:
        return self.staged + self.unstaged + self.untracked

    @property
    def clean(self) -> bool:
        return self.total == 0


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def get_status_lines(ignore_untracked: bool = False) -> list[str]:
    cmd = ["git", "status", "--short"]
    if ignore_untracked:
        cmd.append("--untracked-files=no")
    rc, out, err = _run(cmd)
    if rc != 0:
        raise RuntimeError(f"git status failed: {err.strip()}")
    return [line.rstrip() for line in out.splitlines() if line.strip()]


def summarize_status(lines: list[str]) -> StatusSummary:
    staged = 0
    unstaged = 0
    untracked = 0

    for line in lines:
        if line.startswith("??"):
            untracked += 1
            continue

        index_flag = line[0]
        worktree_flag = line[1] if len(line) > 1 else " "
        if index_flag != " ":
            staged += 1
        if worktree_flag != " ":
            unstaged += 1

    return StatusSummary(staged=staged, unstaged=unstaged, untracked=untracked)


def get_diff_stat(*, cached: bool = False) -> str:
    cmd = ["git", "diff", "--stat"]
    if cached:
        cmd.insert(2, "--cached")
    rc, out, err = _run(cmd)
    if rc != 0:
        raise RuntimeError(f"git diff --stat failed: {err.strip()}")
    return out.strip()


def evaluate_handoff(
    lines: list[str],
    *,
    allow_uncommitted: bool = False,
    reason: str | None = None,
) -> tuple[int, str]:
    summary = summarize_status(lines)

    if summary.clean:
        return 0, "PASS: 工作树干净，可以记录为 `已提交` 或 `无待提交改动`。"

    if allow_uncommitted:
        if not reason or not reason.strip():
            return 2, "ERROR: 使用 `--allow-uncommitted` 时必须提供非空 `--reason`。"
        return (
            0,
            "PASS: 存在未提交改动，但已显式声明原因。"
            f" 建议在最终回复中写 `未提交：{reason.strip()}`。",
        )

    return (
        1,
        "FAIL: 检测到未提交改动。请先提交，或使用 "
        '`--allow-uncommitted --reason "<原因>"` 显式声明未提交状态。',
    )


def _print_summary(lines: list[str]) -> None:
    summary = summarize_status(lines)
    print("=== agent handoff status ===")
    print(f"staged: {summary.staged}, unstaged: {summary.unstaged}, untracked: {summary.untracked}")

    if not lines:
        return

    print()
    print("pending changes:")
    for line in lines:
        print(f"  {line}")

    staged_stat = get_diff_stat(cached=True)
    unstaged_stat = get_diff_stat(cached=False)

    if staged_stat:
        print()
        print("staged diff stat:")
        print(staged_stat)
    if unstaged_stat:
        print()
        print("unstaged diff stat:")
        print(unstaged_stat)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether agent handoff handles commit state")
    parser.add_argument(
        "--allow-uncommitted",
        action="store_true",
        help="Allow pending changes only when an explicit reason is provided",
    )
    parser.add_argument(
        "--reason",
        default=None,
        help="Reason for leaving changes uncommitted; required with --allow-uncommitted",
    )
    parser.add_argument(
        "--ignore-untracked",
        action="store_true",
        help="Ignore untracked files when evaluating pending changes",
    )
    args = parser.parse_args()

    try:
        lines = get_status_lines(ignore_untracked=args.ignore_untracked)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    code, message = evaluate_handoff(
        lines,
        allow_uncommitted=args.allow_uncommitted,
        reason=args.reason,
    )
    _print_summary(lines)
    print()
    print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
