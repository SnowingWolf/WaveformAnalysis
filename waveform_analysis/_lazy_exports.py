"""Small standard-library helpers for module-level lazy exports.

The helper deliberately does not know anything about WaveformAnalysis.  A
module supplies a mapping from public names to ``(module, attribute)`` pairs;
the target is imported only when that public name is requested.
"""

from collections.abc import Mapping, MutableMapping, Sequence
from importlib import import_module
import sys
from types import ModuleType

LazyExport = tuple[str, str | None]

__all__ = ["LazyExport", "lazy_dir", "resolve_lazy_attribute"]


_MISSING = object()


class _LazyExportModule(ModuleType):
    """Keep a lazy symbol from being shadowed by a same-named submodule.

    Python assigns every imported child module to its parent package.  A
    package that historically exported a function with the same name as a
    child module (for example ``data.records_view``) would otherwise expose
    the module after a canonical-first import.  Only an existing module value
    is intercepted; ordinary module attributes and module-valued exports keep
    normal semantics.
    """

    def __getattribute__(self, name: str) -> object:
        namespace = ModuleType.__getattribute__(self, "__dict__")
        lazy_exports = namespace.get("_LAZY_EXPORTS")
        if lazy_exports is not None and name in lazy_exports:
            module_name, attribute_name = lazy_exports[name]
            current = namespace.get(name, _MISSING)
            if attribute_name is not None and isinstance(current, ModuleType):
                try:
                    return resolve_lazy_attribute(name, lazy_exports, namespace)
                except AttributeError:
                    # A child may inspect its parent while still initializing.
                    # In that narrow window, preserve the normal module value.
                    spec = getattr(current, "__spec__", None)
                    if spec is not None and getattr(spec, "_initializing", False):
                        return current
                    raise
        return ModuleType.__getattribute__(self, name)


def _install_lazy_export_module(namespace: MutableMapping[str, object]) -> None:
    """Install the shadow-resistant module class on one package initializer."""

    module_name = namespace.get("__name__")
    if isinstance(module_name, str):
        module = sys.modules.get(module_name)
        if module is not None and not isinstance(module, _LazyExportModule):
            module.__class__ = _LazyExportModule


def resolve_lazy_attribute(
    name: str,
    lazy_exports: Mapping[str, LazyExport],
    namespace: MutableMapping[str, object],
) -> object:
    """Resolve and cache one lazy export in a module namespace.

    Only an unknown public name is converted to the module-level
    :class:`AttributeError`.  Import failures and missing target attributes
    intentionally propagate unchanged so an optional or broken target cannot
    be mistaken for an unknown export.
    """

    try:
        module_name, attribute_name = lazy_exports[name]
    except KeyError:
        module_name = namespace.get("__name__", "module")
        raise AttributeError(f"module {module_name!r} has no attribute {name!r}") from None

    module = import_module(module_name, namespace.get("__package__"))
    value = module if attribute_name is None else getattr(module, attribute_name)
    namespace[name] = value
    return value


def lazy_dir(
    namespace: Mapping[str, object],
    lazy_exports: Mapping[str, LazyExport],
    public_names: Sequence[str] = (),
) -> list[str]:
    """Return a deterministic ``dir()`` view including lazy public names."""

    return sorted(set(namespace) | set(lazy_exports) | set(public_names))
