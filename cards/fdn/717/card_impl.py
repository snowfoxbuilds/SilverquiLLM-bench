"""Card implementation for ImpactTremors."""

from __future__ import annotations


from dataclasses import dataclass
from engine.card import ActivatedAbility, Creature, Enchantment
from engine.continuous_effects import (
    ContinuousEffect,
    DURATION_PERMANENT,
    Layer,
    SubLayer,
)
from engine.types import CardType, Keyword, ManaCost, TargetRequirement, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry


def _is_on_battlefield(game: Any, obj: Any) -> bool:
    """Check if *obj* is on any player's battlefield."""
    for player in game.players:
        if game.get_battlefield(player).contains(obj):
            return True
    return False


class ImpactTremors(Enchantment):
    """Impact Tremors — {1}{R} — Deal 1 damage to each opponent on creature ETB.

    Whenever a creature you control enters, this enchantment deals 1 damage
    to each opponent.

    FDN collector number 717.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Impact Tremors")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{R}"))
        kwargs.setdefault(
            "rules_text",
            "Whenever a creature you control enters, this enchantment deals "
            "1 damage to each opponent.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        pass

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import deal_damage

        source = self

        def _condition(game: Any, data: dict) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            permanent = data.get("permanent")
            if permanent is None:
                return False
            controller = source.controller
            if controller is None:
                return False
            if getattr(permanent, "controller", None) is not controller:
                return False
            return CardType.CREATURE in getattr(permanent, "card_types", set())

        def _effect(game: GameState) -> None:
            controller = source.controller
            if controller is None:
                return
            for player in game.players:
                if player is not controller:
                    deal_damage(game, source, player, 1)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["ImpactTremors"]
