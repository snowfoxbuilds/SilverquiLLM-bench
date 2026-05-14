"""Card implementation for Vengeful Bloodwitch."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

class VengefulBloodwitch(Creature):
    """Vengeful Bloodwitch — {1}{B} — 1/1 — Vampire Warlock

    Whenever this creature or another creature you control dies, target
    opponent loses 1 life and you gain 1 life.

    FDN collector number 76.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Vengeful Bloodwitch")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Warlock"})
        kwargs.setdefault("base_power", 1)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "Whenever this creature or another creature you control dies, "
            "target opponent loses 1 life and you gain 1 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            creature = data.get("creature")
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            creature_ctrl = data.get("controller")
            # Fires when self dies OR another creature you control dies
            if creature is source:
                return True
            if creature_ctrl is controller:
                return True
            return False

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # ENGINE LIMITATION: no targeting system; drains first opponent
            controller.life += 1
            for player in game.players:
                if player is not controller:
                    player.life -= 1
                    break

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))
