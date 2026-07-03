"""Card implementation for Island."""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType, Supertype


class Island(Land):
    """Island — Basic Land — Island.

    ({T}: Add {U}.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Island")
        kwargs.setdefault("supertypes", {Supertype.BASIC})
        kwargs.setdefault("subtypes", {"Island"})
        super().__init__(**kwargs)

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, player: Any = None) -> None:
            source.is_tapped = True

        def _produce(game: Any = None, src: Any = None, player: Any = None) -> None:
            pass

        return [ManaAbility(
            cost=_cost,
            mana_produced=_produce,
            description="{T}: Add {U}.",
            mana_types=[ManaType.BLUE],
        )]

    def enter_battlefield(self, game: Any, **kwargs: Any) -> None:
        """Basic lands enter untapped."""
        self.is_tapped = False

