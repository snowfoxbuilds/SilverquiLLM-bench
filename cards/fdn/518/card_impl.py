"""Card implementation for CrosswayTroublemakers."""

from __future__ import annotations


from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry



class CrosswayTroublemakers(Creature):
    """Crossway Troublemakers — {5}{B} — 5/5 — Vampire

    Attacking Vampires you control have deathtouch and lifelink.
    Whenever a Vampire you control dies, you may pay 2 life. If you do,
    draw a card.

    FDN collector number 518.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Crossway Troublemakers")
        kwargs.setdefault("mana_cost", ManaCost.parse("{5}{B}"))
        kwargs.setdefault("subtypes", {"Vampire"})
        kwargs.setdefault("base_power", 5)
        kwargs.setdefault("base_toughness", 5)
        kwargs.setdefault(
            "rules_text",
            "Attacking Vampires you control have deathtouch and lifelink.\n"
            "Whenever a Vampire you control dies, you may pay 2 life. If "
            "you do, draw a card.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration
        from engine.game import draw_card

        source = self

        # ENGINE LIMITATION: Continuous effect granting deathtouch and
        # lifelink to attacking Vampires not implemented. Would need
        # combat phase tracking and a Layer.ABILITY_ADDING effect.

        def _condition(game: Any, data: dict) -> bool:
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            creature = data.get("creature")
            creature_ctrl = data.get("controller")
            if creature_ctrl is not controller:
                return False
            # Must be a Vampire
            subtypes = getattr(creature, "subtypes", set())
            return "Vampire" in subtypes

        def _effect(game: GameState) -> None:
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            # ENGINE LIMITATION: no interactive choice system; auto-pays 2 life
            # "You may pay 2 life" — simplified: always pay if able
            if controller.life >= 2:
                controller.life -= 2
                draw_card(game, controller)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["CrosswayTroublemakers"]
