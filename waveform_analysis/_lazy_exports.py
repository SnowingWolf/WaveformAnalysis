"""Small standard-library helpers for module-level lazy exports.

The helper deliberately does not know anything about WaveformAnalysis.  A
module supplies a mapping from public names to ``(module, attribute)`` pairs;
the target is imported only when that public name is requested.
"""

from collections.abc import Mapping, MutableMapping, Sequence
from importlib import import_module

LazyExport = tuple[str, str | None]

__all__ = ["LazyExport", "lazy_dir", "resolve_lazy_attribute"]


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
