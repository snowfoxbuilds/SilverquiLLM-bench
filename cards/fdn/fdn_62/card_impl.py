"""Card implementation for Hungry Ghoul."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False

class HungryGhoul(Creature):
    """Hungry Ghoul — {1}{B} — 2/2 — Zombie

    {1}, Sacrifice another creature: Put a +1/+1 counter on this creature.

    FDN collector number 62.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Hungry Ghoul")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Zombie"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "{1}, Sacrifice another creature: Put a +1/+1 counter on "
            "this creature.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 1:
                return False
            # Need a target creature to sacrifice (another creature you control)
            sac_target = getattr(src, "_sacrifice_target", None)
            if sac_target is None or sac_target is src:
                return False
            if not _is_on_battlefield(game, sac_target):
                return False
            if getattr(sac_target, "controller", None) is not controller:
                return False
            controller.mana_pool.pay(ManaCost(generic=1))
            from engine.game import sacrifice
            sacrifice(game, controller, sac_target)
            return True

        def _effect(game: Any) -> None:
            from engine.game import add_counter
            if _is_on_battlefield(game, source):
                add_counter(game, source, "+1/+1", 1)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{1}, Sacrifice another creature: Put a +1/+1 "
            "counter on this creature.",
        )]
