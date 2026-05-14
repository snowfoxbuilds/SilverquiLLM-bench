"""Card implementation for Cathar Commando."""

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

class CatharCommando(Creature):
    """Cathar Commando — {1}{W} — 3/1 — Human Soldier

    Flash
    {1}, Sacrifice this creature: Destroy target artifact or enchantment.

    FDN collector number 139.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Cathar Commando")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{W}"))
        kwargs.setdefault("subtypes", {"Human", "Soldier"})
        kwargs.setdefault("keywords", Keyword.FLASH)
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Flash\n{1}, Sacrifice this creature: Destroy target artifact "
            "or enchantment.",
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
            controller.mana_pool.pay(ManaCost(generic=1))
            # Sacrifice self
            from engine.game import sacrifice
            sacrifice(game, controller, src)
            return True

        def _effect(game: Any) -> None:
            from engine.game import destroy

            target = getattr(source, "_current_target", None)
            if target is None:
                return
            if not _is_on_battlefield(game, target):
                return
            # Only targets artifacts or enchantments
            target_types = getattr(target, "card_types", set())
            if CardType.ARTIFACT in target_types or CardType.ENCHANTMENT in target_types:
                destroy(game, target)

        return [ActivatedAbility(
            cost=_cost,
            effect=_effect,
            description="{1}, Sacrifice this creature: Destroy target "
            "artifact or enchantment.",
        )]
