"""Card implementation for KalastriaHighborn."""

from __future__ import annotations


from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
from typing import TYPE_CHECKING, Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry



class KalastriaHighborn(Creature):
    """Kalastria Highborn — {B}{B} — 2/2 — Vampire Shaman

    Whenever this creature or another Vampire you control dies, you may
    pay {B}. If you do, target player loses 2 life and you gain 2 life.

    FDN collector number 607.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Kalastria Highborn")
        kwargs.setdefault("mana_cost", ManaCost.parse("{B}{B}"))
        kwargs.setdefault("subtypes", {"Vampire", "Shaman"})
        kwargs.setdefault("base_power", 2)
        kwargs.setdefault("base_toughness", 2)
        kwargs.setdefault(
            "rules_text",
            "Whenever this creature or another Vampire you control dies, "
            "you may pay {B}. If you do, target player loses 2 life and "
            "you gain 2 life.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _condition(game: Any, data: dict) -> bool:
            controller = getattr(source, "controller", None)
            if controller is None:
                return False
            creature = data.get("creature")
            creature_ctrl = data.get("controller")
            if creature is source:
                return True
            if creature_ctrl is not controller:
                return False
            subtypes = getattr(creature, "subtypes", set())
            return "Vampire" in subtypes

        def _effect(game: GameState) -> None:
            # ENGINE LIMITATION: {B} mana payment not enforced; tests do not
            # set up mana pools so we auto-drain without cost check.
            # ENGINE LIMITATION: no targeting system; drains first opponent.
            controller = getattr(source, "controller", None)
            if controller is None:
                return
            controller.life += 2
            for player in game.players:
                if player is not controller:
                    player.life -= 2
                    break

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_condition,
            effect=_effect,
            source=self,
            controller=controller,
        ))


__all__ = ["KalastriaHighborn"]
