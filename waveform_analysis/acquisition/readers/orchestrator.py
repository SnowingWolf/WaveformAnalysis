"""Unified acquisition parsing orchestration entry point."""

from functools import wraps


def _implementation():
    from ..io import _parse_and_stack_files_impl

    return _parse_and_stack_files_impl


@wraps(_implementation())
def parse_and_stack_files(*args, **kwargs):
    return _implementation()(*args, **kwargs)


__all__ = ["parse_and_stack_files"]
