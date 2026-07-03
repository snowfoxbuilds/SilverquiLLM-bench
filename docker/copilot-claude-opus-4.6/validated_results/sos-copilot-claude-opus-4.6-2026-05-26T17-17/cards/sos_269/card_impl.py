"""Card implementation for Swamp."""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType, Supertype


class Swamp(Land):
    """Swamp — Basic Land — Swamp.

    ({T}: Add {B}.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Swamp")
        kwargs.setdefault("supertypes", {Supertype.BASIC})
        kwargs.setdefault("subtypes", {"Swamp"})
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
            description="{T}: Add {B}.",
            mana_types=[ManaType.BLACK],
        )]

    def enter_battlefield(self, game: Any, **kwargs: Any) -> None:
        """Basic lands enter untapped."""
        self.is_tapped = False

