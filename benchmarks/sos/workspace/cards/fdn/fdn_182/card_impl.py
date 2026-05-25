"""Card implementation for Reassembling Skeleton."""

from __future__ import annotations
import random
from typing import TYPE_CHECKING, Any
from engine.card import ActivatedAbility, ArtifactCreature, Creature, ManaAbility
from engine.types import CardType, Keyword, ManaCost, ManaType, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

class ReassemblingSkeleton(Creature):
    """Reassembling Skeleton — {1}{B} — 1/1 — Skeleton Warrior

    {1}{B}: Return this card from your graveyard to the battlefield tapped.

    FDN collector number 182.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Reassembling Skeleton")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Skeleton", "Warrior"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "{1}{B}: Return this card from your graveyard to the "
            "battlefield tapped.",
        )
        super().__init__(**kwargs)

    def get_activated_abilities(self) -> list[ActivatedAbility]:
        source = self

        def _cost(game: Any, src: Any) -> bool:
            # Can only be activated from the graveyard
            controller = src.owner  # use owner since controller may be None
            if controller is None:
                return False
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(src):
                return False
            if controller.mana_pool.total() < 2:
                return False
            if controller.mana_pool.get(ManaType.BLACK) < 1:
                return False
            controller.mana_pool.pay(ManaCost.parse("{1}{B}"))
            return True

        def _effect(game: Any) -> None:
            controller = source.owner
            if controller is None:
                return
            graveyard = controller.zones[Zone.GRAVEYARD]
            if not graveyard.contains(source):
                return
            graveyard.remove(source)
            source.controller = controller
            source.is_tapped = True
            source.damage_marked = 0
            source.summoning_sick = True
            # Clear accumulated state — return as fresh creature
            source.plus_one_counters = 0
            if hasattr(source, "counters"):
                source.counters.clear()
            bf = game.get_battlefield(controller)
            bf.add(source)
            # Register triggers
            if hasattr(source, "register_triggers"):
                source.register_triggers(game)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{1}{B}: Return this card from your graveyard to "
            "the battlefield tapped.",
        )]
