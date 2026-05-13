"""Card implementation for PainfulQuandary."""

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


class PainfulQuandary(Enchantment):
    """Painful Quandary — {3}{B}{B} — Opponent spell = lose 5 unless discard.

    Whenever an opponent casts a spell, that player loses 5 life unless
    they discard a card.

    FDN collector number 179.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Painful Quandary")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}{B}{B}"))
        kwargs.setdefault(
            "rules_text",
            "Whenever an opponent casts a spell, that player loses 5 life "
            "unless they discard a card.",
        )
        super().__init__(**kwargs)

    def on_resolve(self, game: GameState) -> None:
        pass

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            if not _is_on_battlefield(game, source):
                return False
            spell = data.get("spell")
            if spell is None:
                return False
            controller = source.controller
            if controller is None:
                return False
            spell_controller = getattr(spell, "controller", None)
            return spell_controller is not controller

        def _effect(game: GameState) -> None:
            # ENGINE LIMITATION: Full implementation would offer the
            # opponent a choice to discard.  For now, the opponent simply
            # loses 5 life (the "unless they discard" clause requires a
            # choice engine that doesn't yet exist).
            controller = source.controller
            if controller is None:
                return
            from engine.game import deal_damage
            # Find the opponent who cast the spell — we use the stack
            # or just damage all opponents for simplicity.
            for player in game.players:
                if player is not controller:
                    player.life -= 5
                    game.trigger_manager.fire_event(
                        game,
                        EventType.LOSES_LIFE,
                        {"player": player, "amount": 5},
                    )

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.SPELL_CAST,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["PainfulQuandary"]
