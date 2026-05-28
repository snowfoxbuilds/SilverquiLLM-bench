"""Card implementation for Shivan Dragon."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

class ShivanDragon(Creature):
    """Shivan Dragon — {4}{R}{R} — 5/5 — Dragon

    Flying
    {R}: This creature gets +1/+0 until end of turn.

    FDN collector number 206.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Shivan Dragon")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}{R}{R}"))
        kwargs.setdefault("subtypes", {"Dragon"})
        kwargs.setdefault("keywords", Keyword.FLYING)
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Flying\n{R}: This creature gets +1/+0 until end of turn.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.get(ManaType.RED) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{R}"))
            return True

        # ENGINE LIMITATION: pump modifies base_power; no end-of-turn cleanup mechanism in engine
        def _effect(game: Any) -> None:
            # +1/+0 until end of turn — boost base_power
            source.modified_power += 1

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{R}: This creature gets +1/+0 until end of turn.",
        )]
