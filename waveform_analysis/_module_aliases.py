"""Identity-preserving import aliases for compatibility package trees."""

from __future__ import annotations

from importlib import import_module
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
import sys
from threading import RLock

_ALIASES: dict[str, str] = {}
_LOCK = RLock()


class _AliasLoader(Loader):
    def __init__(self, canonical_name: str):
        self.canonical_name = canonical_name
        self._canonical_metadata: dict[str, object] = {}

    def create_module(self, _spec: ModuleSpec):
        module = import_module(self.canonical_name)
        self._canonical_metadata = {
            name: getattr(module, name)
            for name in ("__name__", "__loader__", "__package__", "__spec__")
        }
        return module

    def exec_module(self, module) -> None:
        for name, value in self._canonical_metadata.items():
            setattr(module, name, value)


class _AliasFinder(MetaPathFinder):
    def find_spec(self, fullname: str, _path=None, _target=None):
        canonical_name = _ALIASES.get(fullname)
        if canonical_name is None or fullname in sys.modules:
            return None
        return ModuleSpec(fullname, _AliasLoader(canonical_name))


_FINDER = _AliasFinder()


def register_module_aliases(aliases: dict[str, str]) -> None:
    """Register lazy aliases without importing the canonical child modules."""
    with _LOCK:
        for legacy_name, canonical_name in aliases.items():
            existing = _ALIASES.get(legacy_name)
            if existing is not None and existing != canonical_name:
                raise RuntimeError(
                    f"Module alias {legacy_name!r} already targets {existing!r}, "
                    f"not {canonical_name!r}"
                )
            _ALIASES[legacy_name] = canonical_name
        if _FINDER not in sys.meta_path:
            sys.meta_path.insert(0, _FINDER)


def alias_module(legacy_name: str, canonical_name: str):
    """Return the canonical module and publish it under ``legacy_name``."""
    register_module_aliases({legacy_name: canonical_name})
    module = import_module(canonical_name)
    sys.modules[legacy_name] = module
    return module
