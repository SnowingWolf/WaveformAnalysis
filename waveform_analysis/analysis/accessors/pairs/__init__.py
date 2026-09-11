"""S1-S2 pair Accessor responsibilities."""

from importlib import import_module

__all__ = ["S1S2PairAccessor"]


def __getattr__(name: str):
    if name == "S1S2PairAccessor":
        return getattr(import_module(".facade", __name__), name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
