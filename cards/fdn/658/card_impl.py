"""Card implementation for GarnaBloodfistOfKeld."""

from __future__ import annotations


from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry



class GarnaBloodfistOfKeld(Creature):
    """Garna, Bloodfist of Keld — {1}{B}{R}{R} — 4/3 — Legendary Human Berserker

    Whenever another creature you control dies, draw a card if it was
    attacking. Otherwise, Garna deals 1 damage to each opponent.

    FDN collector number 658.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Garna, Bloodfist of Keld")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}{R}{R}"))
        kwargs.setdefault("subtypes", {"Human", "Berserker"})
        kwargs.setdefault("supertypes", {Supertype.LEGENDARY})
        kwargs.setdefault("base_power", 4)
        kwargs.setdefault("base_toughness", 3)
        kwargs.setdefault(
            "rules_text",
            "Whenever another creature you control dies, draw a card if "
            "it was attacking. Otherwise, Garna deals 1 damage to each "
            "opponent.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _condition(game: Any, data: dict) -> bool:
            creature = data.get("creature")
            if creature is source:
                return False  # "another"
            controller = getattr(source, "controller", None)
            creature_ctrl = data.get("controller")
            return creature_ctrl is controller

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # ENGINE LIMITATION: no attack state tracking; always takes the
            # "nonattacking" branch (deals 1 damage to each opponent)
            for player in game.players:
                if player is not controller:
                    player.life -= 1

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["GarnaBloodfistOfKeld"]
