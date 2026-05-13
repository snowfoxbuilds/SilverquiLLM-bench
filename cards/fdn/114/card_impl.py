"""Card implementation for TreetopSnarespinner."""

from __future__ import annotations


from engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
from typing import TYPE_CHECKING, Any
import random


def _is_on_battlefield(game: Any, card: Any) -> bool:
    """Check if *card* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(card):
            return True
    return False


class TreetopSnarespinner(Creature):
    """Treetop Snarespinner — {3}{G} — 1/4 — Spider

    Reach
    Deathtouch
    {2}{G}: Put a +1/+1 counter on target creature you control. Activate
    only as a sorcery.

    FDN collector number 114.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Treetop Snarespinner")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{G}"))
        kwargs.setdefault("subtypes", {"Spider"})
        kwargs.setdefault("keywords", Keyword.REACH | Keyword.DEATHTOUCH)
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 4)
        kwargs.setdefault(
            "rules_text",
            "Reach\nDeathtouch\n{2}{G}: Put a +1/+1 counter on target "
            "creature you control. Activate only as a sorcery.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            controller = src.controller
            if controller is None:
                return False
            if controller.mana_pool.total() < 3:
                return False
            if controller.mana_pool.get(ManaType.GREEN) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{2}{G}"))
            return True

        # ENGINE LIMITATION: sorcery-speed timing not enforced
        def _effect(game: Any) -> None:
            from engine.game import add_counter

            target = getattr(source, "_current_target", None)
            if target is None:
                return
            # Must target a creature you control
            controller = source.controller
            if getattr(target, "controller", None) is not controller:
                return
            if _is_on_battlefield(game, target):
                add_counter(game, target, "+1/+1", 1)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{2}{G}: Put a +1/+1 counter on target creature "
            "you control. Activate only as a sorcery.",
        )]


__all__ = ["TreetopSnarespinner"]
