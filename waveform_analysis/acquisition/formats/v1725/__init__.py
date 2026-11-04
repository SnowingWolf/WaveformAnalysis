"""CAEN V1725 DAW_DEMO binary format and adapter."""

from .reader import (
    V1725_ADAPTER,
    V1725_LAYOUT,
    V1725_SPEC,
    V1725Adapter,
    V1725Reader,
    V1725Spec,
    V1725Wave,
)

# Preserve the serialization path used before the device became a package.
V1725Wave.__module__ = __name__

__all__ = [
    "V1725Wave",
    "V1725Reader",
    "V1725Spec",
    "V1725_SPEC",
    "V1725_LAYOUT",
    "V1725Adapter",
    "V1725_ADAPTER",
]
