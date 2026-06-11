"""Card implementation for Arnyn, Deathbloom Botanist."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.card import Creature
from engine.types import CardType, Keyword, ManaCost, Supertype

if TYPE_CHECKING:
    from engine.game_state import GameState
    from engine.player import Player


class ArnynDeathbloomBotanist(Creature):
    """Arnyn, Deathbloom Botanist — {2}{B} — Legendary Creature — Vampire Druid.

    Deathtouch
    Whenever a creature you control with power or toughness 1 or less dies,
    target opponent loses 2 life and you gain 2 life.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Arnyn, Deathbloom Botanist")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault("keywords", Keyword.DEATHTOUCH)
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("subtypes", {"Vampire", "Druid"})
        super().__init__(**kwargs)

    def on_creature_dies(self, game: "GameState", creature: Any, target_opponent: "Player" = None) -> None:
        """Trigger: whenever a creature you control with power or toughness <= 1 dies."""
        power = getattr(creature, "base_power", None)
        toughness = getattr(creature, "base_toughness", None)
        if power is None or toughness is None:
            return

        if power <= 1 or toughness <= 1:
            controller = self.controller or self.owner
            if target_opponent is not None:
                target_opponent.life -= 2
                controller.life += 2
