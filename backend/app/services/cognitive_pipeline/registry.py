"""
Generic registry pattern for pluggable pipeline components.

Each pipeline component (Context Builder, Executor, etc.) has its own
typed registry that maps strategy names to implementation instances.
"""

from __future__ import annotations

from typing import Dict, Generic, List, TypeVar

T = TypeVar("T")


class Registry(Generic[T]):
    """A typed registry mapping names to component instances.

    Usage::

        registry = Registry[ContextBuilder]()
        registry.register("default", DefaultContextBuilder())
        registry.register("augmented", AugmentedContextBuilder())
        builder = registry.get("augmented")
    """

    def __init__(self) -> None:
        self._entries: Dict[str, T] = {}

    def register(self, name: str, instance: T, overwrite: bool = False) -> None:
        """Register a component implementation under *name*.

        Raises ``KeyError`` if *name* is already registered and *overwrite*
        is ``False``.
        """
        if name in self._entries and not overwrite:
            raise KeyError(
                f"'{name}' is already registered. Use overwrite=True to replace."
            )
        self._entries[name] = instance

    def get(self, name: str) -> T:
        """Retrieve a registered implementation by name.

        Raises ``KeyError`` if *name* is not registered.
        """
        if name not in self._entries:
            raise KeyError(
                f"'{name}' is not registered. "
                f"Available: {', '.join(sorted(self._entries))}"
            )
        return self._entries[name]

    def list(self) -> List[str]:
        """Return sorted list of registered names."""
        return sorted(self._entries)

    def unregister(self, name: str) -> None:
        """Remove a registered implementation."""
        self._entries.pop(name, None)

    def __contains__(self, name: str) -> bool:
        return name in self._entries

    def __len__(self) -> int:
        return len(self._entries)
