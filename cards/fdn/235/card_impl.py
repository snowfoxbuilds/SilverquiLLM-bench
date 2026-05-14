"""Card implementation for Wary Thespian."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any
from engine.card import ArtifactCreature, Creature
from engine.types import CardType, Keyword, ManaCost, Supertype, Zone
if TYPE_CHECKING:
    from engine.game_state import GameState

    from cards.registry import CardRegistry

def _self_dies_condition(source: Any):
    """Return a condition callable that matches only when *source* dies."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("creature") is source

    return _condition
def _self_etb_condition(source: Any):
    """Return a condition callable that matches only when *source* enters."""

    def _condition(game: Any, data: dict) -> bool:
        return data.get("permanent") is source

    return _condition

class WaryThespian(Creature):
    """Wary Thespian — {1}{G} — 3/1 — Cat Druid

    When this creature enters or dies, surveil 1.

    FDN collector number 235.
    """

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Wary Thespian")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}{G}"))
        kwargs.setdefault("subtypes", {"Cat", "Druid"})
        kwargs.setdefault("base_power", 3)
        kwargs.setdefault("base_toughness", 1)
        kwargs.setdefault(
            "rules_text",
            "When this creature enters or dies, surveil 1.",
        )
        super().__init__(**kwargs)

    def register_triggers(self, game: GameState) -> None:
        from engine.triggers import EventType, TriggerRegistration

        source = self

        def _surveil_effect(game: GameState) -> None:
            controller = (
                getattr(source, "controller", None)
                or getattr(source, "owner", None)
            )
            if controller is None:
                return
            library = controller.zones[Zone.LIBRARY]
            if len(library) > 0:
                card = library.top(1)[0]
                library.remove(card)
                # Surveil: may put into graveyard (simplified: always
                # put into graveyard for deterministic behaviour).
                graveyard = controller.zones[Zone.GRAVEYARD]
                graveyard.add(card)

        controller = getattr(self, "controller", None) or game.active_player
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.ENTERS_BATTLEFIELD,
            condition=_self_etb_condition(self),
            effect=_surveil_effect,
            source=self,
            controller=controller,
        ))
        game.trigger_manager.register(TriggerRegistration(
            event_type=EventType.CREATURE_DIES,
            condition=_self_dies_condition(self),
            effect=_surveil_effect,
            source=self,
            controller=controller,
        ))
