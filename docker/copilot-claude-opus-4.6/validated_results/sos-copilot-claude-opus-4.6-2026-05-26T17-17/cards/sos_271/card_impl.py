"""Card implementation for Forest."""

from __future__ import annotations

from typing import Any

from engine.card import Land, ManaAbility
from engine.types import ManaType, Supertype


class Forest(Land):
    """Forest — Basic Land — Forest.

    ({T}: Add {G}.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Forest")
        kwargs.setdefault("supertypes", {Supertype.BASIC})
        kwargs.setdefault("subtypes", {"Forest"})
        super().__init__(**kwargs)
        self.mana_cost = None

    def get_mana_abilities(self) -> list[ManaAbility]:
        source = self

        def _cost(game: Any = None, src: Any = None, *args: Any, **kwargs: Any) -> bool:
            if source.is_tapped:
                return False
            source.is_tapped = True
            return True

        def _produce(game: Any = None, *args: Any, **kwargs: Any) -> None:
            if source.controller is not None:
                source.controller.mana_pool.add(ManaType.GREEN, 1)

        return [ManaAbility(
            cost=_cost,
            mana_produced=_produce,
            description="{T}: Add {G}.",
            mana_types=[ManaType.GREEN],
        )]

    def enter_battlefield(self, game: Any, **kwargs: Any) -> None:
        """Basic lands enter untapped."""
        self.is_tapped = False
