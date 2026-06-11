"""Card implementation for Campus Composer // Aqueous Aria."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import ActivatedAbility, Creature
from engine.types import CardType, Keyword, ManaCost, Zone

if TYPE_CHECKING:
    from engine.game_state import GameState


class CampusComposerAqueousAria(Creature):
    """Campus Composer // Aqueous Aria — {3}{U} — 3/4 Merfolk Bard.

    Ward {2}.
    This creature enters prepared. (While it's prepared, you may cast a copy
    of its spell. Doing so unprepares it.)
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Campus Composer // Aqueous Aria")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{U}"))
        kwargs.setdefault("subtypes", {"Merfolk", "Bard"})
        kwargs.setdefault("keywords", Keyword.WARD)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 4)
        super().__init__(**kwargs)
        self.prepared: bool = False

    def on_resolve(self, game: "GameState") -> None:
        """ETB: enters prepared."""
        self.prepared = True

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        card = self

        def _cost(game: "GameState") -> bool:
            return card.prepared

        def _effect(game: "GameState") -> None:
            # Cast a copy of the spell side, then unprepare
            card.prepared = False

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="Cast a copy of Aqueous Aria (unprepares this creature).",
        )]
