"""Peak-channel Accessor responsibilities."""

from importlib import import_module

__all__ = ["PeakChannelAccessor"]


def __getattr__(name: str):
    if name == "PeakChannelAccessor":
        return getattr(import_module(".facade", __name__), name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
