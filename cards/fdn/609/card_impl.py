"""Card implementation for MidnightReaper."""

from __future__ import annotations


from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry



class MidnightReaper(Creature):
    """Midnight Reaper — {2}{B} — 3/2 — Zombie Knight

    Whenever a nontoken creature you control dies, this creature deals
    1 damage to you and you draw a card.

    FDN collector number 609.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Midnight Reaper")
        kwargs.setdefault("mana_cost", ManaCost.parse("{2}{B}"))
        kwargs.setdefault("subtypes", {"Zombie", "Knight"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Whenever a nontoken creature you control dies, this creature "
            "deals 1 damage to you and you draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        def _condition(game: Any, data: dict) -> bool:
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            creature = data.get("creature")
            creature_ctrl = data.get("controller")
            if creature_ctrl is not controller:
                return False
            # Must be nontoken
            if getattr(creature, "is_token", False):
                return False
            return True

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # Deal 1 damage to you
            controller.life -= 1
            draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["MidnightReaper"]
