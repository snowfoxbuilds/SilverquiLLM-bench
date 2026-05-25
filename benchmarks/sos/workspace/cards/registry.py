"""Card registry and metadata for mapping card names to implementations.

Provides:
- ``CardMetadata`` — dataclass holding Scryfall-sourced card data.
- ``CardRegistry`` — maps card names to ``(impl_class, metadata)`` pairs.
- ``default_registry`` — module-level singleton registry instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from engine.card import CardImpl

if TYPE_CHECKING:
    from engine.player import Player


@dataclass
class CardMetadata:
    """Card metadata sourced from Scryfall or similar data providers.

    Attributes:
        name: Card name (e.g. ``"Lightning Bolt"``).
        mana_cost_str: Raw mana cost string (e.g. ``"{R}"``).
        type_line: Full type line (e.g. ``"Instant"``).
        oracle_text: Oracle rules text.
        power: Power as a string (``None`` for non-creatures).
        toughness: Toughness as a string (``None`` for non-creatures).
        colors: List of color letters (e.g. ``["R"]``).
        keywords: List of keyword ability strings (e.g. ``["Flying", "Haste"]``).
        rarity: Rarity string (e.g. ``"common"``, ``"rare"``).
        set_code: Set code (e.g. ``"fdn"``).
        collector_number: Collector number within the set.
    """

    name: str = ""
    mana_cost_str: str = ""
    type_line: str = ""
    oracle_text: str = ""
    power: str | None = None
    toughness: str | None = None
    colors: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    rarity: str = ""
    set_code: str = ""
    collector_number: str = ""


class CardRegistry:
    """Registry mapping card names to implementation classes and metadata.

    Supports registering, looking up, creating instances, and listing cards.
    """

    def __init__(self) -> None:
        self._entries: dict[str, tuple[type[CardImpl], CardMetadata]] = {}

    def register(
        self,
        name: str,
        impl_class: type[CardImpl],
        metadata: CardMetadata | None = None,
    ) -> None:
        """Register a card implementation with optional metadata.

        Args:
            name: The card name (case-sensitive).
            impl_class: The :class:`~engine.card.CardImpl` subclass for
                this card.
            metadata: Optional :class:`CardMetadata` for the card.  If
                ``None``, a default ``CardMetadata(name=name)`` is stored.
        """
        if metadata is None:
            metadata = CardMetadata(name=name)
        self._entries[name] = (impl_class, metadata)

    def get(self, name: str) -> tuple[type[CardImpl], CardMetadata]:
        """Look up a card by name.

        Args:
            name: The card name.

        Returns:
            A ``(impl_class, metadata)`` tuple.

        Raises:
            KeyError: If *name* is not registered.
        """
        if name not in self._entries:
            raise KeyError(f"Card not registered: {name!r}")
        return self._entries[name]

    def create_instance(self, name: str, owner: Player | None = None) -> CardImpl:
        """Create a new card instance from the registry.

        Args:
            name: The card name.
            owner: The player who owns the card.

        Returns:
            A new :class:`~engine.card.CardImpl` instance.

        Raises:
            KeyError: If *name* is not registered.
        """
        impl_class, _metadata = self.get(name)
        return impl_class(name=name, owner=owner)

    def list_all(self) -> list[str]:
        """Return a sorted list of all registered card names."""
        return sorted(self._entries.keys())

    def __contains__(self, name: str) -> bool:
        """Return ``True`` if *name* is registered."""
        return name in self._entries

    def __len__(self) -> int:
        """Return the number of registered cards."""
        return len(self._entries)


# Module-level default registry instance.
default_registry: CardRegistry = CardRegistry()
